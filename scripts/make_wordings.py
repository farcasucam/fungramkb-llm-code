"""Alternative wordings (W2, W3) of the deep contrast items of a benchmark (prompt robustness, P16).

W2 (rule-based) is always produced. W3 (LLM paraphrase) is produced when a paraphrasing server is given;
the paraphraser must NOT be one of the evaluated models. Paraphrases are cached (resumable) and filtered
by automatic checks; a stratified sample is written for human audit.

    # W2 only, and the list of noun alternatives for expert approval
    python scripts/make_wordings.py --bench data/processed/fgkb_reason_main.jsonl \\
        --synonym-candidates docs/w2_synonym_candidates.tsv

    # W2 with approved synonyms + W3 with a paraphrasing model served by vLLM on the Spark
    python scripts/make_wordings.py --bench data/processed/fgkb_reason_main.jsonl \\
        --synonyms data/extension/w2_synonyms.json \\
        --paraphrase-url http://192.168.1.112:8003/v1 --paraphrase-model mistralai/Mistral-Small-3.2-24B-Instruct-2506

Output: data/processed/fgkb_reason_main_wordings.jsonl (items "<id>@w2" / "<id>@w3", same gold, patch and
property as the original; pair_id suffixed with the wording so EN/ES twins stay paired within a wording).
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
import random
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fgkb_llm.bench import wording as W
from fgkb_llm.bench.contrast import contrast_subset
from fgkb_llm.bench.schema import read_jsonl, write_jsonl
from fgkb_llm.conditions.prompts import ContextBuilder
from fgkb_llm.kb.loaders import load_json


def synonym_candidates(kb, items, ctx, path):
    """TSV of (concept, language, current lemma, proposed alternative, all lemmas, n items) for approval."""
    seen = collections.Counter()
    for it in items:
        sub = ctx.for_item(it)
        for cid in sub.linker.concepts(it.question, it.lang):
            con = kb.concepts.get(cid)
            if con is not None and con.semantic_type == "entity" and len(kb.lemmas(cid, it.lang)) > 1:
                seen[(cid, it.lang)] += 1
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["concept", "lang", "lemma_used", "proposed_alternative", "all_lemmas", "n_items",
                    "approved_alternative (leave empty to reject)"])
        for (cid, lang), n in sorted(seen.items(), key=lambda kv: (-kv[1], kv[0])):
            alt = W.candidate_alternative(kb, cid, lang) or ""
            w.writerow([cid, lang, kb.label(cid, lang), alt, " | ".join(kb.lemmas(cid, lang)), n, ""])
    print(f"{len(seen)} (concept, language) pairs with alternative lemmas -> {path}")


def load_synonyms(path):
    """JSON {concept: {lang: lemma}} or the candidate TSV with the approval column filled in."""
    if not path:
        return None
    p = Path(path)
    if p.suffix == ".json":
        return json.loads(p.read_text(encoding="utf-8"))
    out = collections.defaultdict(dict)
    with open(p, encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            alt = (row.get("approved_alternative (leave empty to reject)") or "").strip()
            if alt:
                out[row["concept"]][row["lang"]] = alt
    return dict(out)


def load_cache(items, ctx, cache_path):
    """Cached paraphrases, re-checked with the current cleaning and checks: the first attempt that passes
    is used (so improving the checks never needs the paraphrasing server again)."""
    by_id = {it.id: it for it in items}
    cache = {}
    if not Path(cache_path).exists():
        return cache
    for line in Path(cache_path).read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        it = by_id.get(r["id"])
        if it is None:
            continue
        sub = ctx.for_item(it)
        for att in r["attempts"]:
            att["error"] = W.check_paraphrase(r["source"], att["text"], it, sub.kb, sub.linker)
        good = [att for att in r["attempts"] if att["error"] is None]
        chosen = good[0] if good else r["attempts"][-1]
        r["paraphrase"], r["ok"], r["error"] = W.clean_paraphrase(chosen["text"]), not chosen["error"], chosen["error"]
        cache[r["id"]] = r
    return cache


def paraphrase_all(items, kb, ctx, url, model, cache_path, workers=32, tries=3, retry_failed=False):
    from openai import OpenAI

    client = OpenAI(base_url=url, api_key="EMPTY", timeout=300)
    cache = load_cache(items, ctx, cache_path)
    todo = [it for it in items if it.id not in cache or (retry_failed and not cache[it.id]["ok"])]
    print(f"W3: {len(cache)} cached ({sum(r['ok'] for r in cache.values())} pass), {len(todo)} to paraphrase "
          f"with {model}", flush=True)

    def one(it):
        src = W.paraphrase_source(it)
        sub = ctx.for_item(it)
        pseudo = ", ".join(W.pseudowords(it, sub.kb)) or ("none in this text" if it.lang == "en" else "ninguna en este texto")
        prompt = W.PARAPHRASE_PROMPT[it.lang].format(text=src, pseudo=pseudo)
        attempts = []
        for k in range(tries):
            r = client.chat.completions.create(
                model=model, messages=[{"role": "user", "content": prompt}], max_tokens=256,
                temperature=0.0 if k == 0 else 0.7, seed=k)
            para = (r.choices[0].message.content or "").strip()
            err = W.check_paraphrase(src, para, it, sub.kb, sub.linker)
            attempts.append({"text": para, "error": err})
            if err is None:
                break
        good = [att for att in attempts if att["error"] is None]
        chosen = good[0] if good else attempts[-1]
        return {"id": it.id, "lang": it.lang, "source": src, "paraphrase": W.clean_paraphrase(chosen["text"]),
                "ok": chosen["error"] is None, "error": chosen["error"], "attempts": attempts, "model": model}

    t0 = time.time()
    with open(cache_path, "a", encoding="utf-8") as fh, ThreadPoolExecutor(workers) as ex:
        for n, rec in enumerate(ex.map(one, todo), 1):
            cache[rec["id"]] = rec
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            if n % 100 == 0 or n == len(todo):
                print(f"W3: {n}/{len(todo)} paraphrased, {(time.time() - t0) / 60:.1f} min", flush=True)
    return cache


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--kb", default="data/processed/fungramkb.json")
    ap.add_argument("--bench", default="data/processed/fgkb_reason_main.jsonl")
    ap.add_argument("--out", default="data/processed/fgkb_reason_main_wordings.jsonl")
    ap.add_argument("--synonyms", default=None, help="approved noun alternatives (JSON or filled-in TSV)")
    ap.add_argument("--synonym-candidates", default=None, help="write the TSV of candidates for approval")
    ap.add_argument("--paraphrase-url", default=None)
    ap.add_argument("--paraphrase-model", default=None)
    ap.add_argument("--paraphrase-cache", default="data/processed/w3_paraphrases.jsonl")
    ap.add_argument("--retry-failed", action="store_true", help="paraphrase again the cached items that fail")
    ap.add_argument("--audit", default="docs/w3_audit_sample.tsv")
    ap.add_argument("--audit-n", type=int, default=100)
    ap.add_argument("--summary", default="docs/wordings_summary.json")
    ap.add_argument("--include-w1", action="store_true",
                    help="also write the original items (meta.wording = w1), so one run covers all wordings")
    a = ap.parse_args(argv)

    kb = load_json(a.kb)
    ctx = ContextBuilder(kb)
    items = contrast_subset([i for i in read_jsonl(a.bench) if i.task == "deep"])
    if a.synonym_candidates:
        synonym_candidates(kb, items, ctx, a.synonym_candidates)

    approved = load_synonyms(a.synonyms)
    out, summary = [], collections.Counter()
    for it in items:
        sub = ctx.for_item(it)
        w2 = W.w2_item(sub.kb, sub.linker, it, approved)
        if w2 is None:
            summary["w2_failed"] += 1
            continue
        summary["w2"] += 1
        summary["w2_with_lexical_substitution"] += bool(w2.meta["substitutions"])
        out.append(w2)

    cache = None
    if a.paraphrase_url and a.paraphrase_model:
        cache = paraphrase_all(items, kb, ctx, a.paraphrase_url, a.paraphrase_model, a.paraphrase_cache,
                               retry_failed=a.retry_failed)
    elif Path(a.paraphrase_cache).exists():  # rebuild W3 from the cache, no server needed
        cache = load_cache(items, ctx, a.paraphrase_cache)
    if cache:
        reasons = collections.Counter()
        ok_ids = {i for i, r in cache.items() if r["ok"]}
        by_id = {it.id: it for it in items}
        # keep W3 only for complete twin groups, so EN/ES clusters stay comparable
        groups = collections.defaultdict(list)
        for it in items:
            groups[it.pair_id or it.id].append(it.id)
        for ids in groups.values():
            if all(i in ok_ids for i in ids):
                for i in ids:
                    sub = ctx.for_item(by_id[i])
                    flag = W.subject_changed(cache[i]["paraphrase"], by_id[i], sub.kb, sub.linker)
                    out.append(W.w3_item(by_id[i], cache[i]["paraphrase"], subject_changed=flag))
                    summary["w3"] += 1
                    summary["w3_subject_changed"] += flag
            else:
                summary["w3_groups_dropped"] += 1
        for r in cache.values():
            if not r["ok"]:
                reasons[r.get("error") or r["attempts"][-1]["error"]] += 1
        summary["w3_rejection_reasons"] = dict(reasons)
        # stratified audit sample (block x language)
        rng = random.Random(7)
        strata = collections.defaultdict(list)
        for i in sorted(ok_ids):
            strata[(by_id[i].meta.get("block"), by_id[i].lang)].append(i)
        per = max(1, a.audit_n // max(1, len(strata)))
        if Path(a.audit).exists():  # never overwrite a sheet that may already be under human annotation
            print(f"audit sample {a.audit} exists: not overwritten")
        else:
            with open(a.audit, "w", encoding="utf-8", newline="") as fh:
                w = csv.writer(fh, delimiter="\t")
                w.writerow(["id", "lang", "block", "original", "paraphrase", "same_meaning (1/0)", "comment"])
                for key in sorted(strata, key=str):
                    for i in rng.sample(strata[key], min(per, len(strata[key]))):
                        w.writerow([i, by_id[i].lang, key[0], cache[i]["source"], cache[i]["paraphrase"], "", ""])

    if a.include_w1:
        for it in items:
            it.meta = {**it.meta, "wording": "w1", "base_id": it.id}
        out = items + out
        summary["w1"] = len(items)
    write_jsonl(out, a.out)
    summary["items_in_contrast_subset"] = len(items)
    Path(a.summary).write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

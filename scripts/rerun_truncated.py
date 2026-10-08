"""Re-generate answers that were cut off by the token limit (no final 'Answer:' line).

At temperature 0 the first max_tokens tokens are the same, so re-generating only the truncated rows
with a larger limit is equivalent to having used that limit for every row. Applies to all prompted
conditions alike (B*, R*, G*, F*, and N1/N2 fallback rows). The old file is backed up.

    python scripts/rerun_truncated.py --config configs/pilot_spark_vllm_remote.yaml --max-tokens 1024

Exploratory second regeneration that leaves the confirmatory file untouched (``--out``): only the
re-generated rows are written to the new file; analyses read both files, the later one overriding.

    python scripts/rerun_truncated.py --config configs/main_qwen_llama.yaml --max-tokens 2048 \
        --models llama3.1-8b-instruct-bf16 --conditions R1 --out results/main_rerun2048.jsonl
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import yaml

from fgkb_llm.bench.schema import read_jsonl
from fgkb_llm.conditions.prompts import ABLATIONS, ContextBuilder
from fgkb_llm.eval.parse import parse_answer
from fgkb_llm.kb.loaders import load_json
from fgkb_llm.llm.backends import GenConfig, make_backend
from fgkb_llm.runner import make_encoder


def _retry(fn, attempts: int = 8):
    """Run a file operation, retrying transient OS errors from synced folders (Google Drive)."""
    for k in range(attempts):
        try:
            return fn()
        except OSError as exc:
            if k == attempts - 1:
                raise
            print(f"  file operation failed ({exc}); retrying in {min(2 ** k, 30)} s", flush=True)
            time.sleep(min(2 ** k, 30))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--max-tokens", type=int, default=1024)
    ap.add_argument("--models", nargs="*", help="only these model names (default: all of the config)")
    ap.add_argument("--conditions", nargs="*", help="only these conditions (default: all prompted ones)")
    ap.add_argument("--out", default=None,
                    help="write only the re-generated rows to this file and leave the results file unchanged")
    a = ap.parse_args(argv)
    cfg = yaml.safe_load(Path(a.config).read_text(encoding="utf-8"))
    out = Path(cfg["output"])
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines() if line.strip()]
    specs = {m.get("name", m.get("model")): m for m in cfg["models"]
             if not a.models or m.get("name", m.get("model")) in a.models}
    # only rows of the models in this config (the output file is shared by several configs), and not rows
    # already re-generated at this length: at temperature 0 a second attempt gives the same answer
    todo = [k for k, r in enumerate(rows) if r.get("pred") is None and r.get("model") in specs
            and (r.get("condition") not in ("N1", "N2", "N1R", "N1P", "N1P2", "N1P3") or r.get("fallback"))
            and int(r.get("max_tokens_rerun", 0)) < a.max_tokens
            and (not a.conditions or r.get("condition") in a.conditions)]
    print(f"{len(todo)} rows of {', '.join(specs)} without a parsable answer out of {len(rows)}", flush=True)
    if not todo:
        return
    kb = load_json(cfg["kb"])
    items = {i.id: i for i in read_jsonl(cfg["benchmark"])}
    ctx = ContextBuilder(kb, budget_tokens=int(cfg.get("budget_tokens", 1500)),
                         modules=dict(ABLATIONS[cfg.get("ablation", "+cognicon")]), encoder=make_encoder(cfg))
    g = cfg.get("gen", {})
    backends = {}
    t0, done = time.time(), 0
    by_model: dict[str, list[int]] = {}
    for k in todo:
        by_model.setdefault(rows[k]["model"], []).append(k)
    for model, ks in by_model.items():
        backend = backends.setdefault(model, make_backend(specs[model]))
        for start in range(0, len(ks), 64):
            chunk = ks[start:start + 64]
            built = []
            for k in chunk:
                r = rows[k]
                cond = {"F1": "B1", "F2": "G2", "N1": "G2", "N2": "G2", "N1R": "G2", "N1P": "G2", "N1P2": "G2", "N1P3": "G2"}.get(r["condition"], r["condition"])
                built.append(ctx.build(cond, items[r["item_id"]]))
            outs = {}
            for system in {b[0] for b in built}:
                idx = [n for n, b in enumerate(built) if b[0] == system]
                gen = backend.generate([built[n][1] for n in idx],
                                       GenConfig(max_tokens=a.max_tokens, temperature=float(g.get("temperature", 0.0)),
                                                 seed=int(g.get("seed", 0)), system=system))
                outs.update(zip(idx, gen))
            for n, k in enumerate(chunk):
                r = rows[k]
                r["raw"] = outs[n]
                r["pred"] = parse_answer(items[r["item_id"]], outs[n])
                r["max_tokens_rerun"] = a.max_tokens
            done += len(chunk)
            print(f"[{model}] {done}/{len(todo)} re-generated, {(time.time() - t0) / 60:.1f} min", flush=True)
    still = sum(1 for k in todo if rows[k]["pred"] is None)
    if a.out:
        text = "".join(json.dumps(rows[k], ensure_ascii=False) + "\n" for k in todo)
        _retry(lambda: Path(a.out).write_text(text, encoding="utf-8"))
        print(f"done: {len(todo) - still} recovered, {still} still without answer -> {a.out} "
              f"({out.name} unchanged)")
        return
    backup = out.with_name(f"{out.stem}.bak-{time.strftime('%Y%m%d-%H%M%S')}.jsonl")
    _retry(lambda: backup.write_text(out.read_text(encoding="utf-8"), encoding="utf-8"))
    text = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    _retry(lambda: out.write_text(text, encoding="utf-8"))
    print(f"done: {len(todo) - still} recovered, {still} still without answer (backup: {backup.name})")


if __name__ == "__main__":
    main()

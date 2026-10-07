"""Experiment runner: models x conditions x items -> results JSONL.

Resumable: rows already present in the output file (same model, condition, item)
are skipped, so long GPU runs can be restarted safely.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import yaml

from .bench.schema import read_jsonl
from .conditions.prompts import ContextBuilder
from .eval.parse import parse_answer
from .kb.loaders import load_json
from .llm.backends import GenConfig, make_backend
from .pipeline.neurosymbolic import NeuroSymbolic

BASE_CONDITIONS = {"B0", "B1", "R1", "R2", "G1", "G2", "G3", "G4", "N1", "N2", "N1R", "N1P", "N1P2"}
ADAPTER_CONDITIONS = {"F1", "F2"}


def config_hash(cfg: dict) -> str:
    return hashlib.sha1(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:10]


def _done(path: Path) -> set[tuple[str, str, str]]:
    if not path.exists():
        return set()
    out = set()
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            out.add((r["model"], r["condition"], r["item_id"]))
    return out


def _append_rows(out_path, rows, attempts: int = 8) -> None:
    """Append JSONL rows, retrying transient OS errors.

    Synced folders (Google Drive for desktop, OneDrive) briefly lock a file while uploading it,
    which Windows reports as ``OSError: [Errno 22] Invalid argument`` or ``PermissionError``.
    """
    text = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    for k in range(attempts):
        try:
            with open(out_path, "a", encoding="utf-8") as fh:
                fh.write(text)
            return
        except OSError as exc:
            if k == attempts - 1:
                raise
            wait = min(2 ** k, 30)
            print(f"  write to {out_path} failed ({exc}); retrying in {wait} s", flush=True)
            time.sleep(wait)


def drop_conditions(out_path: Path, conditions: list[str], models: list[str] | None = None) -> int:
    """Remove result rows of the given conditions (optionally only some models) so they are run again.
    The previous file is kept as <name>.bak-<timestamp>.jsonl."""
    if not out_path.exists():
        return 0
    lines = out_path.read_text(encoding="utf-8").splitlines()
    keep, dropped = [], 0
    for line in lines:
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("condition") in conditions and (not models or r.get("model") in models):
            dropped += 1
        else:
            keep.append(line)
    backup = out_path.with_name(f"{out_path.stem}.bak-{time.strftime('%Y%m%d-%H%M%S')}.jsonl")
    backup.write_text("\n".join(lines) + "\n", encoding="utf-8")
    out_path.write_text("\n".join(keep) + ("\n" if keep else ""), encoding="utf-8")
    return dropped


def _sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def write_manifest(cfg: dict, config_path: str, out_path: Path) -> Path:
    """Record what a run used (docs/analysis_plan.md, section 1): hashes of the KB, the benchmark, the config
    and the source files, and the git tag/commit if available. One entry per invocation, appended."""
    import subprocess

    src = Path(__file__).resolve().parent
    code = hashlib.sha256()
    for f in sorted(src.rglob("*.py")):
        code.update(f.relative_to(src).as_posix().encode() + b"\0" + f.read_bytes())

    def git(*args):
        try:
            return subprocess.run(["git", *args], cwd=src, capture_output=True, text=True, timeout=10,
                                  check=False).stdout.strip()
        except (OSError, subprocess.SubprocessError):  # no git on the machine, or not a repository
            return ""

    entry = {"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "config": config_path, "config_hash": config_hash(cfg),
             "kb_sha256": _sha256(cfg["kb"]), "benchmark_sha256": _sha256(cfg["benchmark"]),
             "code_sha256": code.hexdigest(), "git_commit": git("rev-parse", "HEAD"),
             "git_describe": git("describe", "--tags", "--always", "--dirty"),
             "models": [{k: m.get(k) for k in ("name", "model", "base_url")} for m in cfg["models"]],
             "conditions": cfg["conditions"], "retriever": cfg.get("retriever"), "gen": cfg.get("gen")}
    path = out_path.with_name(out_path.stem + "_manifest.jsonl")
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
    return path


def run(config_path: str, redo: list[str] | None = None) -> Path:
    cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    if redo:
        n = drop_conditions(Path(cfg["output"]), redo)
        print(f"--redo {','.join(redo)}: {n} previous rows removed (backup kept)", flush=True)
    chash = config_hash(cfg)
    kb = load_json(cfg["kb"])
    splits = set(cfg.get("splits", ["test_seen", "test_unseen"]))
    # the contrast subset is balanced over `contrast_over` (default: the run's splits) and then restricted
    # to `splits`, so a dev-only run uses exactly the dev items of the full analysis set
    pool = set(cfg.get("contrast_over", splits)) | splits
    items = [i for i in read_jsonl(cfg["benchmark"]) if i.split in pool]
    if cfg.get("tasks"):
        items = [i for i in items if i.task in set(cfg["tasks"])]
    if cfg.get("subset") == "contrast":  # primary analysis set (bench/contrast.py)
        from .bench.contrast import contrast_subset

        items = contrast_subset(items)
    items = [i for i in items if i.split in splits]
    if cfg.get("limit"):
        # sample whole EN/ES twin groups, not the first N lines (the file is ordered by block)
        import random

        pids = sorted({i.pair_id or i.id for i in items})
        random.Random(int(cfg.get("sample_seed", 0))).shuffle(pids)
        keep, n = set(), 0
        for pid in pids:
            if n >= int(cfg["limit"]):
                break
            keep.add(pid)
            n += sum(1 for i in items if (i.pair_id or i.id) == pid)
        items = [i for i in items if (i.pair_id or i.id) in keep]
    from .conditions.prompts import ABLATIONS

    encoder = None
    rcfg = cfg.get("retriever") or {}
    if rcfg.get("kind") == "dense":  # dense R1/R2 (sentence-transformers, CPU by default)
        from .retrieval import DenseEncoder

        encoder = DenseEncoder(rcfg.get("model", "intfloat/multilingual-e5-base"), rcfg.get("device", "cpu"))
    ctx = ContextBuilder(kb, budget_tokens=int(cfg.get("budget_tokens", 1500)),
                         modules=dict(ABLATIONS[cfg.get("ablation", "+cognicon")]), encoder=encoder)
    g = cfg.get("gen", {})
    out_path = Path(cfg["output"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_manifest(cfg, config_path, out_path)
    done = _done(out_path)
    batch_size = int(cfg.get("batch_size", 64))

    for mspec in cfg["models"]:
        backend = make_backend(mspec)
        mname = mspec.get("name", mspec.get("model", "mock"))
        if cfg.get("ablation"):
            mname += f"@{cfg['ablation']}"
        is_adapter = bool(mspec.get("lora_path"))
        conds = [c for c in cfg["conditions"] if (c in ADAPTER_CONDITIONS) == is_adapter]
        for cond in conds:
            todo = [it for it in items if (mname, cond, it.id) not in done]
            if not todo:
                continue
            t0 = time.time()
            n_done = 0
            print(f"[{mname}] {cond}: {len(todo)} items to run", flush=True)

            def flush(rows, out_path=out_path):
                # rows are appended chunk by chunk, so an interruption loses at most one chunk
                _append_rows(out_path, rows)

            def progress(n, t0=t0, todo=todo, mname=mname, cond=cond):
                el = time.time() - t0
                eta = el / n * (len(todo) - n) if n else 0
                print(f"[{mname}] {cond}: {n}/{len(todo)} ({100 * n / len(todo):.0f} %) "
                      f"elapsed {el / 60:.1f} min, remaining ~{eta / 60:.0f} min", flush=True)

            if cond in ("N1", "N2", "N1R", "N1P", "N1P2"):
                ns = NeuroSymbolic(ctx, backend, verify_loop=(cond == "N2"),
                                   max_retries=int(cfg.get("n2_retries", 2)),
                                   constrained=bool(cfg.get("constrained_decoding", True)),
                                   role_aware=(cond == "N1R"), pinned=(cond == "N1P"),
                                   broad=(cond == "N1P2"))
                workers = int(mspec.get("concurrency", 16))
                for chunk in _chunks(todo, batch_size):
                    rows, fallback_items = [], []
                    for it, res in zip(chunk, ns.run_many(chunk, GenConfig(seed=int(g.get("seed", 0))), workers)):
                        if res.fallback:
                            fallback_items.append((it, res))
                            continue
                        rows.append(_row(it, mname, cond, res.answer, res.query, chash,
                                         trace=res.trace, trace_ok=bool(res.trace) or res.status == "selpref_violation",
                                         attempts=res.attempts, kb_status=res.status))
                    if fallback_items:  # fallback: G2 prompting, flagged
                        built = [ctx.build("G2", it) for it, _ in fallback_items]
                        outs = _generate(backend, built, g)
                        for (it, res), out, b in zip(fallback_items, outs, built):
                            rows.append(_row(it, mname, cond, parse_answer(it, out), out, chash, fallback=True,
                                             attempts=res.attempts, ctx_tokens=b[2].get("ctx_tokens", 0)))
                    flush(rows)
                    n_done += len(chunk)
                    progress(n_done)
            else:
                prompt_cond = {"F1": "B1", "F2": "G2"}.get(cond, cond)
                for chunk in _chunks(todo, batch_size):
                    built = [ctx.build(prompt_cond, it) for it in chunk]
                    outs = _generate(backend, built, g)
                    flush([_row(it, mname, cond, parse_answer(it, out), out, chash,
                                ctx_tokens=b[2].get("ctx_tokens", 0)) for it, out, b in zip(chunk, outs, built)])
                    n_done += len(chunk)
                    progress(n_done)
            print(f"[{mname}] {cond}: done, {n_done} items in {(time.time() - t0) / 60:.1f} min", flush=True)
    return out_path


def _generate(backend, built, g) -> list[str]:
    """Generate for (system, prompt, meta) triples, batching by system prompt (language)."""
    by_sys: dict[str, list[int]] = {}
    for k, b in enumerate(built):
        by_sys.setdefault(b[0], []).append(k)
    outs: list[str] = [""] * len(built)
    for system, idxs in by_sys.items():
        for k, o in zip(idxs, backend.generate([built[k][1] for k in idxs], _gcfg(g, system))):
            outs[k] = o
    return outs


def _gcfg(g: dict, system: str) -> GenConfig:
    return GenConfig(max_tokens=int(g.get("max_tokens", 384)), temperature=float(g.get("temperature", 0.0)),
                     seed=int(g.get("seed", 0)), system=system)


def _chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def _row(it, model, cond, pred, raw, chash, **extra) -> dict:
    return {
        "item_id": it.id, "task": it.task, "lang": it.lang, "split": it.split, "depth": it.depth,
        "distractor": it.distractor, "pair_id": it.pair_id, "gold": it.gold, "pred": pred,
        "model": model, "condition": cond, "raw": raw, "config_hash": chash, **extra,
    }

"""Pull Ollama models with a visible progress line (used by run_pilot_windows.ps1 / spark_pilot.sh).

    python scripts/ollama_pull.py http://192.168.1.112:11434 qwen2.5:7b-instruct-fp16 llama3.1:8b-instruct-fp16
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request


def pull(base: str, model: str) -> None:
    req = urllib.request.Request(f"{base}/api/pull", data=json.dumps({"model": model, "stream": True}).encode(),
                                 headers={"Content-Type": "application/json"})
    last, t0 = -1.0, time.time()
    with urllib.request.urlopen(req, timeout=7200) as resp:
        for line in resp:
            if not line.strip():
                continue
            ev = json.loads(line)
            if "error" in ev:
                raise SystemExit(f"{model}: {ev['error']}")
            total, done = ev.get("total"), ev.get("completed")
            if total and done is not None:
                pct = 100 * done / total
                if pct - last >= 5 or done == total:
                    print(f"  {model}: {pct:5.1f} %  ({done / 1e9:.1f}/{total / 1e9:.1f} GB, "
                          f"{time.time() - t0:.0f} s)", flush=True)
                    last = pct
            elif ev.get("status") and ev["status"] != "success":
                print(f"  {model}: {ev['status']}", flush=True)
    print(f"  {model}: ready ({time.time() - t0:.0f} s)", flush=True)


if __name__ == "__main__":
    base, *models = sys.argv[1:]
    for m in models:
        pull(base.rstrip("/"), m)

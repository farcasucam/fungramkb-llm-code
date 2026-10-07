"""Property-contrastive subset of FGKB-Reason.

A question-only classifier can learn *property priors* ("... is alive" is nearly always "yes")
without looking at the concept or the knowledge. The primary analysis therefore uses a contrast
subset in which, for every (task, queried property), each gold label appears equally often, so the
property alone carries no information about the answer. EN/ES twins stay together.

The property key is recovered from ``pair_id`` (see generate.py / deep.py):
    ent:<x>:<key>:<neg>   hop:<x>:<key>   isa:<x>:<category>   cons:<x>:<key>   selpref:<event>:<x>
    deep:<x>:<key>:<key2>  undet:<x>:<key>  novel:<z>:<key>  exc:<z>:<key>  cf:<a>:<x>:<key>
    cfc:<a>:<x>:<key>      abl:deep:<x>:<key>:<key2>
"""

from __future__ import annotations

import random
from collections import defaultdict

from .schema import Item


def prop_key(item: Item) -> str:
    pid = item.pair_id or item.id
    if "(" in pid:
        return pid[pid.index("("):].rstrip(":")
    kind, _, rest = pid.partition(":")
    if kind == "isa":
        return "isa:" + rest.split(":")[-1]  # the category
    if kind == "selpref":
        return "selpref:" + rest.split(":")[0]  # the event
    return pid


# items whose text has the same shape are balanced together; a definition or scenario prefix is a
# different family (otherwise the prefix itself would predict the label)
FAMILY = {"deep_real": "plain", "undetermined": "plain", "undet_control": "plain", "ablation": "plain",
          "novel": "novel", "exceptions": "exceptions", "counterfactual": "counterfactual"}


def _family(it: Item) -> str:
    return FAMILY.get((it.meta or {}).get("block", ""), it.task)


def contrast_subset(items: list[Item], seed: int = 13, tasks=("deep", "entailment", "multihop", "consistency")) -> list[Item]:
    """Down-sample so that labels are balanced within each (task, property key)."""
    rng = random.Random(seed)
    twins: dict[str, list[Item]] = defaultdict(list)
    for it in items:
        twins[it.pair_id or it.id].append(it)
    groups: dict[tuple[str, str], dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for pid, its in twins.items():
        it = its[0]
        if it.task in tasks:
            groups[(it.task, _family(it), prop_key(it))][it.gold].append(pid)
    keep: set[str] = set()
    for by_label in groups.values():
        if len(by_label) < 2:
            continue
        k = min(len(v) for v in by_label.values())
        for pids in by_label.values():
            pids = sorted(pids)
            rng.shuffle(pids)
            keep.update(pids[:k])
    return [it for it in items if (it.pair_id or it.id) in keep]

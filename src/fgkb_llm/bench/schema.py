"""Benchmark item schema and JSONL I/O."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path

TASKS = ("grounding", "entailment", "multihop", "procedural", "consistency", "deep")

LABELS = {
    "grounding": None,  # option letter
    "entailment": ("entailment", "neutral", "contradiction"),
    "multihop": ("yes", "no"),
    "procedural": None,  # option letter
    "consistency": ("consistent", "inconsistent"),
    "deep": ("yes", "no", "undetermined"),
}


@dataclass
class Item:
    id: str
    task: str
    lang: str
    question: str
    gold: str
    options: list[str] = field(default_factory=list)  # for multiple choice; gold is a letter
    premise: str = ""
    hypothesis: str = ""
    focus_concepts: list[str] = field(default_factory=list)
    depth: int | None = None
    trace: list[list[str]] = field(default_factory=list)  # [[ancestor, strict|default, source], ...]
    distractor: bool = False  # KB contradicts the commonsense prior (e.g. defeasible exception)
    pair_id: str | None = None  # links EN/ES twins and negation/paraphrase pairs
    split: str = "test"  # train | dev | test_seen | test_unseen
    template: str = ""
    meta: dict = field(default_factory=dict)


def write_jsonl(items: Iterable[Item], path: str | Path) -> int:
    n = 0
    with open(path, "w", encoding="utf-8") as fh:
        for it in items:
            fh.write(json.dumps(asdict(it), ensure_ascii=False) + "\n")
            n += 1
    return n


def read_jsonl(path: str | Path) -> list[Item]:
    with open(path, encoding="utf-8") as fh:
        return [Item(**json.loads(line)) for line in fh if line.strip()]

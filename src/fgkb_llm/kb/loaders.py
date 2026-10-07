"""Loaders for FunGramKB data.

The project works on a *canonical JSON* format (documented in docs/DATA_FORMAT.md).
Converting the native FunGramKB export into that format is a one-off task done by
``scripts/convert_export.py``; see docs/PROMPTS.md (P01) because the native export
schema must be inspected first.
"""

from __future__ import annotations

import json
from pathlib import Path

from .model import Concept, Instance, KnowledgeBase, LexicalUnit, Script, ScriptStep

_CONCEPT_KEYS = {"id", "parents", "semantic_type", "meaning_postulate", "thematic_frame", "glosses"}


def load_json(path: str | Path) -> KnowledgeBase:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    kb = KnowledgeBase(version=data.get("version", "unknown"))
    for c in data.get("concepts", []):
        kb.concepts[c["id"]] = Concept(
            id=c["id"],
            parents=list(c.get("parents", [])),
            semantic_type=c["semantic_type"],
            meaning_postulate=c.get("meaning_postulate"),
            thematic_frame=c.get("thematic_frame"),
            glosses=dict(c.get("glosses", {})),
            meta={k: v for k, v in c.items() if k not in _CONCEPT_KEYS},
        )
    for lu in data.get("lexicon", []):
        kb.lexicon.append(LexicalUnit(lemma=lu["lemma"], lang=lu["lang"], pos=lu.get("pos", ""),
                                      concept=lu["concept"], corrupt=bool(lu.get("lemma_corrupt"))))
    for s in data.get("scripts", []):
        kb.scripts[s["id"]] = Script(
            id=s["id"],
            name=s.get("name", {}),
            participants=s.get("participants", []),
            steps=[ScriptStep(order=st["order"], predication=st["predication"], label=st.get("label", {}),
                              event=st.get("event"), evar=st.get("evar")) for st in s.get("steps", [])],
            preconditions=s.get("preconditions", []),
            relations=s.get("relations", []),
            description=s.get("description", ""),
        )
    for i in data.get("instances", []):
        kb.instances[i["id"]] = Instance(**i)
    return kb


def dump_json(kb: KnowledgeBase, path: str | Path) -> None:
    out = {
        "version": kb.version,
        "concepts": [
            {
                "id": c.id,
                "parents": c.parents,
                "semantic_type": c.semantic_type,
                "meaning_postulate": c.meaning_postulate,
                "thematic_frame": c.thematic_frame,
                "glosses": c.glosses,
                **c.meta,
            }
            for c in kb.concepts.values()
        ],
        "lexicon": [{"lemma": lu.lemma, "lang": lu.lang, "pos": lu.pos, "concept": lu.concept,
                     **({"lemma_corrupt": True} if lu.corrupt else {})} for lu in kb.lexicon],
        "scripts": [
            {
                "id": s.id,
                "name": s.name,
                "participants": s.participants,
                "steps": [st.__dict__ for st in s.steps],
                "preconditions": s.preconditions,
                "relations": s.relations,
                "description": s.description,
            }
            for s in kb.scripts.values()
        ],
        "instances": [i.__dict__ for i in kb.instances.values()],
    }
    Path(path).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")


def validate(kb: KnowledgeBase) -> list[str]:
    """Structural checks; returns a list of human-readable problems."""
    problems: list[str] = []
    for c in kb.concepts.values():
        for p in c.parents:
            if p not in kb.concepts:
                problems.append(f"{c.id}: unknown parent {p}")
        if c.semantic_type not in ("entity", "event", "quality"):
            problems.append(f"{c.id}: bad semantic type {c.semantic_type}")
    for lu in kb.lexicon:
        if lu.concept not in kb.concepts:
            problems.append(f"lexical unit {lu.lemma}/{lu.lang}: unknown concept {lu.concept}")
    return problems

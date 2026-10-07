"""Normalise free-text model outputs into task labels."""

from __future__ import annotations

import re

from ..bench.schema import Item

_FINAL = re.compile(r"(?:answer|respuesta)\s*[:：]\s*(.+)", re.IGNORECASE)

SYNONYMS = {
    "entailment": ["entailment", "entails", "implicación", "implica"],
    "contradiction": ["contradiction", "contradicts", "contradicción", "contradice"],
    "neutral": ["neutral", "neither", "ninguna"],
    "undetermined": ["undetermined", "indeterminado", "cannot be determined", "no se puede determinar", "unknown"],
    "yes": ["yes", "sí", "si", "true", "cierto"],
    "no": ["no", "false", "falso"],
    "consistent": ["consistent", "coherente"],
    "inconsistent": ["inconsistent", "incoherente", "not consistent", "no es coherente"],
}

TASK_LABELS = {
    "entailment": ["entailment", "contradiction", "neutral"],
    "multihop": ["yes", "no"],
    "consistency": ["inconsistent", "consistent"],  # order matters: 'inconsistent' contains 'consistent'
    "deep": ["undetermined", "yes", "no"],
}


def _final_segment(text: str) -> str:
    matches = _FINAL.findall(text)
    return matches[-1] if matches else text.strip().splitlines()[-1] if text.strip() else ""


def parse_answer(item: Item, text: str) -> str | None:
    seg = _final_segment(text).strip().lower()
    if item.options:
        m = re.match(r"^\(?([a-z])\)?(?:[\.\):\s]|$)", seg)
        if m and ord(m.group(1)) - 97 < len(item.options):
            return m.group(1).upper()
        for i, opt in enumerate(item.options):
            if opt.lower() in seg:
                return chr(65 + i)
        m = re.search(r"\b([A-D])\b", _final_segment(text))
        return m.group(1) if m else None
    for label in TASK_LABELS.get(item.task, []):
        for syn in SYNONYMS[label]:
            if re.search(rf"(?<![a-záéíóúñ]){re.escape(syn)}(?![a-záéíóúñ])", seg):
                return label
    return None

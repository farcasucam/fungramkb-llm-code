"""Repair Spanish/Italian lemmas whose accented letters were lost in the export ('?cido' -> 'ácido').

Each '?' is replaced by the candidate (á é í ó ú ñ ü à è ì ò ù) that maximises the word
frequency (wordfreq, Zipf scale) of every token in the lemma. Lemmas with no candidate above a
minimum frequency stay flagged as corrupt. Used by convert_export.py.
"""
from __future__ import annotations

import itertools

CANDS = {"es": "áéíóúñü", "it": "àèéìòù"}


def repair(lemma: str, lang: str, min_zipf: float = 1.5) -> str | None:
    from wordfreq import zipf_frequency

    out = []
    for tok in lemma.split(" "):
        if "?" not in tok:
            out.append(tok)
            continue
        n = tok.count("?")
        if n > 3:
            return None
        best, score = None, 0.0
        for combo in itertools.product(CANDS.get(lang, "áéíóú"), repeat=n):
            it = iter(combo)
            cand = "".join(next(it) if ch == "?" else ch for ch in tok)
            s = zipf_frequency(cand.lower(), lang)
            if s > score:
                best, score = cand, s
        if best is None or score < min_zipf:
            return None
        out.append(best)
    return " ".join(out)

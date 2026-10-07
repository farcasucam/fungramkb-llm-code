"""Concept linking: text -> FunGramKB concepts.

Shared by every condition, so differences between conditions come only from the
knowledge supplied. Strategy:

1. longest-match lookup of (multi-word) lemmas from the FunGramKB lexicon, with a
   light suffix-stripping lemmatiser (plug in spaCy via ``lemmatise`` for real data);
2. sense disambiguation for ambiguous lemmas by Lesk-style overlap between the
   sentence and each sense's neighbourhood (gloss, ancestors, postulate fillers);
   an embedding scorer can be passed instead (``scorer``).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from ..kb.model import KnowledgeBase

_TOKEN = re.compile(r"[A-Za-zÀ-ÿ]+(?:-[A-Za-zÀ-ÿ]+)*")


def simple_lemmatise(token: str, lang: str) -> list[str]:
    t = token.lower()
    cands = [t]
    if lang == "en":
        for suf, rep in (("ies", "y"), ("es", ""), ("s", ""), ("ing", ""), ("ed", "")):
            if t.endswith(suf) and len(t) - len(suf) >= 3:
                cands.append(t[: -len(suf)] + rep)
    else:
        if t.endswith("ces") and len(t) > 4:
            cands.append(t[:-3] + "z")  # avestruces -> avestruz
        for suf in ("es", "s"):
            if t.endswith(suf) and len(t) - len(suf) >= 3:
                cands.append(t[: -len(suf)])
        for suf, rep in (("a", "ar"), ("e", "er"), ("an", "ar"), ("en", "er")):
            if t.endswith(suf) and len(t) > 3:
                cands.append(t[: -len(suf)] + rep)
    return cands


@dataclass
class Mention:
    surface: str
    start: int
    end: int
    concept: str
    candidates: list[str]


class ConceptLinker:
    def __init__(self, kb: KnowledgeBase, reasoner=None,
                 lemmatise: Callable[[str, str], list[str]] = simple_lemmatise,
                 scorer: Callable[[str, str], float] | None = None):
        self.kb = kb
        self.reasoner = reasoner
        self.lemmatise = lemmatise
        self.scorer = scorer
        self.index: dict[tuple[str, str], list[str]] = {}
        for lu in kb.lexicon:
            self.index.setdefault((lu.lang, lu.lemma.lower()), []).append(lu.concept)
        self.max_len = max((len(lu.lemma.split()) for lu in kb.lexicon), default=1)

    def _signature(self, concept: str, lang: str) -> set[str]:
        words: set[str] = set()
        c = self.kb.concepts.get(concept)
        if c is None:
            return words
        words |= set(_TOKEN.findall(c.glosses.get(lang, "").lower()))
        related = set(c.parents)
        if self.reasoner is not None:
            related |= {f.prop.filler for f in self.reasoner.facts_by_concept.get(concept, []) if f.prop.filler}
            related |= {f.prop.event for f in self.reasoner.facts_by_concept.get(concept, [])}
        for r in related:
            words |= set(self.kb.label(r, lang).lower().split())
        return words

    def disambiguate(self, candidates: list[str], context: str, lang: str) -> str:
        if len(candidates) == 1:
            return candidates[0]
        if self.scorer is not None:
            return max(candidates, key=lambda c: self.scorer(context, c))
        ctx = {w for tok in _TOKEN.findall(context) for w in self.lemmatise(tok, lang)}
        return max(candidates, key=lambda c: (len(ctx & self._signature(c, lang)), -candidates.index(c)))

    def link(self, text: str, lang: str = "en") -> list[Mention]:
        toks = [(m.group(0), m.start(), m.end()) for m in _TOKEN.finditer(text)]
        out: list[Mention] = []
        i = 0
        while i < len(toks):
            hit = None
            for n in range(min(self.max_len, len(toks) - i), 0, -1):
                span = toks[i:i + n]
                heads = self.lemmatise(span[-1][0], lang)
                prefix = " ".join(t[0].lower() for t in span[:-1])
                for h in heads:
                    key = (lang, f"{prefix} {h}".strip())
                    if key in self.index:
                        hit = (n, span, self.index[key])
                        break
                if hit:
                    break
            if hit:
                n, span, cands = hit
                concept = self.disambiguate(list(dict.fromkeys(cands)), text, lang)
                out.append(Mention(text[span[0][1]:span[-1][2]], span[0][1], span[-1][2], concept, cands))
                i += n
            else:
                i += 1
        return out

    def concepts(self, text: str, lang: str = "en", types: tuple[str, ...] = ("entity", "event", "quality")) -> list[str]:
        seen: list[str] = []
        for m in self.link(text, lang):
            c = self.kb.concepts.get(m.concept)
            if c and c.semantic_type in types and m.concept not in seen:
                seen.append(m.concept)
        return seen

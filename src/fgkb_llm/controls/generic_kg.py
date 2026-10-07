"""Control G3: a generic KG (WordNet / Open Multilingual WordNet) with the same budget as G2.

For each linked lemma we take the first WordNet synset with the matching part of speech and
verbalise, in the item's language where OMW has lemmas:
  * its gloss (English: WordNet glosses are not translated),
  * its hypernym chain ("A bootlegger is a kind of criminal."),
  * up to five part meronyms.
The output is plain sentences, like G1/G2, so the three conditions differ in content, not format.

Corpora: ``wordnet`` and ``omw-2.0`` (``omw-1.4`` for older NLTK), downloaded on first use.
ConceptNet: pass a callable ``conceptnet(lemma, lang) -> list[str]`` (P08).
"""

from __future__ import annotations

from collections.abc import Callable

from ..graph.build import approx_tokens

_POS = {"n": "n", "v": "v", "adj": "a"}
_TPL = {
    "en": {"def": "{w}: {d}.", "isa": "{art} {a} is a kind of {b}.", "isa_v": "To {a} is a way to {b}.",
           "part": "{art} {a} has {b} as a part."},
    "es": {"def": "{w}: {d}.", "isa": "{A} es un tipo de {b}.", "isa_v": "{A} es una forma de {b}.",
           "part": "{A} tiene como parte {b}."},
}


def _fmt(tpl: str, a: str, b: str) -> str:
    art = "An" if a[:1].lower() in "aeiou" else "A"
    return tpl.format(a=a, A=a[:1].upper() + a[1:], b=b, art=art)


_WN = None


def _wordnet():
    """WordNet reader, downloading the corpora on first use."""
    global _WN
    if _WN is not None:
        return _WN
    try:
        import nltk
        from nltk.corpus import wordnet as wn
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("control G3 needs nltk: pip install -e '.[controls]'") from exc
    for res in ("wordnet", "omw-2.0", "omw-1.4"):
        try:
            nltk.data.find(f"corpora/{res}")
        except LookupError:
            nltk.download(res, quiet=True)
    wn.ensure_loaded()
    _WN = wn
    return wn


def _name(syn, lang: str) -> str:
    names = syn.lemma_names("spa") if lang == "es" else syn.lemma_names()
    return (names or syn.lemma_names())[0].replace("_", " ")


def wordnet_context(lemmas: list[tuple[str, str, str]], budget_tokens: int = 1500,
                    conceptnet: Callable[[str, str], list[str]] | None = None, hops: int = 6) -> str:
    """lemmas: (lemma, lang, pos). Spanish lemmas are looked up in the Open Multilingual WordNet."""
    wn = _wordnet()
    lines: list[str] = []
    used = 0

    def add(line: str) -> bool:
        nonlocal used
        if line in lines:
            return True
        cost = approx_tokens(line) + 1
        if used + cost > budget_tokens:
            return False
        lines.append(line)
        used += cost
        return True

    for lemma, lang, pos in lemmas:
        t = _TPL["es" if lang == "es" else "en"]
        wn_lang = "spa" if lang == "es" else "eng"
        syns = wn.synsets(lemma.replace(" ", "_"), pos=_POS.get(pos), lang=wn_lang)
        if not syns:
            continue
        s = syns[0]
        if not add(t["def"].format(w=lemma, d=s.definition())):
            break
        cur, depth = s, 0
        while cur.hypernyms() and depth < hops:
            h = cur.hypernyms()[0]
            a, b = _name(cur, lang), _name(h, lang)
            if not add(_fmt(t["isa_v"] if s.pos() == "v" else t["isa"], a, b)):
                return "\n".join(lines)
            cur, depth = h, depth + 1
        for part in s.part_meronyms()[:5]:
            a, b = _name(s, lang), _name(part, lang)
            add(_fmt(t["part"], a, b))
        if conceptnet is not None:
            for edge in conceptnet(lemma, lang):
                if not add(edge):
                    break
    return "\n".join(lines)

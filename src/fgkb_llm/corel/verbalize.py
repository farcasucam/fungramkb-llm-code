"""Template verbalisation of properties and IS-A links (English and Spanish).

Used by R1 (text RAG), by the benchmark generator and by the LoRA data builder.
Templates are deliberately plain; richer NLG is task P05 in docs/PROMPTS.md.
"""

from __future__ import annotations

from ..kb.model import KnowledgeBase
from .facts import Fact, Prop

_HEDGE = {
    ("en", True): "always", ("en", False): "typically",
    ("es", True): "siempre", ("es", False): "normalmente",
}


def _3sg(verb: str) -> str:
    from .nlg import _en_forms

    return _en_forms(verb)[0]


def _es_3sg(verb: str) -> str:
    from .nlg import _es_3sg as es3

    return es3(verb)


def _filler_label(kb: KnowledgeBase, filler: str, lang: str, quant: str = "") -> str:
    if any(sep in filler for sep in ("|", "^", "&")):
        parts = [p.strip().lstrip("0123456789msip ").strip() for p in filler.replace("^", "|").replace("&", "|").split("|")]
        joiner = " or " if lang == "en" else " o "
        return joiner.join(kb.label(p, lang) for p in parts if p)
    lab = kb.label(filler, lang)
    if quant and (quant in ("m", "s", "i") or (quant.isdigit() and quant != "1")):
        num = "" if not quant.isdigit() else quant + " "
        plural = lab + ("s" if lang == "en" or lab[-1] in "aeiou" else "es")
        return f"{num}{plural}"
    return lab


def subject_phrase(kb: KnowledgeBase, concept: str, lang: str = "en") -> str:
    from .nlg import _es_np

    lab = kb.label(concept, lang)
    if lang == "en":
        return ("an " if lab[0] in "aeiou" else "a ") + lab
    return _es_np(kb, concept)[0] if concept in kb.concepts else "un " + lab


def verbalise_prop(kb: KnowledgeBase, concept: str, prop: Prop, *, strict: bool, negated: bool,
                   lang: str = "en", hedge: bool = True) -> str:
    """Sentence for a property. ``hedge=False`` drops always/typically (used in test
    items, so the wording does not leak whether the knowledge is strict).

    Uses the role-aware generator (nlg.sentence) when the property carries its subject role;
    falls back to the simple template otherwise."""
    from .nlg import sentence as _nlg_sentence

    if prop.subj_role:
        out = _nlg_sentence(kb, concept, prop, negated=negated, lang=lang,
                            hedge=_HEDGE[(lang, strict)] if hedge else None)
        if out is not None:
            return out
    subj = subject_phrase(kb, concept, lang)
    verb = kb.label(prop.event, lang)
    hedge_word = _HEDGE[(lang, strict)] if hedge else ""
    obj = _filler_label(kb, prop.filler, lang, prop.quant) if prop.filler else ""
    if lang == "en":
        v = _3sg(verb)
        if negated:
            base = verb if not verb.startswith("be") else verb.replace("be", "is", 1)
            core = f"{'is not' if verb.startswith('be') else 'does not'} {base.removeprefix('is ').strip() if verb.startswith('be') else base}"
            core = core.replace("is not be ", "is not ")
            sent = f"{subj.capitalize()} {core}"
        elif verb.startswith("be"):
            sent = " ".join(w for w in (subj.capitalize(), "is", hedge_word, verb[3:]) if w)
        else:
            sent = " ".join(w for w in (subj.capitalize(), hedge_word, v) if w)
        if obj:
            prep = {"Location": " in", "Goal": " to", "Origin": " from", "Speed": "", "Instrument": " with"}.get(prop.other_role, "")
            sent += f"{prep} {obj}"
        return sent + "."
    v = _es_3sg(verb)
    sent = " ".join(w for w in (subj.capitalize(), "no" if negated else hedge_word, v) if w)
    if obj:
        prep = {"Location": " en", "Goal": " a", "Origin": " de", "Instrument": " con"}.get(prop.other_role, "")
        sent += f"{prep} {obj}"
    return sent + "."


def verbalise_fact(kb: KnowledgeBase, fact: Fact, lang: str = "en") -> str:
    return verbalise_prop(kb, fact.concept, fact.prop, strict=fact.strict, negated=fact.negated, lang=lang)


def verbalise_isa(kb: KnowledgeBase, child: str, parent: str, lang: str = "en") -> str:
    if lang == "en":
        return f"{subject_phrase(kb, child, 'en').capitalize()} is {subject_phrase(kb, parent, 'en')}."
    return f"{subject_phrase(kb, child, 'es').capitalize()} es {subject_phrase(kb, parent, 'es')}."

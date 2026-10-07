"""P13–P15: minimal proofs, required facts, and the deep-reasoning suite of FGKB-Reason.

Depth (project script v2, §12.1) = number of rule applications in the minimal proof:
  isa-step (one per IS-A edge), postulate application, exception block, filler chaining.

Item blocks produced here (all with EN/ES twins, 3-valued gold from the reasoner):
  deep_real      inherited properties with depth >= 3 and composite (filler-chaining) queries
  novel          pseudoword concepts inserted under real parents (definition given to every condition)
  exceptions     default / exception / exception-of-exception chains built with novel concepts
  counterfactual one ancestor postulate flipped; questions whose gold changes because of it
  undetermined   properties the KB does not settle (open world)
  ablation       evidence-ablation variants: one required fact removed (gold recomputed)

Every item that needs a modified KB carries ``meta["kb_patch"]`` (concept overrides), so the
context builder and the reasoner see exactly the same knowledge.
"""

from __future__ import annotations

import copy
import hashlib
import itertools
import json
import random
from collections import deque

from ..corel.facts import Prop
from ..corel.nlg import relative, sentence
from ..corel.parser import parse
from ..kb.model import Concept, KnowledgeBase, LexicalUnit
from ..reasoner.asp import Answer, Reasoner
from .schema import Item

LANGS = ("en", "es")
Q3 = {
    "en": "Is it true that {h} Answer yes, no or undetermined.",
    "es": "¿Es cierto que {h} Responde sí, no o indeterminado.",
}
DEF = {"en": "{x} is a kind of {y}.", "es": "{x} es un tipo de {y}."}  # x = 'a grolp' / 'un grolp' 
DEF_NEG = {"en": "{x} is a kind of {y}. {neg}", "es": "{x} es un tipo de {y}. {neg}"}
SOMETHING = {"en": "something that", "es": "algo que"}
PREP = {"en": {"Location": " in", "Goal": " to", "Origin": " from", "Instrument": " with", "Means": " with"},
        "es": {"Location": " en", "Goal": " a", "Origin": " de", "Instrument": " con", "Means": " con"}}


# ----------------------------------------------------------------------------------------- proofs
def isa_path(r: Reasoner, x: str, y: str) -> list[tuple[str, str]] | None:
    """Shortest IS-A path x -> y as a list of edges."""
    if x == y:
        return []
    prev = {x: None}
    dq = deque([x])
    while dq:
        c = dq.popleft()
        for p in sorted(r.parents.get(c, ())):
            if p not in prev:
                prev[p] = c
                if p == y:
                    path, n = [], p
                    while prev[n] is not None:
                        path.append((prev[n], n))
                        n = prev[n]
                    return path[::-1]
                dq.append(p)
    return None


def proof(r: Reasoner, x: str, prop: Prop, ans: Answer | None = None) -> dict | None:
    """Minimal proof of the reasoner's verdict on (x, prop)."""
    ans = ans or r.query(x, prop)
    if ans.status not in ("true", "false") or not ans.support:
        return None
    best = None
    for anc, kind, src in ans.support:
        path = isa_path(r, x, anc)
        if path is None:
            continue
        if best is None or len(path) < len(best[0]):
            best = (path, anc, kind, src)
    path, anc, kind, src = best
    steps = [["isa", a, b] for a, b in path] + [["postulate", anc, src, kind]]
    required = [f"isa:{a}>{b}" for a, b in path] + [src]
    types = {"taxonomic"} if path else set()
    types.add("property-inheritance" if path else "property")
    if ans.status == "false":
        overridden = [f for a2 in r.ancestors_or_self(x) - {anc}
                      for f in r.facts_by_concept.get(a2, []) if f.prop.key == prop.key and not f.negated]
        if overridden:
            steps.append(["exception-block", overridden[0].source])
            required.append(overridden[0].source)
            types.add("exception")
    return {"depth": len(steps), "steps": steps, "required": required, "types": sorted(types),
            "label": "yes" if ans.status == "true" else "no", "strict": kind == "strict"}


# ---------------------------------------------------------------------------------------- patches
def apply_patch(kb: KnowledgeBase, patch: dict) -> KnowledgeBase:
    """Return a KB copy with concept overrides: {id: {parents, semantic_type, meaning_postulate, lemmas}}."""
    k = copy.copy(kb)
    k.concepts = dict(kb.concepts)
    k.lexicon = list(kb.lexicon)
    for cid, spec in patch.get("concepts", {}).items():
        old = kb.concepts.get(cid)
        k.concepts[cid] = Concept(
            id=cid, parents=spec.get("parents", old.parents if old else []),
            semantic_type=spec.get("semantic_type", old.semantic_type if old else "entity"),
            meaning_postulate=spec.get("meaning_postulate", old.meaning_postulate if old else None),
            thematic_frame=old.thematic_frame if old else None,
            glosses=old.glosses if old else {}, meta={"provenance": "patch"})
        for lang, lem in spec.get("lemmas", {}).items():
            k.lexicon.append(LexicalUnit(lemma=lem, lang=lang, pos="n", concept=cid))
    k.version = kb.version + "+patch:" + patch_id(patch)
    return k


def patch_id(patch: dict) -> str:
    return hashlib.sha1(json.dumps(patch, sort_keys=True).encode()).hexdigest()[:10]


def drop_predication(mp: str, evar: str) -> str | None:
    """Meaning postulate without the item that contains predication ``evar``."""
    m = parse(mp)
    keep = [it for it in m.items if all(p.evar != evar for p in it.predications)]
    return " ".join(str(it) for it in keep) or None


# --------------------------------------------------------------------------------------- language
def _sentence(kb, x, prop, neg, lang, subject=None):
    return sentence(kb, x, prop, negated=neg, lang=lang, subject=subject)


def _q(sent: str | None, lang: str) -> str | None:
    if not sent:
        return None
    h = sent[0].lower() + sent[1:-1] + "?"
    return Q3[lang].format(h=h)


def _composite(kb, x, p: Prop, f: str, q: Prop, lang: str) -> str | None:
    """'An X <P> something that <Q>' — the filler of P is replaced by a relative clause about it."""
    rel = relative(kb, f, q, lang)
    if rel is None:
        return None
    from ..corel import nlg

    d = nlg.describe(kb, x, Prop(p.event, p.self_role, p.other_role, f, p.quant, p.subj_role), lang=lang)
    if d is None:
        return None
    subj, pred = d
    np_f = nlg._en_np(kb, f, p.quant) if lang == "en" else nlg._es_np(kb, f, p.quant)[0]
    import re

    # the filler NP must be replaced in the predicate, as a whole phrase (never inside the subject)
    pat = re.compile(rf"(?<![\w-]){re.escape(np_f)}(?![\w-])")
    hits = pat.findall(pred)
    if len(hits) != 1:
        return None
    full = f"{subj} {pat.sub(rel, pred, count=1)}"
    return full[0].upper() + full[1:] + "."


PSEUDO_ON = ["bl", "dr", "gr", "pl", "tr", "cl", "br", "fr", "m", "n", "s", "t", "l", "v", "z", "k"]
PSEUDO_NU = ["a", "e", "i", "o", "u"]
PSEUDO_CO = ["l", "n", "r", "s", "t", "m"]


def pseudoword(rng: random.Random, forbidden: set[str]) -> str:
    """CV(C)CV(C) pseudoword pronounceable in English and Spanish, not in either lexicon."""
    while True:
        w = (rng.choice(PSEUDO_ON) + rng.choice(PSEUDO_NU) + rng.choice(PSEUDO_CO) + rng.choice(PSEUDO_ON[8:])
             + rng.choice(PSEUDO_NU) + rng.choice(["", "n", "l", "r"]))
        if w not in forbidden and len(w) >= 5:
            forbidden.add(w)
            return w


# -------------------------------------------------------------------------------------- generator
class DeepSuite:
    def __init__(self, kb: KnowledgeBase, seed: int = 21):
        self.kb = kb
        self.r = Reasoner(kb)
        self.rng = random.Random(seed)
        self._n = itertools.count()
        self.words = {lu.lemma.lower() for lu in kb.lexicon}
        self._emitted: set[str] = set()

    def _id(self, block):
        return f"{block}-{next(self._n):06d}"

    def entities(self):
        return sorted(c.id for c in self.kb.concepts.values()
                      if c.semantic_type == "entity" and not c.id.startswith("#") and self.r.closure(c.id))

    def _item(self, block, lang, q, gold, x, pr, pair, prop=None, **meta):
        if prop is not None:
            meta["prop"] = list(prop.key)  # the queried property, for exact re-derivation
        return Item(id=self._id(block) + f"-{lang}", task="deep", lang=lang, question=q, gold=gold,
                    focus_concepts=[x], depth=pr["depth"] if pr else None,
                    trace=[[str(s) for s in st] for st in (pr["steps"] if pr else [])],
                    distractor="exception" in (pr["types"] if pr else []), pair_id=pair, template=block,
                    meta={"block": block, "required_facts": pr["required"] if pr else [],
                          "reasoning_types": pr["types"] if pr else [], **meta})

    # ---- deep_real: inheritance depth >= 3 and composite chaining --------------------------------
    def deep_real(self, min_depth: int = 3, max_per_concept: int = 6) -> list[Item]:
        out = []
        for x in self.entities():
            clo = self.r.closure(x)
            cands = []
            for p, a in clo.items():
                pr = proof(self.r, x, p, a)
                if pr and pr["depth"] >= min_depth:
                    cands.append(("inherit", p, None, None, pr))
                # composite: filler F of p has its own properties q
                if a.status == "true" and p.filler and p.filler in self.kb.concepts and " " not in p.filler:
                    for q, b in self.r.closure(p.filler).items():
                        prq = proof(self.r, p.filler, q, b)
                        if not prq or q.filler == x:
                            continue
                        pr2 = {"depth": pr["depth"] + prq["depth"] + 1,
                               "steps": pr["steps"] + [["filler-chain", p.filler]] + prq["steps"],
                               "required": pr["required"] + prq["required"],
                               "types": sorted(set(pr["types"]) | set(prq["types"]) | {"filler-chaining"}),
                               "label": prq["label"], "strict": pr["strict"] and prq["strict"]}
                        if pr2["depth"] >= min_depth:
                            cands.append(("composite", p, p.filler, q, pr2))
            self.rng.shuffle(cands)
            for kind, p, f, q, pr in cands[:max_per_concept]:
                pair = f"deep:{x}:{p.key}:{q.key if q else ''}"
                qs = {}
                for lang in LANGS:
                    sent = _sentence(self.kb, x, p, False, lang) if kind == "inherit" else _composite(self.kb, x, p, f, q, lang)
                    qs[lang] = _q(sent, lang)
                if all(qs.values()):
                    for lang in LANGS:
                        out.append(self._item("deep_real", lang, qs[lang], pr["label"], x, pr, pair, kind=kind, prop=(q if q else p)))
        return out

    # ---- undetermined (open world) -----------------------------------------------------------------
    def undetermined(self, per_concept: int = 2) -> list[Item]:
        """Plausible but undecidable: properties of *cousin* concepts (same nearest non-meta
        ancestor) that the KB neither entails nor refutes for x (open world)."""
        out = []
        for x in self.entities():
            known = {p.key for p in self.r.closure(x)}
            anc = [a for a in sorted(self.r.ancestors_or_self(x) - {x}, key=lambda a: self.r.depth(x, a) or 99)
                   if not a.startswith("#")]
            # the shared ancestor must be specific (it has a non-meta parent itself): siblings under a
            # broad top-level class give implausible questions ("a release molests a crime")
            if not anc or not any(not p.startswith("#") for p in self.r.parents.get(anc[0], ())):
                continue
            cousins = [c for c in self.entities() if c != x and anc[0] in self.r.ancestors_or_self(c)]
            pool_props, owner = {}, {}
            for c in cousins:
                for f in self.r.facts_by_concept.get(c, []):
                    if f.prop.key not in known and not f.negated:
                        pool_props[f.prop.key] = f.prop
                        owner[f.prop.key] = c
            pool = list(pool_props)
            self.rng.shuffle(pool)
            for k in pool[:per_concept]:
                p, c = pool_props[k], owner[k]
                pair = f"undet:{x}:{k}"
                qs = {lang: _q(_sentence(self.kb, x, p, False, lang), lang) for lang in LANGS}
                # contrast twin: the same property asked about the cousin that has it (provable)
                prc = proof(self.r, c, p)
                qc = {lang: _q(_sentence(self.kb, c, p, False, lang), lang) for lang in LANGS}
                if all(qs.values()) and all(qc.values()) and prc:
                    ctrl_pair = f"undc:{c}:{k}"
                    new_ctrl = ctrl_pair not in self._emitted  # one control may serve several cousins
                    self._emitted.add(ctrl_pair)
                    for lang in LANGS:
                        out.append(self._item("undetermined", lang, qs[lang], "undetermined", x, None, pair,
                                              contrast_of=ctrl_pair, prop=p))
                        if new_ctrl:
                            out.append(self._item("undet_control", lang, qc[lang], prc["label"], c, prc, ctrl_pair,
                                                  contrast_of=pair, prop=p))
        return out

    # ---- novel concepts and exception chains ----------------------------------------------------------
    def novel(self, n_concepts: int = 120, n_undetermined: int = 2) -> list[Item]:
        out = []
        parents = [e for e in self.entities() if len(self.r.closure(e)) >= 2]
        self.rng.shuffle(parents)
        for y in parents[:n_concepts]:
            w = pseudoword(self.rng, self.words)
            z = f"${w.upper()}_00"
            patch = {"concepts": {z: {"parents": [y], "semantic_type": "entity",
                                      "meaning_postulate": f"+(e1: +BE_00 (x1: {z})Theme (x2: {y})Referent)",
                                      "lemmas": {"en": w, "es": w}}}}
            kb2 = apply_patch(self.kb, patch)
            r2 = self.r.patched(kb2, list(patch["concepts"]))
            for p, a in r2.closure(z).items():
                pr = proof(r2, z, p, a)
                if not pr:
                    continue
                pair = f"novel:{z}:{p.key}"
                qs = {lang: _q(_sentence(kb2, z, p, False, lang, subject=_pseudo_np(w, lang)), lang) for lang in LANGS}
                if not all(qs.values()):
                    continue
                for lang in LANGS:
                    defin = DEF[lang].format(x=_pseudo_np(w, lang).capitalize(), y=_kind_np(kb2, y, lang))
                    out.append(self._item("novel", lang, defin + " " + qs[lang], pr["label"], z, pr, pair,
                                          kb_patch=patch, definition=defin, prop=p))
            # contrast twins: properties that other parents have but y neither has nor lacks; with the
            # same definition the answer is "undetermined", so the property alone does not give it away
            known = {p.key for p in r2.closure(z)}
            others = list({f.prop.key: (f.prop, f.concept) for f in self.r.facts
                           if not f.negated and f.prop.key not in known and f.concept != y}.values())
            self.rng.shuffle(others)
            added = 0
            for p, _src in others:
                if added >= n_undetermined or r2.query(z, p).status != "unknown":
                    continue
                qs = {lang: _q(_sentence(kb2, z, p, False, lang, subject=_pseudo_np(w, lang)), lang) for lang in LANGS}
                if not all(qs.values()):
                    continue
                for lang in LANGS:
                    defin = DEF[lang].format(x=_pseudo_np(w, lang).capitalize(), y=_kind_np(kb2, y, lang))
                    out.append(self._item("novel", lang, defin + " " + qs[lang], "undetermined", z, None,
                                          f"novel:{z}:{p.key}", kb_patch=patch, definition=defin, prop=p))
                added += 1
        return out

    def exceptions(self, n_chains: int = 80) -> list[Item]:
        """y has default P. z: kind of y that does not P (exception). w: kind of z that does P again."""
        out = []
        cands = [(y, f) for y in self.entities() for f in self.r.facts_by_concept.get(y, [])
                 if not f.strict and not f.negated]
        self.rng.shuffle(cands)
        for y, f in cands[:n_chains]:
            wz, ww = pseudoword(self.rng, self.words), pseudoword(self.rng, self.words)
            z, w = f"${wz.upper()}_00", f"${ww.upper()}_00"
            body = _prop_corel(f.prop)
            patch = {"concepts": {
                z: {"parents": [y], "semantic_type": "entity", "lemmas": {"en": wz, "es": wz},
                    "meaning_postulate": f"+(e1: +BE_00 (x1: {z})Theme (x2: {y})Referent) *(e2: n {body})"},
                w: {"parents": [z], "semantic_type": "entity", "lemmas": {"en": ww, "es": ww},
                    "meaning_postulate": f"+(e1: +BE_00 (x1: {w})Theme (x2: {z})Referent) *(e2: {body})"}}}
            kb2 = apply_patch(self.kb, patch)
            r2 = self.r.patched(kb2, list(patch["concepts"]))
            for target, label, nm in ((z, "no", wz), (w, "yes", ww)):
                ans = r2.query(target, f.prop)
                pr = proof(r2, target, f.prop, ans)
                if not pr or pr["label"] != label:
                    continue
                pr["types"] = sorted(set(pr["types"]) | {"exception"})
                pr["depth"] += 1 if target == w else 0  # exception-of-exception: one more override
                pair = f"exc:{target}:{f.prop.key}"
                texts = {}
                for lang in LANGS:
                    nz, nw = _pseudo_np(wz, lang), _pseudo_np(ww, lang)
                    neg_z = _sentence(kb2, z, f.prop, True, lang, subject=nz)
                    pos_w = _sentence(kb2, w, f.prop, False, lang, subject=nw)
                    q = _q(_sentence(kb2, target, f.prop, False, lang, subject=nz if target == z else nw), lang)
                    if not (neg_z and pos_w and q):
                        break
                    # both definitions are always given, whichever concept is asked about, so the
                    # answer cannot be read off the length or shape of the context
                    defin = (DEF_NEG[lang].format(x=nz.capitalize(), y=_kind_np(kb2, y, lang), neg=neg_z)
                             + " " + DEF[lang].format(x=nw.capitalize(), y=wz) + " " + pos_w)
                    texts[lang] = (defin, q)
                if len(texts) < len(LANGS):
                    continue
                for lang in LANGS:
                    defin, q = texts[lang]
                    out.append(self._item("exceptions", lang, defin + " " + q, label, target, pr, pair,
                                          kb_patch=patch, definition=defin, prop=f.prop))
        return out

    # ---- counterfactuals ------------------------------------------------------------------------------
    def counterfactual(self, n: int = 150) -> list[Item]:
        """Flip one positive fact of ancestor A (strict negation); ask descendants inheriting it."""
        out = []
        cands = []
        for a in self.entities():
            kids = [x for x in self.entities() if x != a and a in self.r.ancestors_or_self(x)]
            for f in self.r.facts_by_concept.get(a, []):
                if not f.negated and kids:
                    cands.append((a, f, kids))
        self.rng.shuffle(cands)
        for a, f, kids in cands[:n]:
            mp = self.kb.concepts[a].meaning_postulate
            evar = f.source.split("/")[1]
            kept = drop_predication(mp, evar)
            new_mp = ((kept + " ") if kept else "") + f"+(e99: n {_prop_corel(f.prop)})"
            patch = {"concepts": {a: {"meaning_postulate": new_mp}}}
            r2 = self.r.patched(apply_patch(self.kb, patch), list(patch["concepts"]))
            for x in kids[:3]:
                before, after = self.r.query(x, f.prop), r2.query(x, f.prop)
                pr = proof(r2, x, f.prop, after)
                if before.status != "true" or after.status != "false" or not pr:
                    continue
                pair = f"cf:{a}:{x}:{f.prop.key}"
                texts = {}
                for lang in LANGS:
                    premise = _sentence(self.kb, a, f.prop, True, lang)
                    qq = _q(_sentence(self.kb, x, f.prop, False, lang), lang)
                    if premise and qq:
                        lead = {"en": "In this scenario, ", "es": "En este escenario, "}[lang]
                        texts[lang] = lead + premise[0].lower() + premise[1:] + " " + qq
                if len(texts) < len(LANGS):
                    continue
                for lang in LANGS:
                    out.append(self._item("counterfactual", lang, texts[lang], "no", x, pr, pair, kb_patch=patch,
                                          factual_gold="yes", flipped=f.source, cf_kind="affected", prop=f.prop))
                # control twin: same scenario, a property of x the flip does not touch. Without it the
                # block's label would be predictable from the "In this scenario" framing alone.
                ctrl = [(q, b) for q, b in r2.closure(x).items()
                        if q.key != f.prop.key and b.status in ("true", "false") and self.r.query(x, q).status == b.status]
                self.rng.shuffle(ctrl)
                for q, b in ctrl:
                    prq = proof(r2, x, q, b)
                    if not prq:
                        continue
                    ctexts = {}
                    for lang in LANGS:
                        premise = _sentence(self.kb, a, f.prop, True, lang)
                        qq = _q(_sentence(self.kb, x, q, False, lang), lang)
                        if premise and qq:
                            lead = {"en": "In this scenario, ", "es": "En este escenario, "}[lang]
                            ctexts[lang] = lead + premise[0].lower() + premise[1:] + " " + qq
                    if len(ctexts) < len(LANGS) or f"cfc:{a}:{x}:{q.key}" in self._emitted:
                        continue
                    self._emitted.add(f"cfc:{a}:{x}:{q.key}")
                    for lang in LANGS:
                        out.append(self._item("counterfactual", lang, ctexts[lang], prq["label"], x, prq,
                                              f"cfc:{a}:{x}:{q.key}", kb_patch=patch, factual_gold=prq["label"],
                                              flipped=f.source, cf_kind="control", prop=q))
                    break
        return out

    # ---- evidence ablation ------------------------------------------------------------------------------
    def ablation(self, items: list[Item], n: int = 300) -> list[Item]:
        """For items with required facts, remove one required postulate; recompute gold."""
        out = []
        pool = [i for i in items if i.lang == "en" and i.meta.get("required_facts") and not i.meta.get("kb_patch")
                and i.meta.get("kind") == "inherit"]
        self.rng.shuffle(pool)
        for it in pool[:n]:
            req = [rf for rf in it.meta["required_facts"] if not rf.startswith("isa:")]
            if not req:
                continue
            src = req[0]
            c, evar = src.split("/")
            mp = self.kb.concepts[c].meaning_postulate
            kept = drop_predication(mp, evar)
            patch = {"concepts": {c: {"meaning_postulate": kept}}}
            r2 = self.r.patched(apply_patch(self.kb, patch), list(patch["concepts"]))
            twins = [t for t in items if t.pair_id == it.pair_id]
            x = it.focus_concepts[0]
            prop = next((f.prop for f in self.r.facts_by_concept.get(c, []) if f.source == src), None)
            if prop is None:
                continue
            new = r2.query(x, prop)
            gold = {"true": "yes", "false": "no"}.get(new.status, "undetermined")
            for t in twins:
                out.append(Item(id=t.id.replace("deep_real", "ablation"), task="deep", lang=t.lang, question=t.question,
                                gold=gold, focus_concepts=t.focus_concepts, depth=t.depth, trace=t.trace,
                                pair_id="abl:" + t.pair_id, template="ablation",
                                meta={**t.meta, "block": "ablation", "kb_patch": patch, "removed": src,
                                      "original_gold": t.gold}))
        return out

    def generate(self) -> list[Item]:
        deep = self.deep_real()
        return (deep + self.undetermined() + self.novel() + self.exceptions() + self.counterfactual()
                + self.ablation(deep))


def _pseudo_np(w: str, lang: str) -> str:
    return ("a " if lang == "en" else "un ") + w


def _kind_np(kb, y: str, lang: str) -> str:
    """Bare noun after 'a kind of' / 'un tipo de'."""
    return kb.label(y, lang)


def _prop_corel(p: Prop) -> str:
    other = f" (x2: {p.filler}){p.other_role}" if p.filler and " " not in p.filler else ""
    return f"{p.event} (x1){p.self_role}{other}"

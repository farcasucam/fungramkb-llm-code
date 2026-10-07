"""FGKB-Reason generator: five tasks, English and Spanish twins, gold from the reasoner.

Every item records the reasoner's trace (which ancestor postulate supports the
answer), its inference depth and whether it is a *distractor* (the KB overrides a
default the LLM is likely to assume, e.g. ostriches and flying).

The templates produce stilted language on purpose; paraphrasing with a different
LLM plus re-validation is a separate step (scripts/paraphrase_items.py, P06).
"""

from __future__ import annotations

import itertools
import random
import string

from ..corel.facts import Prop
from ..corel.parser import parse
from ..corel.verbalize import subject_phrase, verbalise_fact, verbalise_prop
from ..kb.model import KnowledgeBase
from ..reasoner.asp import Answer, Reasoner
from .schema import Item

LANGS = ("en", "es")
LETTERS = string.ascii_uppercase

T = {
    "ground_q": {
        "en": "In the sentence «{s}», which meaning does the word '{w}' have?",
        "es": "En la oración «{s}», ¿qué significado tiene la palabra '{w}'?",
    },
    "entail_premise": {"en": "This is {x}.", "es": "Esto es {x}."},
    "entail_q": {
        "en": "Premise: {p}\nHypothesis: {h}\nDoes the premise entail the hypothesis, contradict it, or neither (entailment / contradiction / neutral)?",
        "es": "Premisa: {p}\nHipótesis: {h}\n¿La premisa implica la hipótesis, la contradice o ninguna de las dos (implicación / contradicción / neutral)?",
    },
    "hop_prop_q": {"en": "Is it true that {h} Answer yes or no.", "es": "¿Es cierto que {h} Responde sí o no."},
    "hop_isa_q": {"en": "Is {x} {y}? Answer yes or no.", "es": "¿Es {x} {y}? Responde sí o no."},
    "proc_next_q": {
        "en": "In the situation «{s}», what normally happens right after '{a}'?",
        "es": "En la situación «{s}», ¿qué ocurre normalmente justo después de '{a}'?",
    },
    "proc_order_q": {
        "en": "In the situation «{s}», does '{a}' normally happen before or after '{b}'?",
        "es": "En la situación «{s}», ¿'{a}' ocurre normalmente antes o después de '{b}'?",
    },
    "proc_opts": {"en": ["before", "after"], "es": ["antes", "después"]},
    "cons_q": {
        "en": "Is the following statement consistent with general conceptual knowledge? «{s}» Answer consistent or inconsistent.",
        "es": "¿Es la siguiente afirmación coherente con el conocimiento conceptual general? «{s}» Responde coherente o incoherente.",
    },
}


def _support(ans: Answer) -> list[list[str]]:
    return [list(s) for s in ans.support]


class BenchmarkGenerator:
    def __init__(self, kb: KnowledgeBase, reasoner: Reasoner | None = None, seed: int = 11):
        self.kb = kb
        self.r = reasoner or Reasoner(kb)
        self.rng = random.Random(seed)
        self._n = itertools.count()

    # ---- utilities -------------------------------------------------------------
    def _id(self, task: str) -> str:
        return f"{task}-{next(self._n):06d}"

    def focus_entities(self) -> list[str]:
        return sorted(c.id for c in self.kb.concepts.values()
                      if c.semantic_type == "entity" and c.level != "meta" and self.r.closure(c.id))

    def _depth(self, concept: str, ans: Answer) -> int:
        ds = [self.r.depth(concept, s[0]) for s in ans.support]
        ds = [d for d in ds if d is not None]
        return min(ds) if ds else 0

    def _is_distractor(self, concept: str, prop: Prop, ans: Answer) -> bool:
        """KB says *false* while some ancestor states the property by default."""
        if ans.status != "false":
            return False
        for anc in self.r.ancestors_or_self(concept) - {concept}:
            for f in self.r.facts_by_concept.get(anc, []):
                if f.prop.key == prop.key and not f.negated:
                    return True
        return False

    # ---- T1 grounding / WSD -----------------------------------------------------
    def grounding(self) -> list[Item]:
        items: list[Item] = []
        for lang in LANGS:
            by_lemma: dict[str, list[str]] = {}
            for lu in self.kb.lexicon:
                if lu.lang == lang and lu.pos == "n":
                    by_lemma.setdefault(lu.lemma, []).append(lu.concept)
            for lemma, senses in sorted(by_lemma.items()):
                senses = sorted(c for c in set(senses) if c in self.kb.concepts)
                if len(senses) < 2:
                    continue
                options = [self.kb.concepts[s].glosses.get(lang)
                           or f"{lemma} ({self.kb.label(self.kb.concepts[s].parents[0], lang)})"
                           for s in senses]
                for gi, s in enumerate(senses):
                    facts = self.r.facts_by_concept.get(s, [])
                    if not facts:
                        continue
                    f = facts[0]
                    sent = verbalise_prop(self.kb, s, f.prop, strict=f.strict, negated=f.negated, lang=lang, hedge=False)
                    sent = sent.replace(self.kb.label(s, lang), lemma, 1)
                    order = list(range(len(options)))
                    self.rng.shuffle(order)  # no answer-position bias
                    items.append(Item(
                        id=self._id("grounding") + f"-{lang}", task="grounding", lang=lang,
                        question=T["ground_q"][lang].format(s=sent, w=lemma),
                        options=[options[k] for k in order], gold=LETTERS[order.index(gi)],
                        focus_concepts=[s], depth=0,
                        pair_id=f"ground:{s}:{f.source}", template="ground_v1",
                    ))
        return items

    # ---- T2 entailment ------------------------------------------------------------
    def entailment(self, neutral_per_concept: int = 2) -> list[Item]:
        items: list[Item] = []
        all_props = {f.prop.key: f.prop for f in self.r.facts}
        for x in self.focus_entities():
            clo = self.r.closure(x)
            known = {p.key for p in clo}
            cands = [(p, a) for p, a in clo.items() if a.status in ("true", "false")]
            unknown = [p for k, p in all_props.items() if k not in known]
            self.rng.shuffle(unknown)
            cands += [(p, Answer("unknown")) for p in unknown[:neutral_per_concept]]
            for prop, ans in cands:
                for hyp_neg in (False, True):
                    if ans.status == "unknown":
                        gold = "neutral"
                    else:
                        gold = "entailment" if (ans.status == "true") != hyp_neg else "contradiction"
                    for lang in LANGS:
                        prem = T["entail_premise"][lang].format(x=subject_phrase(self.kb, x, lang))
                        hyp = verbalise_prop(self.kb, x, prop, strict=True, negated=hyp_neg, lang=lang, hedge=False)
                        items.append(Item(
                            id=self._id("entailment") + f"-{lang}", task="entailment", lang=lang,
                            question=T["entail_q"][lang].format(p=prem, h=hyp), premise=prem, hypothesis=hyp,
                            gold=gold, focus_concepts=[x, prop.event] + ([prop.filler] if prop.filler else []),
                            depth=self._depth(x, ans), trace=_support(ans),
                            distractor=self._is_distractor(x, prop, ans),
                            pair_id=f"ent:{x}:{prop.key}:{int(hyp_neg)}", template="entail_v1",
                            meta={"prop": list(prop.key), "hyp_negated": hyp_neg, "kb_status": ans.status},
                        ))
        return items

    # ---- T3 multi-hop ----------------------------------------------------------------
    def multihop(self, max_depth: int = 4) -> list[Item]:
        items: list[Item] = []
        entities = self.focus_entities()
        for x in entities:
            for prop, ans in self.r.closure(x).items():
                if ans.status not in ("true", "false"):
                    continue
                d = self._depth(x, ans)
                if d < 1 or d > max_depth:
                    continue
                for lang in LANGS:
                    h = verbalise_prop(self.kb, x, prop, strict=True, negated=False, lang=lang, hedge=False)
                    h = h[0].lower() + h[1:-1] + "?"
                    items.append(Item(
                        id=self._id("multihop") + f"-{lang}", task="multihop", lang=lang,
                        question=T["hop_prop_q"][lang].format(h=h),
                        gold="yes" if ans.status == "true" else "no",
                        focus_concepts=[x, prop.event], depth=d, trace=_support(ans),
                        distractor=self._is_distractor(x, prop, ans),
                        pair_id=f"hop:{x}:{prop.key}", template="hop_prop_v1",
                    ))
            # taxonomic hops (closed-world over the ontology)
            ancestors = [a for a in self.r.ancestors_or_self(x) - {x} if not a.startswith("#")]
            for a in ancestors:
                d = self.r.depth(x, a)
                if d is None or d < 2 or d > max_depth:
                    continue
                # the negative asks about the SAME category with another entity, so the category word
                # alone does not predict the answer (contrast pair)
                others = [e for e in entities if e != x and not self.r.is_a(e, a) and not self.r.is_a(a, e)]
                neg = self.rng.choice(others) if others else None
                for xx, gold in ((x, "yes"), (neg, "no")):
                    if xx is None:
                        continue
                    for lang in LANGS:
                        items.append(Item(
                            id=self._id("multihop") + f"-{lang}", task="multihop", lang=lang,
                            question=T["hop_isa_q"][lang].format(x=subject_phrase(self.kb, xx, lang), y=subject_phrase(self.kb, a, lang)),
                            gold=gold, focus_concepts=[xx, a], depth=d if gold == "yes" else None,
                            pair_id=f"isa:{xx}:{a}", template="hop_isa_v1",
                        ))
        return items

    # ---- T4 procedural (Cognicon) ---------------------------------------------------
    def _step_label(self, st, lang: str) -> str:
        """Label from the script or, for exported scripts, from the step predication."""
        if st.label.get(lang):
            return st.label[lang]
        try:
            pred = parse("+" + st.predication.lstrip("+*")).items[0].predications[0]
        except ValueError:
            return ""
        verb = self.kb.label(pred.event, lang) if self.kb.lemmas(pred.event, lang) else ""
        objs = [c for p in pred.participants if p.role in ("Theme", "Referent", "Goal")
                for c in p.filler_concepts() if self.kb.lemmas(c, lang) and c != "+HUMAN_00"]
        return (verb + (" " + self.kb.label(objs[0], lang) if objs else "")).strip()

    def procedural(self) -> list[Item]:
        items: list[Item] = []
        for sc in self.kb.scripts.values():
            steps = sorted(sc.steps, key=lambda s: s.order)
            for st in steps:
                for lang in LANGS:
                    st.label.setdefault(lang, self._step_label(st, lang))
            # drop unlabeled and duplicate-label steps (they cannot be asked about unambiguously)
            seen, kept = set(), []
            for st in steps:
                key = st.label.get("en")
                if key and st.label.get("es") and key not in seen:
                    seen.add(key)
                    kept.append(st)
            steps = kept
            if len(steps) < 3:
                continue
            for lang in LANGS:
                name = sc.name.get(lang, sc.id)
                for i, st in enumerate(steps[:-1]):
                    gold_step = steps[i + 1]
                    distract = [s for s in steps if s not in (st, gold_step)]
                    self.rng.shuffle(distract)
                    opts = [gold_step] + distract[:3]
                    self.rng.shuffle(opts)
                    items.append(Item(
                        id=self._id("procedural") + f"-{lang}", task="procedural", lang=lang,
                        question=T["proc_next_q"][lang].format(s=name, a=st.label.get(lang, "")),
                        options=[o.label.get(lang, "") for o in opts], gold=LETTERS[opts.index(gold_step)],
                        focus_concepts=[sc.id], depth=1, pair_id=f"next:{sc.id}:{st.order}", template="proc_next_v1",
                    ))
                for a, b in itertools.combinations(steps, 2):
                    for first, second in ((a, b), (b, a)):
                        gold = "A" if first.order < second.order else "B"
                        items.append(Item(
                            id=self._id("procedural") + f"-{lang}", task="procedural", lang=lang,
                            question=T["proc_order_q"][lang].format(s=name, a=first.label.get(lang, ""), b=second.label.get(lang, "")),
                            options=T["proc_opts"][lang], gold=gold, focus_concepts=[sc.id],
                            depth=abs(first.order - second.order),
                            pair_id=f"order:{sc.id}:{first.order}:{second.order}", template="proc_order_v1",
                        ))
        return items

    # ---- T5 consistency ---------------------------------------------------------------
    def consistency(self) -> list[Item]:
        items: list[Item] = []
        # (a) property assertions in both polarities
        for x in self.focus_entities():
            for prop, ans in self.r.closure(x).items():
                for neg in (False, True):
                    verdict = self.r.check_assertion(x, prop, negated=neg)
                    gold = "inconsistent" if verdict == "inconsistent" else "consistent"
                    for lang in LANGS:
                        s = verbalise_prop(self.kb, x, prop, strict=True, negated=neg, lang=lang, hedge=False)
                        items.append(Item(
                            id=self._id("consistency") + f"-{lang}", task="consistency", lang=lang,
                            question=T["cons_q"][lang].format(s=s), gold=gold,
                            focus_concepts=[x, prop.event], depth=self._depth(x, ans), trace=_support(ans),
                            distractor=self._is_distractor(x, prop, ans) or (ans.status == "true" and not ans.strict and neg),
                            pair_id=f"cons:{x}:{prop.key}:{int(neg)}", template="cons_prop_v1",
                            meta={"negated": neg, "verdict": verdict, "prop": list(prop.key)},
                        ))
        # (b) selection-preference violations from thematic frames
        entities = self.focus_entities()
        for ev in self.kb.by_type("event"):
            if not ev.thematic_frame:
                continue
            frame = parse("+" + ev.thematic_frame)
            agent = [p for p in frame.items[0].predications[0].participants if p.role == "Agent"]
            if not agent or not agent[0].filler_concepts():
                continue
            prefs = agent[0].filler_concepts()
            for y in entities:
                ok = any(self.r.is_a(y, p) for p in prefs)
                for lang in LANGS:
                    s = verbalise_prop(self.kb, y, Prop(ev.id, "Agent"), strict=True, negated=False, lang=lang, hedge=False)
                    items.append(Item(
                        id=self._id("consistency") + f"-{lang}", task="consistency", lang=lang,
                        question=T["cons_q"][lang].format(s=s), gold="consistent" if ok else "inconsistent",
                        focus_concepts=[y, ev.id], depth=None, pair_id=f"selpref:{ev.id}:{y}",
                        template="cons_selpref_v1", meta={"selection_preferences": prefs},
                    ))
        return items

    def generate_all(self) -> list[Item]:
        return self.grounding() + self.entailment() + self.multihop() + self.procedural() + self.consistency()


def balance(items: list[Item], per_task: dict[str, int] | None = None, seed: int = 3) -> list[Item]:
    """Subsample to target counts per task, keeping EN/ES twins together and
    stratifying multi-hop by depth."""
    if not per_task:
        return items
    rng = random.Random(seed)
    out: list[Item] = []
    for task, n in per_task.items():
        pool = [i for i in items if i.task == task]
        pairs: dict[str, list[Item]] = {}
        for it in pool:
            pairs.setdefault(it.pair_id or it.id, []).append(it)
        keys = list(pairs)
        if task in ("multihop", "consistency", "entailment"):
            # stratify by (depth, gold) so labels and depths stay balanced
            by_d: dict = {}
            for k in keys:
                by_d.setdefault((pairs[k][0].depth or 0, pairs[k][0].gold), []).append(k)
            keys = []
            per_d = max(1, n // (2 * max(1, len(by_d))))
            for d, ks in sorted(by_d.items(), key=lambda kv: (kv[0][0], kv[0][1])):
                rng.shuffle(ks)
                keys += ks[:per_d]
        else:
            rng.shuffle(keys)
        chosen = []
        for k in keys:
            if len(chosen) >= n:
                break
            chosen.extend(pairs[k])
        out.extend(chosen[:n] if len(chosen) > n + 1 else chosen)
    return out


def describe(items: list[Item]) -> dict:
    from collections import Counter
    return {
        "n": len(items),
        "by_task": dict(Counter(i.task for i in items)),
        "by_lang": dict(Counter(i.lang for i in items)),
        "by_split": dict(Counter(i.split for i in items)),
        "distractors": sum(i.distractor for i in items),
        "gold": {t: dict(Counter(i.gold for i in items if i.task == t)) for t in {i.task for i in items}},
    }


def example_lines(kb, reasoner, concept: str, lang: str = "en") -> list[str]:
    return [verbalise_fact(kb, f, lang) for f in reasoner.facts_by_concept.get(concept, [])]

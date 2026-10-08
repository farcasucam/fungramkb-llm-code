"""N1 / N2: text -> COREL query -> ASP reasoner -> answer, with a verifiable trace.

N1  one constrained generation of a COREL query predication, then symbolic answer.
N1R N1 with per-event role constraints in the schema and a role-tolerant decision.
N1P "pinned" parser: the subject is restricted to the entities the shared linker finds in the
    interrogative clause, the model fills only subject / event / object / polarity (with concept
    labels shown), and roles are not generated: the decision matches event and filler in the
    subject's closure. Motivated by the pilot error analysis on the dev split (7 Oct 2026).
N1P2 N1P with broadened candidates: a fixed set of relational events (copulas, comprise, do, create, use)
    and every quality concept are always offered, so a paraphrase whose verb or adjective is outside the
    lexicon can still be mapped (dev analysis of the W3 paraphrases, 7 Oct 2026).
N1P3 (exploratory, after the confirmatory run) N1P2 with a deterministic normalisation of the parsed query
    when the reasoner cannot decide it: (1) light-verb / nominalised attribution read as BE_01 with the
    quality ("involve violence", "have a small size"), near-synonymous qualities, and the converse
    predication (the question's subject as the filler); (2) event subsumption through the genus of the
    events' meaning postulates (SNIFF_00 is +ABSORB_00 ...). Same parser and prompts as N1P2.
N2  N1 plus a verification loop: if the query fails validation (syntax, unknown
    concept, wrong semantic type, role not licensed by the thematic frame), the
    error is fed back and the model regenerates (``max_retries``, default 2).

Scope: inference tasks (entailment, multihop, consistency). Grounding and
procedural items fall back to the G2 prompt; the fallback is recorded so the
paper can report N1 coverage separately.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from ..bench.schema import Item
from ..conditions.prompts import SYSTEM, ContextBuilder
from ..corel.facts import CLASSIFY_EVENTS, predication_to_prop
from ..corel.gbnf import (
    json_to_query,
    query_grammar,
    query_schema,
    query_schema_role_aware,
    query_schema_slots,
)
from ..corel.parser import parse, try_parse
from ..llm.backends import Backend, GenConfig

# N1P2: events always offered (copulas and frequent relational events of the deep items)
RELATIONAL_EVENTS = ("+BE_01", "+BE_02", "+COMPRISE_00", "+DO_00", "+CREATE_00", "+USE_00")
# N1P3: verbs that paraphrase an attribution ("X has a small size", "X involves violence", "X happens violently")
ATTRIBUTIVE_EVENTS = ("+BE_01", "+BE_02", "+HAVE_00", "+COMPRISE_00", "+DO_00", "+EXIST_00", "+HAPPEN_00",
                      "+INVOLVE_00", "+CONTAIN_00")
SYMBOLIC_TASKS = {"entailment", "multihop", "consistency", "deep"}

INSTR = {
    "en": (
        "Translate the {what} into ONE COREL query predication about the main concept.\n"
        "Format: (e1: [n] EVENT (x1: SUBJECT)Role [(x2: OTHER)Role])\n"
        "Use 'n' for negation. For 'X is a Y' use +BE_00 with (x1: X)Theme (x2: Y)Referent; for 'X is <quality>' "
        "use +BE_01 with (x1: X)Theme (x2: QUALITY)Attribute.\n"
        "Allowed concepts: {concepts}\nAllowed events: {events}\n"
        "{examples}\n{what_cap}: {text}\nCOREL query:"
    ),
    "es": (
        "Traduce la {what} a UNA predicación de consulta COREL sobre el concepto principal.\n"
        "Formato: (e1: [n] EVENTO (x1: SUJETO)Role [(x2: OTRO)Role])\n"
        "Usa 'n' para la negación. Para 'X es un Y' usa +BE_00 con (x1: X)Theme (x2: Y)Referent; para 'X es <cualidad>' "
        "usa +BE_01 con (x1: X)Theme (x2: CUALIDAD)Attribute.\n"
        "Conceptos permitidos: {concepts}\nEventos permitidos: {events}\n"
        "{examples}\n{what_cap}: {text}\nConsulta COREL:"
    ),
}
JSON_HINT = {
    "en": "\nReturn the query as JSON with the fields negated, event, subject, subject_role, object, object_role "
          "(object and object_role empty if there is no second participant).",
    "es": "\nDevuelve la consulta como JSON con los campos negated, event, subject, subject_role, object, object_role "
          "(object y object_role vacíos si no hay segundo participante).",
}
EXAMPLES = (
    "Examples:\n"
    "A sparrow flies. -> (e1: +FLY_00 (x1: $SPARROW_00)Agent)\n"
    "A dog does not have hair. -> (e1: n +COMPRISE_00 (x1: +DOG_00)Theme (x2: +HAIR_00)Referent)\n"
    "Is a bat an animal? -> (e1: +BE_00 (x1: $BAT_00)Theme (x2: +ANIMAL_00)Referent)\n"
    "Is a sparrow small? -> (e1: +BE_01 (x1: $SPARROW_00)Theme (x2: +SMALL_00)Attribute)"
)


PINNED = {
    "en": (
        "Fill in a query about the question below.\n"
        "subject: the entity the question asks about.\n"
        "event: the concept of the verb; for 'X is <quality>' use +BE_01, for 'X is located in Y' use +BE_02.\n"
        "object: the other participant, place, manner or quality (empty if there is none).\n"
        "negated: true only if the question itself is negative.\n"
        "Examples: 'Is it true that a sparrow is small?' -> subject sparrow, event +BE_01, object small. "
        "'Is it true that a car is driven by a human?' -> subject car, event drive, object human.\n"
        "Subjects: {subjects}\nEvents: {events}\nObjects: {objects}\n"
        "Question: {clause}\nReturn JSON with the fields negated, subject, event, object."
    ),
    "es": (
        "Rellena una consulta sobre la pregunta siguiente.\n"
        "subject: la entidad por la que se pregunta.\n"
        "event: el concepto del verbo; para 'X es <cualidad>' usa +BE_01, para 'X está en Y' usa +BE_02.\n"
        "object: el otro participante, lugar, modo o cualidad (vacío si no hay).\n"
        "negated: true solo si la propia pregunta es negativa.\n"
        "Ejemplos: '¿Es cierto que un gorrión es pequeño?' -> sujeto gorrión, evento +BE_01, objeto pequeño. "
        "'¿Es cierto que un coche es conducido por un humano?' -> sujeto coche, evento conducir, objeto humano.\n"
        "Sujetos: {subjects}\nEventos: {events}\nObjetos: {objects}\n"
        "Pregunta: {clause}\nDevuelve JSON con los campos negated, subject, event, object."
    ),
}
_QUESTION = re.compile(r"[^.?¿!\n]*\?")
_INSTRUCTION = re.compile(r"\s+(?:Answer|Responde)\b.*$", re.DOTALL)


# Grammatical subjects of the questions map to core roles first (Role and Reference Grammar macroroles:
# actor / undergoer), then to obliques; ties keep a stable order.
_CORE_ROLES = ("Agent", "Theme", "Referent", "Attribute", "Experiencer", "Goal", "Location", "Origin",
               "Instrument", "Manner", "Means", "Purpose", "Reason", "Result", "Company", "Scene", "Time",
               "Duration", "Frequency", "Position", "Speed", "Beneficiary", "Condition", "Quantity")


def _role_key(q) -> tuple:
    rank = {r: k for k, r in enumerate(_CORE_ROLES)}
    return (rank.get(q.self_role, len(rank)), rank.get(q.other_role or "", len(rank)), q.self_role, q.other_role or "")


def interrogative_clause(item: Item) -> str:
    """The sentence that asks the question (background sentences of novel / exception /
    counterfactual items precede it); for entailment items, the hypothesis."""
    text = item.hypothesis if item.task == "entailment" else item.question
    text = _INSTRUCTION.sub("", text or "")
    found = _QUESTION.findall(text)
    return (found[-1] if found else text).strip(" ¿?").strip() + ("?" if found else "")


@dataclass
class NSResult:
    answer: str | None
    query: str | None
    attempts: list[dict] = field(default_factory=list)
    trace: list = field(default_factory=list)
    status: str = ""  # reasoner status
    fallback: bool = False
    raw: str = ""


class NeuroSymbolic:
    def __init__(self, ctx: ContextBuilder, backend: Backend, *, verify_loop: bool, max_retries: int = 2,
                 constrained: bool = True, role_aware: bool = False, pinned: bool = False, broad: bool = False,
                 normalise: bool = False, equivalences: dict | None = None):
        self.ctx = ctx
        self.kb = ctx.kb
        self.r = ctx.reasoner
        self.backend = backend
        self.verify_loop = verify_loop
        self.max_retries = max_retries
        self.constrained = constrained
        # N1R: per-event role constraints in the schema + role-tolerant matching in the decision
        # N1P implies the role-tolerant decision: roles are not generated at all
        self.pinned = pinned or broad or normalise
        self.broad = broad or normalise  # N1P2
        self.normalise = normalise  # N1P3
        self.equivalences = equivalences or {}
        self.role_aware = role_aware or self.pinned

    # ---- candidate vocabulary for the grammar ---------------------------------------
    def candidates(self, item: Item) -> tuple[list[str], list[str]]:
        seeds = self.ctx.seeds(item)
        # classification (+BE_00) only for tasks that ask "is X a Y"; deep items never do, and offering it
        # there made the model encode "X is legal" as a classification (pilot, 5 Oct 2026)
        concepts, events = set(), (set() if item.task == "deep" else {"+BE_00"})
        for s in seeds:
            c = self.kb.concepts.get(s)
            if c is None:
                continue
            if c.semantic_type == "event":
                events.add(s)
            else:
                concepts.add(s)
                concepts |= {a for a in self.r.ancestors_or_self(s) if not a.startswith("#")}
                for prop in self.r.closure(s):
                    events.add(prop.event)
                    if prop.filler and prop.filler[0] in "+$" and " " not in prop.filler:
                        concepts.add(prop.filler)
        return sorted(concepts), sorted(events)

    # ---- validation -----------------------------------------------------------------
    def validate(self, text: str) -> tuple[object | None, str | None]:
        mp, err = try_parse("+" + text.strip())
        if err:
            return None, f"syntax error: {err}"
        pred = mp.items[0].predications[0]
        if pred.event in CLASSIFY_EVENTS:
            pass  # classification is handled by the taxonomy, even when the KB has no +BE_00 entry
        elif pred.event not in self.kb:
            return None, f"unknown event {pred.event}"
        elif self.kb.concepts[pred.event].semantic_type != "event":
            return None, f"{pred.event} is not an event"
        subj = [p for p in pred.participants if p.var == "x1"]
        if not subj or not subj[0].filler_concepts():
            return None, "missing subject (x1: CONCEPT)"
        for p in pred.participants:
            for c in p.filler_concepts():
                if c not in self.kb:
                    return None, f"unknown concept {c}"
        frame = self.kb.concepts[pred.event].thematic_frame if pred.event in self.kb else None
        if frame and not self.pinned:
            allowed = {p.role for p in parse("+" + frame).items[0].predications[0].participants}
            # roles attested for this event in meaning postulates are valid too (default frames
            # inherited from metaconcept schemata are sometimes narrower than the postulates)
            allowed |= self._attested_roles().get(pred.event, set())
            bad = [p.role for p in pred.participants if p.var == "x1" and p.role not in allowed]
            if bad:
                return None, f"role {bad[0]} not in the thematic frame of {pred.event} ({', '.join(sorted(allowed))})"
        return pred, None

    def _schema(self, events, concepts) -> dict:
        if not self.role_aware:
            return query_schema(events, concepts)
        roles = {}
        for ev in events:
            rs = set(self._attested_roles().get(ev, set()))
            c = self.kb.concepts.get(ev)
            if c is not None and c.thematic_frame:
                rs |= {p.role for p in parse("+" + c.thematic_frame).items[0].predications[0].participants}
            roles[ev] = rs
        return query_schema_role_aware(events, concepts, roles)

    def _attested_roles(self) -> dict:
        if not hasattr(self, "_roles"):
            self._roles = {}
            for f in self.r.facts:
                self._roles.setdefault(f.prop.event, set()).update(r for r in (f.prop.self_role, f.prop.other_role) if r)
        return self._roles

    # ---- N1P: pinned slots ---------------------------------------------------------
    def _type(self, c: str) -> str:
        con = self.kb.concepts.get(c)
        return con.semantic_type if con is not None else ""

    def _event_forms(self, lang: str) -> dict[str, set[str]]:
        """Inflected forms of every event (base, 3rd person, participles), produced with the same
        morphology the NLG uses to write the questions. The linker's suffix stripping misses
        participles and irregular verbs ('smoked', 'dicho', 'tiene')."""
        from ..corel import nlg

        cache = self.__dict__.setdefault("_ev_forms", {})
        if lang in cache:
            return cache[lang]
        forms: dict[str, set[str]] = {}
        for ev, con in self.kb.concepts.items():
            if con.semantic_type != "event":
                continue
            bases = {lem.lower() for lem in self.kb.lemmas(ev, lang)}
            verb = nlg._verb(self.kb, ev, lang)
            if verb:
                bases.add(verb.lower())
            bases.update(nlg.LIGHT_VERBS.get(ev, {}).get(lang, ()))
            fs = set(bases)
            for b in bases:
                if lang == "en":
                    fs.update(nlg._en_forms(b))
                else:
                    fs.update({nlg._es_3sg(b), nlg._es_3pl(b), nlg._es_pp(b, False), nlg._es_pp(b, True)})
            forms[ev] = {f for f in fs if f}
        cache[lang] = forms
        return forms

    def fuzzy_events(self, clause: str, lang: str) -> list[str]:
        """Events with an inflected form in the clause (whole-word match, multi-word forms allowed)."""
        text = " " + " ".join(re.findall(r"[a-záéíóúñü]+", clause.lower())) + " "
        hits = []
        for ev, fs in self._event_forms(lang).items():
            if any(f" {f} " in text or f" {f}s " in text for f in fs):
                hits.append(ev)
        return hits

    def slots(self, item: Item) -> dict:
        """Candidate subjects, events and objects for N1P, from the interrogative clause only."""
        clause = interrogative_clause(item)
        linked = [c for c in self.ctx.linker.concepts(clause, item.lang) if c in self.kb]
        subjects = [c for c in linked if self._type(c) == "entity"]
        if not subjects:  # nothing linked in the clause: back off to the item's seeds
            subjects = [c for c in self.ctx.seeds(item) if self._type(c) == "entity"]
        cue_events = [c for c in linked if self._type(c) == "event"] + self.fuzzy_events(clause, item.lang)
        objects = [c for c in linked if self._type(c) != "event" and c not in subjects[:1]]
        events = list(cue_events)
        for subj in subjects:
            for prop in self.r.closure(subj):
                events.append(prop.event)
                if prop.filler and prop.filler[0] in "+$" and " " not in prop.filler:
                    objects.append(prop.filler)
        if any(self._type(c) == "quality" for c in objects):
            events.append("+BE_01")
        if self.broad:
            events += [e for e in RELATIONAL_EVENTS if e in self.kb]
            objects += sorted((c for c, con in self.kb.concepts.items()
                               if con.semantic_type == "quality" and not c.startswith("#")),
                              key=lambda c: self.kb.label(c, item.lang))
        uniq = lambda xs: list(dict.fromkeys(x for x in xs if x))
        return {"clause": clause, "subjects": uniq(subjects), "events": uniq(events),
                "objects": uniq(objects), "cue_events": uniq(cue_events)}

    def _pinned_prompt(self, item: Item, sl: dict) -> str:
        lab = lambda c: f"{c} ({self.kb.label(c, item.lang)})"
        # events cued by the clause first, so the model sees the verb's concept at the top
        return PINNED[item.lang].format(subjects=", ".join(map(lab, sl["subjects"])),
                                        events=", ".join(map(lab, sl["events"])),
                                        objects=", ".join(map(lab, sl["objects"])) or "-", clause=sl["clause"])

    def _roles_for(self, subj: str, event: str, obj: str) -> tuple[str, str]:
        """Roles for a slot query: those of a matching postulate in the subject's closure, else the
        event's thematic frame (first two roles), else Theme / Referent. Only used to write a
        well-formed COREL query; the decision is role-tolerant."""
        matches = sorted((q for q in self.r.closure(subj) if q.event == event and q.filler == obj), key=_role_key)
        if matches:
            return matches[0].self_role or "Theme", matches[0].other_role or "Referent"
        con = self.kb.concepts.get(event)
        if con is not None and con.thematic_frame:
            roles = [p.role for p in parse("+" + con.thematic_frame).items[0].predications[0].participants]
            if roles:
                return roles[0], (roles[1] if len(roles) > 1 else "Referent")
        return ("Theme", "Attribute") if event == "+BE_01" else ("Theme", "Referent")

    def slots_to_query(self, obj: dict) -> str:
        subj, event, other = obj["subject"], obj["event"], obj.get("object") or ""
        r0, r1 = self._roles_for(subj, event, other)
        neg = "n " if obj.get("negated") else ""
        q = f"(e1: {neg}{event} (x1: {subj}){r0}"
        return q + (f" (x2: {other}){r1})" if other else ")")

    def selection_ok(self, pred) -> bool:
        frame = self.kb.concepts[pred.event].thematic_frame
        if not frame:
            return True
        fpred = parse("+" + frame).items[0].predications[0]
        subj = next(p for p in pred.participants if p.var == "x1")
        for fp in fpred.participants:
            if fp.role == subj.role and fp.filler_concepts():
                return any(self.r.is_a(subj.filler_concepts()[0], pref) for pref in fp.filler_concepts())
        return True

    # ---- N1P3: normalisation of undecided queries ------------------------------------
    def _genus(self) -> dict[str, str]:
        """Event -> the event of the first predication of its meaning postulate (its genus in COREL),
        e.g. +SNIFF_00 -> +ABSORB_00. Events without a postulate have no genus."""
        if "_genus_map" not in self.__dict__:
            g = {}
            for cid, con in self.kb.concepts.items():
                if con.semantic_type != "event" or not con.meaning_postulate:
                    continue
                mp, err = try_parse(con.meaning_postulate)
                if err or not mp.items or not mp.items[0].predications:
                    continue
                ev = mp.items[0].predications[0].event
                if ev != cid and ev in self.kb.concepts:
                    g[cid] = ev
            self._genus_map = g
        return self._genus_map

    def event_ancestors(self, event: str) -> list[str]:
        out, e, g = [], event, self._genus()
        while e in g and g[e] not in out and g[e] != event:
            e = g[e]
            out.append(e)
        return out

    def _match(self, subj: str, event: str, filler: str):
        """Decide (subj, event, filler) in the subject's closure, role-tolerant, with event subsumption:
        the same event decides either way; a more specific event (whose genus chain reaches ``event``)
        entails the positive; a negated more general event entails the negative."""
        if subj not in self.kb.concepts:
            return None
        closure = self.r.closure(subj)
        cands = sorted((q for q in closure if q.filler == filler and closure[q].status in ("true", "false")),
                       key=_role_key)
        for q in cands:
            if q.event == event:
                return closure[q], "same event"
        for q in cands:
            if closure[q].status == "true" and event in self.event_ancestors(q.event):
                return closure[q], f"subsumption {q.event} < {event}"
        ups = set(self.event_ancestors(event))
        for q in cands:
            if closure[q].status == "false" and q.event in ups:
                return closure[q], f"subsumption {event} < not {q.event}"
        return None

    def normalised(self, subj: str, prop):
        """First decidable reading of an undecided query, in a fixed order, or None."""
        ev, filler = prop.event, prop.filler
        nq = self.equivalences.get("noun->quality", {})
        qq = self.equivalences.get("quality->quality", {})
        readings = [(subj, ev, filler, "query")]
        if filler and self._type(filler) == "entity" and ev in ATTRIBUTIVE_EVENTS:
            readings += [(subj, "+BE_01", q, f"attribution {filler}->{q}") for q in nq.get(filler, [])]
        if filler and self._type(filler) == "quality":
            if ev != "+BE_01" and ev in ATTRIBUTIVE_EVENTS:
                readings.append((subj, "+BE_01", filler, f"attribution {ev}->+BE_01"))
            readings += [(subj, "+BE_01", q, f"quality {filler}~{q}") for q in qq.get(filler, [])]
        if filler and self._type(filler) == "entity":
            readings.append((filler, ev, subj, "converse"))
        for s_, e_, f_, how in readings:
            if not f_:
                continue
            m = self._match(s_, e_, f_)
            if m is not None:
                return m[0], f"{how}; {m[1]}"
        return None

    # ---- decision -------------------------------------------------------------------
    def decide(self, item: Item, pred) -> tuple[str | None, str, list]:
        subj = next(p for p in pred.participants if p.var == "x1").filler_concepts()[0]
        if pred.event in CLASSIFY_EVENTS:
            others = [p for p in pred.participants if p.var != "x1" and p.filler_concepts()]
            if not others:
                return None, "unknown", []
            holds = self.r.is_a(subj, others[0].filler_concepts()[0])
            status = "true" if holds else "false"
            trace = [[subj, "isa", others[0].filler_concepts()[0]]]
            positive = holds != pred.negated
        else:
            prop, neg = predication_to_prop(pred)
            ans = self.r.query(subj, prop)
            if self.role_aware and ans.status == "unknown":
                # role-tolerant reading: same event and same filler, roles mislabelled by the parser
                # deterministic: the subject of the question is read as a core role before an oblique one
                closure = self.r.closure(subj)
                for q in sorted(closure, key=_role_key):
                    if q.event == prop.event and q.filler == prop.filler and closure[q].status in ("true", "false"):
                        ans = closure[q]
                        break
            status, trace = ans.status, [list(s) for s in ans.support]
            if self.normalise and status == "unknown" and item.task == "deep":
                found = self.normalised(subj, prop)
                if found is not None:
                    ans, how = found
                    status, trace = ans.status, [list(s) for s in ans.support] + [["normalised", how, ""]]
            if item.task == "consistency":
                if status == "unknown" and not neg and not self.selection_ok(pred):
                    return "inconsistent", "selpref_violation", trace
                verdict = self.r.check_assertion(subj, prop, negated=neg)
                return ("inconsistent" if verdict == "inconsistent" else "consistent"), status, trace
            if status in ("unknown", "conflict"):
                if item.task == "entailment":
                    return "neutral", status, trace
                if item.task == "deep":
                    return "undetermined", status, trace  # open world: neither entailed nor refuted
                return "no", status, trace
            positive = (status == "true") != neg
        if item.task == "entailment":
            return ("entailment" if positive else "contradiction"), status, trace
        if item.task == "consistency":
            return ("consistent" if positive else "inconsistent"), status, trace
        return ("yes" if positive else "no"), status, trace

    # ---- main -----------------------------------------------------------------------
    def _prompt(self, item: Item, concepts, events, feedback: str | None) -> str:
        lang = item.lang
        if item.task == "entailment":
            what, text = ("hypothesis", item.hypothesis) if lang == "en" else ("hipótesis", item.hypothesis)
        else:
            what, text = ("question", item.question) if lang == "en" else ("pregunta", item.question)
        p = INSTR[lang].format(what=what, what_cap=what.capitalize(), text=text,
                               concepts=", ".join(concepts), events=", ".join(events), examples=EXAMPLES)
        if feedback:
            p += f"\nPrevious attempt was rejected: {feedback}. Produce a corrected query."
        return p

    def _engine_for(self, item: Item) -> NeuroSymbolic:
        sub = self.ctx.for_item(item)
        if sub is self.ctx:
            return self
        # deep item with its own (patched) KB: reason over exactly that KB
        return NeuroSymbolic(sub, self.backend, verify_loop=self.verify_loop, max_retries=self.max_retries,
                             constrained=self.constrained, role_aware=self.role_aware, pinned=self.pinned,
                             broad=self.broad, normalise=self.normalise, equivalences=self.equivalences)

    def _job(self, item: Item, cfg: GenConfig, feedback: str | None = None):
        """Prompt, generation config and parsing context for one query generation."""
        use_json = self.constrained and getattr(self.backend, "grammar_field", "") == "json_schema"
        if self.pinned:
            sl = self.slots(item)
            prompt = self._pinned_prompt(item, sl)
            gcfg = GenConfig(max_tokens=128, temperature=0.0, seed=cfg.seed, system=SYSTEM[item.lang],
                             json_schema=query_schema_slots(sl["subjects"], sl["events"], sl["objects"])
                             if self.constrained else None)
            if feedback:
                prompt += f"\nPrevious attempt was rejected: {feedback}. Produce a corrected query."
            return prompt, gcfg, True, sl
        concepts, events = self.candidates(item)
        gcfg = GenConfig(max_tokens=128 if use_json else 96, temperature=0.0, seed=cfg.seed, system=SYSTEM[item.lang],
                         grammar=query_grammar(events, concepts) if self.constrained and not use_json else None,
                         json_schema=self._schema(events, concepts) if use_json else None)
        prompt = self._prompt(item, concepts, events, feedback) + (JSON_HINT[item.lang] if use_json else "")
        return prompt, gcfg, use_json, None

    def _to_query(self, out: str, use_json: bool) -> str:
        if use_json:
            try:
                obj = json.loads(out)
                out = self.slots_to_query(obj) if self.pinned else json_to_query(obj)
            except (ValueError, KeyError, TypeError, AttributeError):
                pass  # left as is: the validator reports it
        return out.splitlines()[0] if out else out

    def run(self, item: Item, cfg: GenConfig) -> NSResult:
        if item.task not in SYMBOLIC_TASKS:
            return NSResult(answer=None, query=None, fallback=True)
        eng = self._engine_for(item)
        feedback, attempts = None, []
        tries = 1 + (self.max_retries if self.verify_loop else 0)
        for _ in range(tries):
            prompt, gcfg, use_json, _ = eng._job(item, cfg, feedback)
            out = eng._to_query(self.backend.generate([prompt], gcfg)[0].strip(), use_json)
            pred, err = eng.validate(out)
            attempts.append({"query": out, "error": err})
            if err is None:
                answer, status, trace = eng.decide(item, pred)
                return NSResult(answer=answer, query=out, attempts=attempts, trace=trace, status=status, raw=out)
            feedback = err
        return NSResult(answer=None, query=attempts[-1]["query"], attempts=attempts, fallback=True)

    # ---- batched N1 ------------------------------------------------------------------
    def run_many(self, items: list[Item], cfg: GenConfig, workers: int = 16) -> list[NSResult]:
        """N1 over many items with the LLM calls in parallel (the reasoner stays single-threaded).
        Same prompts, constraints and decision as ``run``; N2 (verification loop) stays sequential."""
        if self.verify_loop:
            return [self.run(it, cfg) for it in items]
        from concurrent.futures import ThreadPoolExecutor

        jobs = []  # (engine, item, prompt, gcfg, use_json) or None for non-symbolic tasks
        for it in items:
            if it.task not in SYMBOLIC_TASKS:
                jobs.append(None)
                continue
            eng = self._engine_for(it)
            prompt, gcfg, use_json, _ = eng._job(it, cfg)
            jobs.append((eng, it, prompt, gcfg, use_json))

        def call(job):
            return None if job is None else self.backend.generate([job[2]], job[3])[0].strip()

        with ThreadPoolExecutor(max(1, workers)) as ex:
            outs = list(ex.map(call, jobs))
        results = []
        for job, out in zip(jobs, outs):
            if job is None:
                results.append(NSResult(answer=None, query=None, fallback=True))
                continue
            eng, it, _, _, use_json = job
            out = eng._to_query(out, use_json)
            pred, err = eng.validate(out)
            attempts = [{"query": out, "error": err}]
            if err is None:
                answer, status, trace = eng.decide(it, pred)
                results.append(NSResult(answer=answer, query=out, attempts=attempts, trace=trace, status=status, raw=out))
            else:
                results.append(NSResult(answer=None, query=out, attempts=attempts, fallback=True))
        return results

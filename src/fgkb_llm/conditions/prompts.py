"""Prompt construction for every experimental condition.

    B0 zero-shot          B1 chain of thought
    R1 RAG (NL)           R2 RAG (COREL lines)
    G1 GraphRAG IS-A only G2 GraphRAG full FunGramKB
    G3 GraphRAG WordNet   G4 GraphRAG corrupted KB
    F1 = B1 prompt on a LoRA model         F2 = G2 prompt on a LoRA model
    N1/N2 are handled in ``pipeline.neurosymbolic``.

Every knowledge condition gets the same token budget (``budget_tokens``).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..bench.schema import Item
from ..controls.corrupt import corrupt_postulates
from ..controls.generic_kg import wordnet_context
from ..graph.build import approx_tokens, linearise_subgraph
from ..kb.model import KnowledgeBase
from ..linking.linker import ConceptLinker
from ..reasoner.asp import Reasoner
from ..retrieval.rag import Retriever, build_corpus

CONDITIONS = ("B0", "B1", "R1", "R2", "G1", "G2", "G3", "G4", "F1", "F2", "N1", "N2")

SYSTEM = {
    "en": "You are a careful assistant answering questions about concepts and everyday situations.",
    "es": "Eres un asistente riguroso que responde preguntas sobre conceptos y situaciones cotidianas.",
}
FINAL = {
    "en": "Give only the final answer on the last line as 'Answer: <answer>'.",
    "es": "Da solo la respuesta final en la última línea como 'Answer: <respuesta>'.",
}
COT = {
    "en": "Think step by step, then give the final answer on the last line as 'Answer: <answer>'.",
    "es": "Razona paso a paso y da la respuesta final en la última línea como 'Answer: <respuesta>'.",
}
CTX_HEADER = {
    "en": "Background knowledge (use it when relevant; it may override common assumptions):",
    "es": "Conocimiento de referencia (úsalo cuando sea pertinente; puede contradecir suposiciones habituales):",
}
COREL_GLOSS = (
    "Notation: '+' strict (no exceptions), '*' default (can have exceptions), 'n' negation; "
    "'C IS-A D' taxonomy; 'C +[EVENT as Role (Role2: FILLER)]' C takes part in EVENT with that role."
)


def format_item(item: Item) -> str:
    q = item.question
    if item.options:
        q += "\n" + "\n".join(f"{chr(65 + i)}. {o}" for i, o in enumerate(item.options))
        q += "\n" + ("Answer with the option letter." if item.lang == "en" else "Responde con la letra de la opción.")
    return q


ABLATIONS = {
    # module set used by G2 for the incremental ablation (section 14 of the project script)
    "ontology": {"postulates": False, "frames": False, "cognicon": False},
    "+postulates": {"postulates": True, "frames": False, "cognicon": False},
    "+frames": {"postulates": True, "frames": True, "cognicon": False},
    "+cognicon": {"postulates": True, "frames": True, "cognicon": True},  # = full G2
}


@dataclass
class ContextBuilder:
    kb: KnowledgeBase
    budget_tokens: int = 1500
    modules: dict = field(default_factory=lambda: dict(ABLATIONS["+cognicon"]))
    encoder: object = None  # retrieval.DenseEncoder for dense R1/R2; None = TF-IDF
    reasoner: Reasoner = field(init=False)
    linker: ConceptLinker = field(init=False)

    def __post_init__(self):
        self.reasoner = Reasoner(self.kb)
        self.linker = ConceptLinker(self.kb, self.reasoner)
        self._retr: dict[tuple[str, str], Retriever] = {}
        self._corrupt: Reasoner | None = None

    # lazily built resources
    def retriever(self, style: str, lang: str) -> Retriever:
        key = (style, lang)
        if key not in self._retr:
            self._retr[key] = Retriever(build_corpus(self.reasoner, style, lang), encoder=self.encoder)
        return self._retr[key]

    def corrupt_reasoner(self) -> Reasoner:
        if self._corrupt is None:
            parent = getattr(self, "_parent", None)
            if parent is None:
                self._corrupt = Reasoner(corrupt_postulates(self.kb), mp_isa=False)
            else:
                # G4 for a patched item: the parent's corrupted KB plus only the *new* concepts of the
                # patch (pseudowords). Edits of existing concepts (ablation, counterfactual) are not
                # applied, otherwise G4 would leak the true postulate the corruption replaced.
                from ..bench.deep import apply_patch

                base = parent.corrupt_reasoner()
                new = {c: spec for c, spec in self._patch["concepts"].items() if c not in parent.kb.concepts}
                self._corrupt = (base.patched(apply_patch(base.kb, {"concepts": new}), list(new)) if new else base)
        return self._corrupt

    def seeds(self, item: Item) -> list[str]:
        text = item.question + " " + " ".join(item.options)
        linked = self.linker.concepts(text, item.lang)
        return linked or [c for c in item.focus_concepts if c in self.kb]

    def context(self, cond: str, item: Item) -> str:
        lang, B = item.lang, self.budget_tokens
        if cond == "R1":
            return self.retriever("nl", lang).context(item.question, B)
        if cond == "R2":
            return COREL_GLOSS + "\n" + self.retriever("corel", lang).context(item.question, B - approx_tokens(COREL_GLOSS))
        seeds = self.seeds(item)
        if cond == "G1":
            return linearise_subgraph(self.reasoner, seeds, budget_tokens=B, mode="isa", lang=lang).text
        if cond in ("G2", "F2"):
            return self.full_context(seeds, item, B)
        if cond == "G4":
            return linearise_subgraph(self.corrupt_reasoner(), seeds, budget_tokens=B, mode="full", lang=lang).text
        if cond == "G3":
            lemmas = []
            for c in seeds:
                lab = self.kb.lemmas(c, lang) or [self.kb.label(c, lang)]
                pos = {"entity": "n", "event": "v", "quality": "adj"}[self.kb.concepts[c].semantic_type]
                lemmas.append((lab[0], lang, pos))
            return wordnet_context(lemmas, B)
        return ""

    def full_context(self, seeds: list[str], item: Item, budget: int) -> str:
        """G2: IS-A + postulates, then thematic frames, then matching Cognicon scripts."""
        lang, m = item.lang, self.modules
        q = (item.question + " " + " ".join(item.options)).lower()
        extra: list[str] = []
        if m.get("frames"):
            # only events the question itself mentions (linked seeds); never derived from the gold
            for ev in dict.fromkeys(s for s in seeds if self.kb.concepts[s].semantic_type == "event"):
                fr = self.kb.concepts[ev].thematic_frame
                if fr:
                    extra.append(f"Thematic frame of {self.kb.label(ev, lang)}: {fr}")
        if m.get("cognicon"):
            for sc in self.kb.scripts.values():
                labels = [st.label.get(lang, "").strip() for st in sorted(sc.steps, key=lambda s: s.order)]
                labels = [lab for lab in labels if lab]
                if len(labels) < 2:
                    continue
                name = sc.name.get(lang, "").strip().lower()
                if (len(name) >= 4 and name in q) or any(len(lab) >= 4 and lab.lower() in q for lab in labels):
                    extra.append(f"Script «{sc.name.get(lang, sc.id)}»: {' > '.join(labels)}")
        # IS-A + postulates have priority: extras may use at most 30 % of the budget
        extra_text, cap = "", int(budget * 0.3)
        for line in extra:
            cand = (extra_text + "\n" + line).strip()
            if approx_tokens(cand) > cap:
                break
            extra_text = cand
        main_budget = budget - approx_tokens(extra_text) if extra_text else budget
        main = linearise_subgraph(self.reasoner, seeds, budget_tokens=max(0, main_budget),
                                  mode="full" if m.get("postulates", True) else "isa", lang=lang).text
        return (main + "\n" + extra_text).strip() if extra_text else main

    def for_item(self, item: Item) -> ContextBuilder:
        """Items of the deep suite may carry a KB patch (novel concept, counterfactual, ablation):
        contexts must come from exactly that KB."""
        patch = (item.meta or {}).get("kb_patch")
        if not patch or getattr(self, "_is_patched", False):
            return self
        from ..bench.deep import apply_patch, patch_id

        cache = self.__dict__.setdefault("_patched", {})
        pid = patch_id(patch)
        if pid not in cache:
            child = object.__new__(ContextBuilder)
            child.kb = apply_patch(self.kb, patch)
            child.budget_tokens = self.budget_tokens
            child.modules = self.modules
            child.encoder = self.encoder  # shared, so cached document embeddings are reused
            child.reasoner = self.reasoner.patched(child.kb, list(patch["concepts"]))
            child.linker = ConceptLinker(child.kb, child.reasoner)
            child._retr, child._corrupt = {}, None
            child._is_patched = True
            child._parent, child._patch = self, patch
            cache[pid] = child
        return cache[pid]

    def build(self, cond: str, item: Item) -> tuple[str, str, dict]:
        """Return (system, user_prompt, meta)."""
        cb = self.for_item(item)
        if cb is not self:
            return cb.build(cond, item)
        lang = item.lang
        body = format_item(item)
        if cond in ("B0",):
            return SYSTEM[lang], f"{body}\n\n{FINAL[lang]}", {"ctx_tokens": 0}
        if cond in ("B1", "F1"):
            return SYSTEM[lang], f"{body}\n\n{COT[lang]}", {"ctx_tokens": 0}
        ctx = self.context(cond, item)
        prompt = f"{CTX_HEADER[lang]}\n{ctx}\n\n{body}\n\n{COT[lang]}"
        return SYSTEM[lang], prompt, {"ctx_tokens": approx_tokens(ctx), "seeds": self.seeds(item)}

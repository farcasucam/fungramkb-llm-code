from fgkb_llm.bench.schema import Item
from fgkb_llm.conditions import ContextBuilder
from fgkb_llm.controls import corrupt_postulates
from fgkb_llm.eval import bootstrap_ci, holm, mcnemar_exact, parse_answer
from fgkb_llm.graph import approx_tokens
from fgkb_llm.linking import ConceptLinker


def _it(task, options=()):
    return Item(id="x", task=task, lang="en", question="q", gold="", options=list(options))


def test_parse_answer():
    assert parse_answer(_it("entailment"), "Reasoning...\nAnswer: Contradiction") == "contradiction"
    assert parse_answer(_it("consistency"), "Answer: inconsistent") == "inconsistent"
    assert parse_answer(_it("consistency"), "Respuesta: coherente") == "consistent"
    assert parse_answer(_it("multihop"), "Answer: Sí") == "yes"
    assert parse_answer(_it("grounding", ["financial institution", "river bank"]), "Answer: B") == "B"
    assert parse_answer(_it("grounding", ["financial institution", "river bank"]), "Answer: river bank") == "B"


def test_stats():
    m, lo, hi = bootstrap_ci([True] * 70 + [False] * 30)
    assert lo < m == 0.7 < hi
    b01, b10, p = mcnemar_exact([True] * 50 + [False] * 50, [True] * 90 + [False] * 10)
    assert (b01, b10) == (40, 0) and p < 1e-6
    adj = holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert adj["a"][1] and not adj["b"][1]


def test_corruption_changes_content_not_format(kb):
    bad = corrupt_postulates(kb, seed=1)
    changed = [c for c in kb.concepts if kb.concepts[c].meaning_postulate != bad.concepts[c].meaning_postulate]
    assert changed
    assert all(bad.concepts[c].parents == kb.concepts[c].parents for c in kb.concepts)


def test_linker_disambiguates(kb, reasoner):
    lk = ConceptLinker(kb, reasoner)
    assert lk.concepts("The bank lends money to people.", "en")[0] == "+BANK_00"
    assert "+BANK_01" in lk.concepts("The bank is located in the river valley.", "en")
    assert lk.concepts("Los avestruces corren rápido.", "es")[0] == "$OSTRICH_00"


def test_budget_respected(kb, items):
    ctx = ContextBuilder(kb, budget_tokens=120)
    for cond in ("R1", "R2", "G1", "G2", "G4"):
        for it in items[:30]:
            assert approx_tokens(ctx.context(cond, it)) <= 120 + 5


def test_g2_includes_frames_and_scripts(kb, items):
    from fgkb_llm.conditions.prompts import ABLATIONS

    proc = next(i for i in items if i.task == "procedural" and i.lang == "en")
    full = ContextBuilder(kb).context("G2", proc)
    assert "Script «eating in a restaurant»" in full
    ctx = ContextBuilder(kb, modules=dict(ABLATIONS["ontology"]))
    ent = next(i for i in items if i.task == "entailment" and i.lang == "en" and "ostrich" in i.question)
    assert "never flies" not in ctx.context("G2", ent)
    assert "never flies" in ContextBuilder(kb).context("G2", ent)


def test_kappa():
    from fgkb_llm.eval.agreement import cohen_kappa

    assert cohen_kappa(list("aabb"), list("aabb")) == 1.0
    assert abs(cohen_kappa(list("aabb"), list("abab"))) < 1e-9


def test_dense_retriever_with_fake_encoder(monkeypatch):
    import numpy as np

    from fgkb_llm.retrieval import DenseEncoder
    from fgkb_llm.retrieval.rag import Doc, Retriever

    calls = []

    class FakeModel:
        def encode(self, texts, **kw):
            calls.append(list(texts))
            vocab = ["bird", "fly", "fish", "swim"]
            v = np.array([[float(w in t) for w in vocab] for t in texts]) + 1e-3
            return v / np.linalg.norm(v, axis=1, keepdims=True)

    enc = DenseEncoder("intfloat/multilingual-e5-base")
    monkeypatch.setattr(enc, "_model", lambda: FakeModel())
    docs = [Doc("a fish can swim", "+FISH_00"), Doc("a bird can fly", "+BIRD_00")]
    r = Retriever(docs, encoder=enc)
    assert r.search("can a bird fly?", k=1)[0][0].concept == "+BIRD_00"
    assert calls[0][0].startswith("passage: ") and calls[1][0].startswith("query: ")
    Retriever(docs + [Doc("a bird can swim", "+BIRD_00")], encoder=enc)  # only the new document is embedded
    assert calls[2] == ["passage: a bird can swim"]

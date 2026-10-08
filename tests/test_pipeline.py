"""N1/N2 logic with an *oracle* backend that writes the correct COREL query.

If the oracle does not reach ~100% on the inference tasks, the decision logic,
the validator or the grammar is wrong — independently of any LLM.
"""


from fgkb_llm.conditions import ContextBuilder
from fgkb_llm.corel.gbnf import query_grammar
from fgkb_llm.llm.backends import GenConfig
from fgkb_llm.pipeline import NeuroSymbolic


class Oracle:
    name = "oracle"

    def __init__(self):
        self.next = ""

    def generate(self, prompts, cfg):
        return [self.next for _ in prompts]


def oracle_query(item):
    if item.template in ("entail_v1",):
        ev, r0, r1, fill = item.meta["prop"]
        neg = "n " if item.meta["hyp_negated"] else ""
    elif item.template == "cons_prop_v1":
        ev, r0, r1, fill = item.pair_id.split(":", 2)[2].rsplit(":", 1)[0].strip("()").replace("'", "").split(", ")
        neg = "n " if item.meta["negated"] else ""
    elif item.template == "cons_selpref_v1":
        _, ev, subj = item.pair_id.split(":")
        return f"(e1: {ev} (x1: {subj})Agent)"
    elif item.template == "hop_isa_v1":
        _, x, y = item.pair_id.split(":")
        return f"(e1: +BE_00 (x1: {x})Theme (x2: {y})Referent)"
    else:
        return None
    if any(s in fill for s in "|^&"):
        return None
    subj = item.focus_concepts[0]
    obj = f" (x2: {fill}){r1}" if fill else ""
    return f"(e1: {neg}{ev} (x1: {subj}){r0}{obj})"


def test_oracle_accuracy(kb, items):
    ctx = ContextBuilder(kb)
    oracle = Oracle()
    ns = NeuroSymbolic(ctx, oracle, verify_loop=False)
    n = ok = 0
    for it in items:
        if it.lang != "en":
            continue
        q = oracle_query(it)
        if q is None:
            continue
        oracle.next = q
        res = ns.run(it, GenConfig())
        assert not res.fallback, (it.id, q, res.attempts)
        n += 1
        ok += res.answer == it.gold
    assert n > 100
    assert ok / n > 0.97, ok / n


def test_verify_loop_recovers(kb, items):
    ctx = ContextBuilder(kb)

    class Flaky:
        name = "flaky"
        calls = 0

        def generate(self, prompts, cfg):
            Flaky.calls += 1
            if Flaky.calls == 1:
                return ["(e1: +FLY_00 (x1: $UNICORN_00)Agent)"]  # unknown concept
            return ["(e1: +FLY_00 (x1: $OSTRICH_00)Agent)"]

    it = next(i for i in items if i.lang == "en" and i.task == "entailment" and i.hypothesis == "An ostrich flies.")
    n1 = NeuroSymbolic(ctx, Flaky(), verify_loop=False).run(it, GenConfig())
    assert n1.fallback
    Flaky.calls = 0
    n2 = NeuroSymbolic(ctx, Flaky(), verify_loop=True).run(it, GenConfig())
    assert n2.answer == "contradiction" and len(n2.attempts) == 2 and "unknown concept" in n2.attempts[0]["error"]


def test_grammar_lists_candidates():
    g = query_grammar(["+FLY_00"], ["$OSTRICH_00", "+BIRD_00"])
    line = next(ln for ln in g.splitlines() if ln.startswith("concept ::="))
    assert '"+BIRD_00"' in line and '"$OSTRICH_00"' in line and "+FLY_00" not in line
    assert g.startswith("root ::=")


def test_n1p3_normalises_attribution_converse_and_subsumption(kb):
    """N1P3 (exploratory): undecided queries are re-read as BE_01 attribution, as the converse predication,
    or through the genus of the event; decidable queries are left untouched."""
    from fgkb_llm.conditions import ContextBuilder
    from fgkb_llm.corel.facts import Prop
    from fgkb_llm.pipeline.neurosymbolic import NeuroSymbolic

    ns = NeuroSymbolic(ContextBuilder(kb), None, verify_loop=False, normalise=True,
                       equivalences={"noun->quality": {}, "quality->quality": {}})
    closure = ns.r.closure
    # pick a concept with a decidable BE_01 attribution and a decidable relation to an entity
    attr = rel = None
    for c in kb.concepts:
        for q, a in closure(c).items():
            if a.status == "true" and q.filler and ns._type(q.filler) == "quality" and q.event == "+BE_01":
                attr = attr or (c, q)
            if a.status == "true" and q.filler and ns._type(q.filler) == "entity" and q.event != "+BE_00":
                rel = rel or (c, q)
    if attr:
        c, q = attr
        found = ns.normalised(c, Prop("+HAVE_00", "Theme", "Referent", q.filler))
        assert found and found[0].status == "true" and found[1].startswith("attribution")
    if rel:
        c, q = rel
        found = ns.normalised(q.filler, Prop(q.event, "Theme", "Referent", c))
        assert found is None or found[1].startswith(("converse", "query"))
    ns._genus_map = {"+SPECIFIC_00": "+GENERAL_00"}
    assert ns.event_ancestors("+SPECIFIC_00") == ["+GENERAL_00"] and ns.event_ancestors("+GENERAL_00") == []

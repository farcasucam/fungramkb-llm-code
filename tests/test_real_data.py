"""Tests for the real-export pipeline: converter, COREL extensions, NLG, deep suite, contrast set."""

import importlib.util
import json
from collections import Counter
from pathlib import Path
from typing import ClassVar

import pytest

from fgkb_llm.corel.facts import Prop, extract
from fgkb_llm.corel.parser import parse

ROOT = Path(__file__).resolve().parents[1]


def _load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------------------------------------------ COREL
def test_grammar_extensions_parse():
    # coreferent satellite, negated preference, parenthesised linked predication as filler
    parse("+(e1: +BE_00 (x1: +A_00)Theme (x2: +B_00)Referent) +(e2: +DO_00 (x1)Theme (f1: x1)Scene)")
    parse("*(e1: +EAT_00 (x1)Agent (x2: n +MEAT_00)Theme)")
    parse("+(e1: +KILL_00 (x1)Agent (x2)Theme (f1: ((e2: +PAY_00 (x3)Agent (x1)Goal)))Reason)")


def test_coreferent_variables_share_fillers():
    mp = parse("+(e1: +BE_00 (x1: +BOOTLEGGER_00)Theme (x2: +CRIMINAL_00)Referent) "
               "+(e2: +DO_00 (x1)Theme (x3: +ALCOHOL_00)Referent) +(e3: +SELL_00 (x1)Agent (x3)Theme)")
    isas, facts = extract("+BOOTLEGGER_00", mp)
    assert [(i.child, i.parent) for i in isas] == [("+BOOTLEGGER_00", "+CRIMINAL_00")]
    sell = [f.prop for f in facts if f.prop.event == "+SELL_00"]
    assert sell and sell[0].filler == "+ALCOHOL_00"  # (x3)Theme resolved through e2


def test_disjunctive_classification_is_not_isa():
    mp = parse("+(e1: +BE_00 (x1: +STIMULANT_00)Theme (x2: +DRUG_00 ^ +SUBSTANCE_00)Referent)")
    isas, _ = extract("+STIMULANT_00", mp)
    assert isas == []
    mp = parse("+(e1: +BE_00 (x1: +BOOTLEG_00)Theme (x2: +ALCOHOL_00 & +PRODUCT_00)Referent)")
    assert {i.parent for i in extract("+BOOTLEG_00", mp)[0]} == {"+ALCOHOL_00", "+PRODUCT_00"}


# -------------------------------------------------------------------------------------------- NLG
def test_nlg_polarity_and_hedges(kb):
    from fgkb_llm.corel.nlg import sentence

    fly = Prop("+FLY_00", "Agent", subj_role="Agent")
    assert sentence(kb, "$OSTRICH_00", fly, negated=True, lang="en", hedge="always") == "An ostrich never flies."
    assert sentence(kb, "$OSTRICH_00", fly, negated=True, lang="en", hedge="typically") == \
        "An ostrich typically does not fly."
    assert sentence(kb, "+BIRD_00", fly, lang="en", hedge="typically") == "A bird typically flies."
    es = sentence(kb, "$OSTRICH_00", fly, negated=True, lang="es", hedge="siempre")
    assert es == "Un avestruz nunca vuela."
    assert "normalmente no vuela" in sentence(kb, "$OSTRICH_00", fly, negated=True, lang="es", hedge="normalmente")


def test_nlg_rejects_empty_light_verbs_and_copula_passives(kb):
    from fgkb_llm.corel.nlg import sentence

    assert sentence(kb, "+BIRD_00", Prop("+DO_00", "Theme", subj_role="Theme"), lang="en") is None
    assert sentence(kb, "+BIRD_00", Prop("+BE_01", "Attribute", "Theme", "+ANIMAL_00", subj_role="Theme"),
                    lang="en") is None


def test_spanish_contractions():
    from fgkb_llm.corel.nlg import _es_contract

    assert _es_contract("Se dedica a el cibercrimen y habla de el juez.") == "Se dedica al cibercrimen y habla del juez."


# ------------------------------------------------------------------------------------- deep suite
@pytest.fixture(scope="module")
def deep_items(kb):
    from fgkb_llm.bench.deep import DeepSuite

    return DeepSuite(kb, seed=1).generate()


def test_deep_blocks_and_labels(deep_items):
    blocks = Counter(i.meta["block"] for i in deep_items)
    for b in ("deep_real", "novel", "exceptions", "counterfactual", "ablation", "undetermined", "undet_control"):
        assert blocks[b] > 0, b
    # no block is label-constant once its contrast twins are counted (counterfactual, novel)
    cf = Counter(i.gold for i in deep_items if i.meta["block"] == "counterfactual")
    assert len(cf) >= 2
    nv = Counter(i.gold for i in deep_items if i.meta["block"] == "novel")
    assert "undetermined" in nv and "yes" in nv
    # EN/ES twins
    by_pair = Counter(i.pair_id for i in deep_items)
    assert all(n % 2 == 0 for n in by_pair.values())


def test_deep_gold_rederivation(kb, deep_items):
    from fgkb_llm.bench.deep import apply_patch
    from fgkb_llm.reasoner.asp import Reasoner

    base = Reasoner(kb)
    lab = {"true": "yes", "false": "no"}
    n = 0
    for it in deep_items:
        if it.lang != "en" or not it.meta.get("prop") or it.meta.get("kind") == "composite":
            continue
        r = base
        if it.meta.get("kb_patch"):
            p = it.meta["kb_patch"]
            r = base.patched(apply_patch(kb, p), list(p["concepts"]))
        got = lab.get(r.query(it.focus_concepts[0], Prop(*it.meta["prop"])).status, "undetermined")
        assert got == it.gold, it.id
        n += 1
    assert n > 20


def test_exceptions_always_show_both_definitions(deep_items):
    exc = [i for i in deep_items if i.meta["block"] == "exceptions" and i.lang == "en"]
    assert exc and all(i.question.count("is a kind of") == 2 for i in exc)


def test_patched_context_contains_pseudoword(kb, deep_items):
    from fgkb_llm.conditions.prompts import ContextBuilder

    cb = ContextBuilder(kb, budget_tokens=400)
    it = next(i for i in deep_items if i.meta["block"] == "novel" and i.lang == "en" and i.gold == "yes")
    word = it.question.split()[1]
    child = cb.for_item(it)
    assert child is not cb and child.for_item(it) is child  # cached, no recursion
    assert word in child.context("G2", it)
    assert word not in cb.context("G2", it)


def test_contrast_subset_balances_property_labels(deep_items):
    from fgkb_llm.bench.contrast import _family, contrast_subset, prop_key

    sub = contrast_subset(deep_items)
    assert sub
    groups = {}
    for it in sub:
        if it.lang == "en":
            groups.setdefault((_family(it), prop_key(it)), Counter())[it.gold] += 1
    for counts in groups.values():
        assert len(counts) >= 2
    pairs = Counter(i.pair_id for i in sub)
    assert all(n == 2 for n in pairs.values())  # twins kept together


# ------------------------------------------------------------------------------------- converter
def _write(path, rows):
    path.write_text("\n".join("\t".join(r) for r in rows) + "\n", encoding="latin-1")


def test_convert_export_minimal(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    raw.mkdir()
    _write(raw / "concept.tsv", [
        ["D", "+ANIMAL_00", "", "sp", "A living being.", "#SELF_CONNECTED_OBJECT", "#ENTITY"],
        ["D", "+BIRD_00", "", "+(e1: +BE_00 (x1: +BIRD_00)Theme (x2: +ANIMAL_00)Referent)  *(e2: +FLY_00 (x1)Agent)",
         "", "#SELF_CONNECTED_OBJECT", "#ENTITY"],
        ["D", "+FLY_00", "", "", "", "#MOTION", "#EVENT"],
    ])
    _write(raw / "hypernym.tsv", [["concept1", "concept2"], ["+BIRD_00", "+ANIMAL_00"],
                                  ["+ANIMAL_00", "#SELF_CONNECTED_OBJECT"], ["#SELF_CONNECTED_OBJECT", "#ENTITY"],
                                  ["+FLY_00", "#MOTION"], ["#MOTION", "#EVENT"]])
    _write(raw / "thematic_schemata.tsv", [["#MOTION", "(x)Agent (x)Theme [x]Goal"]])
    _write(raw / "word.tsv", [["bird", "01", "ENG", "+BIRD_00", "n"], ["p?jaro", "01", "SPA", "+BIRD_00", "n"],
                              ["fly", "01", "ENG", "+FLY_00", "v"]])
    (raw / "cognicon.tsv").write_text(
        '@FLYING_SOUTH_00\t"+(e1: +FLY_00 (x1: +BIRD_00)Agent)\n+(e2: +FLY_00 (x1)Agent)"\te1 -> e2 [Before]\tD\t0\tdesc\n',
        encoding="latin-1")
    conv = _load_script("convert_export")
    monkeypatch.setattr(conv, "repair", lambda lemma, lang: "pájaro" if lemma == "p?jaro" else None, raising=False)
    data = conv.convert(raw, tmp_path / "out.json")
    cs = {c["id"]: c for c in data["concepts"]}
    assert cs["+ANIMAL_00"]["meaning_postulate"] is None and cs["+ANIMAL_00"].get("semantic_primitive")
    assert cs["+FLY_00"]["semantic_type"] == "event"
    assert cs["+FLY_00"]["thematic_frame"] == "(e1: +FLY_00 (x1)Agent (x2)Theme (x3)Goal)"
    assert any(lu["lemma"] == "pájaro" and lu.get("lemma_repaired_from") == "p?jaro" for lu in data["lexicon"])
    sc = data["scripts"][0]
    assert [s["evar"] for s in sc["steps"]] == ["e1", "e2"] and sc["steps"][0]["event"] == "+FLY_00"
    json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))


def test_repair_lemmas_restores_accents():
    pytest.importorskip("wordfreq")
    rep = _load_script("repair_lemmas")
    assert rep.repair("p?jaro", "es") == "pájaro"
    assert rep.repair("cami?n", "es") == "camión"


# ------------------------------------------------------------------------------------ pilot analysis
def test_pilot_analysis_detects_a_known_effect(deep_items):
    """Synthetic results with G2 = 0.85 and B1 = 0.55 accuracy: H1 must be detected, Holm applied."""
    import random

    pa = _load_script("pilot_analysis")
    rng = random.Random(0)
    labels = ["yes", "no", "undetermined"]
    rows = []
    for it in deep_items:
        for cond, acc in (("B1", 0.55), ("G1", 0.6), ("G2", 0.85), ("G4", 0.5)):
            pred = it.gold if rng.random() < acc else rng.choice([x for x in labels if x != it.gold])
            rows.append({"item_id": it.id, "model": "sim", "condition": cond, "pred": pred, "gold": it.gold})
    res = pa.analyse(rows, deep_items)["sim"]
    h1 = res["tests"]["H1 G2>B1"]
    assert h1["diff"] > 0.15 and h1["p_cluster_t"] < 0.001
    assert res["tests"]["G2>G4"]["p_holm"] < 0.01
    assert 0 <= res["diagnostics"]["G2"]["evidence_sensitivity"] <= 1


def test_n1_oracle_on_deep_items(kb, deep_items):
    """N1 with an oracle parser must reproduce the gold on single-property deep items, including
    patched KBs (novel, exceptions, counterfactual, ablation) and 'undetermined'."""
    from fgkb_llm.conditions import ContextBuilder
    from fgkb_llm.llm.backends import GenConfig
    from fgkb_llm.pipeline import NeuroSymbolic

    class Oracle:
        name = "oracle"
        next = ""

        def generate(self, prompts, cfg):
            return [self.next for _ in prompts]

    oracle = Oracle()
    ns = NeuroSymbolic(ContextBuilder(kb), oracle, verify_loop=False, constrained=False)
    n = ok = 0
    for it in deep_items:
        if it.lang != "en" or it.meta.get("kind") == "composite" or not it.meta.get("prop"):
            continue
        ev, r0, r1, fill = it.meta["prop"]
        if any(s in fill for s in "|^&"):
            continue
        obj = f" (x2: {fill}){r1}" if fill else ""
        oracle.next = f"(e1: {ev} (x1: {it.focus_concepts[0]}){r0}{obj})"
        res = ns.run(it, GenConfig())
        n += 1
        ok += res.answer == it.gold
    assert n > 30
    assert ok / n > 0.97, ok / n


def test_n1_json_schema_route(kb, deep_items):
    """Servers without GBNF (Ollama): N1 constrained by a JSON schema, converted back to COREL."""
    import json as _json

    from fgkb_llm.conditions import ContextBuilder
    from fgkb_llm.llm.backends import GenConfig
    from fgkb_llm.pipeline import NeuroSymbolic

    class JsonOracle:
        name, grammar_field = "json-oracle", "json_schema"
        payload: ClassVar[dict] = {}
        schemas: ClassVar[list] = []

        def generate(self, prompts, cfg):
            assert cfg.json_schema and cfg.grammar is None
            self.schemas.append(cfg.json_schema)
            return [_json.dumps(self.payload) for _ in prompts]

    o = JsonOracle()
    ns = NeuroSymbolic(ContextBuilder(kb), o, verify_loop=False, constrained=True)
    n = ok = 0
    for it in deep_items:
        if it.lang != "en" or it.meta.get("kind") == "composite" or not it.meta.get("prop"):
            continue
        ev, r0, r1, fill = it.meta["prop"]
        if any(s in fill for s in "|^&"):
            continue
        o.payload = {"negated": False, "event": ev, "subject": it.focus_concepts[0], "subject_role": r0,
                     "object": fill, "object_role": r1 if fill else ""}
        n += 1
        ok += ns.run(it, GenConfig()).answer == it.gold
    assert n > 30 and ok / n > 0.97, ok / n
    s = o.schemas[0]
    assert s["properties"]["event"]["enum"] and s["required"]


def test_n1r_role_aware_schema_and_tolerant_decision(kb):
    """N1R: one schema branch per event with its attested roles; a query with the right event and
    filler but a mislabelled role is still decided from the KB."""
    from fgkb_llm.conditions import ContextBuilder
    from fgkb_llm.corel.parser import parse as _parse
    from fgkb_llm.pipeline import NeuroSymbolic

    ns = NeuroSymbolic(ContextBuilder(kb), backend=None, verify_loop=False, role_aware=True)
    schema = ns._schema(["+FLY_00", "+COMPRISE_00"], ["$OSTRICH_00", "+FEATHER_00"])
    assert "anyOf" in schema and len(schema["anyOf"]) == 2
    fact = next(f for f in ns.r.facts if f.prop.filler)
    wrong = "Instrument" if fact.prop.other_role != "Instrument" else "Location"
    q = f"(e1: {fact.prop.event} (x1: {fact.concept}){fact.prop.self_role} (x2: {fact.prop.filler}){wrong})"
    pred = _parse("+" + q).items[0].predications[0]

    class It:
        task, lang = "deep", "en"

    _, status, _ = ns.decide(It(), pred)
    assert status in ("true", "false")
    strict = NeuroSymbolic(ContextBuilder(kb), backend=None, verify_loop=False, role_aware=False)
    assert strict.decide(It(), pred)[1] == "unknown"


def test_n1p_interrogative_clause_and_slots(kb, deep_items):
    """N1P: the subject candidates come from the question sentence, not from background sentences."""
    from fgkb_llm.bench.schema import Item
    from fgkb_llm.conditions import ContextBuilder
    from fgkb_llm.pipeline import NeuroSymbolic
    from fgkb_llm.pipeline.neurosymbolic import interrogative_clause

    it = next(i for i in deep_items if i.lang == "en" and i.meta.get("block") == "novel" and ". " in i.question)
    clause = interrogative_clause(it)
    assert clause.endswith("?") and "Answer" not in clause and it.question.index(clause) > 0
    es = Item(id="x", task="deep", lang="es", question="Un voslul es un tipo de virus. ¿Es cierto que un voslul "
              "infecta muchos humanos? Responde sí, no o indeterminado.", gold="yes")
    assert interrogative_clause(es) == "Es cierto que un voslul infecta muchos humanos?"
    ns = NeuroSymbolic(ContextBuilder(kb), backend=None, verify_loop=False, pinned=True)
    eng = ns._engine_for(it)
    sl = eng.slots(it)
    assert sl["subjects"][0] == it.focus_concepts[0]
    assert it.meta["prop"][0] in sl["events"]


def test_n1p_oracle_slots(kb, deep_items):
    """A perfect slot filler (gold subject / event / object, no roles) reproduces the gold through the
    role-tolerant decision on nearly every deep item (role-ambiguous properties are the exception)."""
    import json as _json

    from fgkb_llm.conditions import ContextBuilder
    from fgkb_llm.llm.backends import GenConfig
    from fgkb_llm.pipeline import NeuroSymbolic

    class SlotOracle:
        name, grammar_field = "slot-oracle", "json_schema"
        payload: ClassVar[dict] = {}

        def generate(self, prompts, cfg):
            props = cfg.json_schema["properties"]
            assert "subject_role" not in props and set(props) == {"negated", "subject", "event", "object"}
            return [_json.dumps(self.payload) for _ in prompts]

    o = SlotOracle()
    ns = NeuroSymbolic(ContextBuilder(kb), o, verify_loop=False, constrained=True, pinned=True)
    n = ok = 0
    for it in deep_items:
        if it.lang != "en" or it.meta.get("kind") == "composite" or not it.meta.get("prop"):
            continue
        ev, _, _, fill = it.meta["prop"]
        if any(s in fill for s in "|^&"):
            continue
        o.payload = {"negated": False, "subject": it.focus_concepts[0], "event": ev, "object": fill}
        res = ns.run_many([it], GenConfig())[0]
        n += 1
        ok += res.answer == it.gold
        if n >= 300:
            break
    assert n >= 100 and ok / n >= 0.97, (ok, n)


def test_nlg_disjunctive_attribute():
    """BE_01 with a disjunctive filler: qualities read as adjectives, entities give None (never
    'is terrorist 00 ^ +criminal', found in the pilot)."""
    from fgkb_llm.corel import nlg
    from fgkb_llm.kb.loaders import load_json

    path = ROOT / "data" / "processed" / "fungramkb.json"
    if not path.exists():
        pytest.skip("real KB not available")
    kb = load_json(str(path))
    bad = Prop(event="+BE_01", self_role="Theme", other_role="Attribute", filler="+TERRORIST_00 ^ +CRIMINAL_00")
    assert nlg.sentence(kb, "+MATERIAL_WITNESS_00", bad, lang="en") is None
    q = [c for c, v in kb.concepts.items() if v.semantic_type == "quality" and kb.lemmas(c, "en")
         and kb.lemmas(c, "es")][:2]
    good = Prop(event="+BE_01", self_role="Theme", other_role="Attribute", filler=f"{q[0]} | {q[1]}")
    s = nlg.sentence(kb, "+MATERIAL_WITNESS_00", good, lang="en")
    assert s and " or " in s and "_" not in s and "+" not in s


def test_make_main_bench_tags_pilot_overlap(tmp_path):
    """Main-study benchmark: groups that repeat a pilot item are tagged, pilot-dev repeats go to dev."""
    from fgkb_llm.bench.schema import read_jsonl

    mod = _load_script("make_main_bench")
    kb = str(ROOT / "tests" / "fixtures" / "toy_kb.json")
    pilot, main = tmp_path / "pilot.jsonl", tmp_path / "main.jsonl"
    from fgkb_llm.bench.deep import DeepSuite
    from fgkb_llm.bench.generate import BenchmarkGenerator
    from fgkb_llm.bench.schema import write_jsonl
    from fgkb_llm.bench.splits import assign_item_splits, concept_split
    from fgkb_llm.kb.loaders import load_json

    k = load_json(kb)
    items = BenchmarkGenerator(k, seed=11).generate_all() + DeepSuite(k, seed=11).generate()
    assign_item_splits(items, concept_split(k))
    write_jsonl(items, str(pilot))
    mod.main(["--kb", kb, "--pilot", str(pilot), "--out", str(main), "--seed", "11",
              "--summary", str(tmp_path / "s.json")])
    out = read_jsonl(str(main))
    assert out and all(i.id.startswith("main-") for i in out)
    assert all(i.meta["pilot_overlap"] in ("dev", "test") for i in out)  # same seed: everything repeats
    assert all(i.split == "dev" for i in out if i.meta["pilot_overlap"] == "dev")


def test_wordings_w2_and_paraphrase_checks():
    """W2 keeps the proposition inside a direct question; W3 checks reject meaning-changing paraphrases."""
    from fgkb_llm.bench import wording as W
    from fgkb_llm.bench.schema import Item
    from fgkb_llm.conditions import ContextBuilder
    from fgkb_llm.kb.loaders import load_json

    path = ROOT / "data" / "processed" / "fungramkb.json"
    if not path.exists():
        pytest.skip("real KB not available")
    kb = load_json(str(path))
    ctx = ContextBuilder(kb)
    q = "Is it true that a lone wolf deals with a crime? Answer yes, no or undetermined."
    assert W.split_item_text(q, "en") == ("", "a lone wolf deals with a crime")
    it = Item(id="t-en", task="deep", lang="en", question=q, gold="yes", focus_concepts=["$LONE_WOLF_00"],
              pair_id="p", meta={"prop": ["+DO_00", "Theme", "Referent", "+CRIME_00"]})
    w2 = W.w2_item(kb, ctx.linker, it, {"+CRIME_00": {"en": "offence"}})
    assert w2.question == "Does a lone wolf deal with an offence? Answer yes, no or undetermined."
    assert w2.gold == it.gold and w2.meta["base_id"] == "t-en" and w2.pair_id == "p@w2"
    es = Item(id="t-es", task="deep", lang="es", question="¿Es cierto que una bomba es pequeña? Responde sí, no o "
              "indeterminado.", gold="yes", focus_concepts=["+BOMB_00"], meta={})
    assert W.w2_item(kb, ctx.linker, es).question.startswith("¿Es pequeña una bomba?")
    nov = Item(id="n-en", task="deep", lang="en", gold="yes", focus_concepts=["$VOSLUL_00"],
               question="A voslul is a kind of virus. Is it true that a voslul is alive? Answer yes, no or undetermined.",
               meta={"kb_patch": {"concepts": {"$VOSLUL_00": {"parents": ["+VIRUS_00"], "lemmas": {"en": "voslul"}}}}})
    src = W.paraphrase_source(nov)
    ok = "A voslul is one type of virus. Would you say a voslul is living?"
    assert W.check_paraphrase(src, ok, nov, kb, ctx.linker) is None
    assert W.check_paraphrase(src, "A vozlul is a virus. Is a vozlul alive?", nov, kb, ctx.linker)  # pseudoword lost
    assert W.check_paraphrase(src, "A voslul is a virus. Is a voslul not alive?", nov, kb, ctx.linker)  # negation
    assert W.check_paraphrase(src, "A voslul is a virus and is alive.", nov, kb, ctx.linker)  # not a question
    alc = Item(id="a-en", task="deep", lang="en", gold="yes", focus_concepts=["+ALCOHOL_00"],
               question="Is it true that alcohol is ingested by a human? Answer yes, no or undetermined.")
    src = W.paraphrase_source(alc)
    assert W.check_paraphrase(src, "Do humans consume alcohol?", alc, kb, ctx.linker) is None  # flagged, kept
    assert W.subject_changed("Do humans consume alcohol?", alc, kb, ctx.linker)
    assert not W.subject_changed("Is alcohol consumed by humans?", alc, kb, ctx.linker)
    assert W.check_paraphrase(W.paraphrase_source(nov), "Some voslul are viruses. Is a voslul alive?", nov, kb,
                              ctx.linker) == "generic statement made existential"
    assert W.clean_paraphrase("Is alcohol drunk by people?\n\n(Note: the meaning is kept.)") == \
        "Is alcohol drunk by people?"


def test_n1p2_broad_candidates(kb, deep_items):
    """N1P2 always offers the relational events and every quality, and keeps N1P's candidates."""
    from fgkb_llm.conditions import ContextBuilder
    from fgkb_llm.pipeline import NeuroSymbolic
    from fgkb_llm.pipeline.neurosymbolic import RELATIONAL_EVENTS

    ctx = ContextBuilder(kb)
    n1p = NeuroSymbolic(ctx, backend=None, verify_loop=False, pinned=True)
    n1p2 = NeuroSymbolic(ctx, backend=None, verify_loop=False, broad=True)
    assert n1p2.pinned and n1p2.role_aware
    qualities = {c for c, con in kb.concepts.items() if con.semantic_type == "quality" and not c.startswith("#")}
    for it in [i for i in deep_items if i.lang == "en"][:40]:
        a, b = n1p._engine_for(it).slots(it), n1p2._engine_for(it).slots(it)
        assert set(a["events"]) <= set(b["events"]) and set(a["objects"]) <= set(b["objects"])
        assert {e for e in RELATIONAL_EVENTS if e in kb} <= set(b["events"]) and qualities <= set(b["objects"])

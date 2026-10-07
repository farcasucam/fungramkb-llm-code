import pytest

from fgkb_llm.corel import CORELSyntaxError, parse
from fgkb_llm.corel.facts import Prop, extract

# Table 3-6 of the thesis (subset of the notation)
THESIS = [
    (
        "+(e1: +BE_00 (x1: +BIRD_00)Theme (x2: +VERTEBRATE_00)Referent) "
        "*(e2: +COMPRISE_00 (x1)Theme (x3: m +FEATHER_00 & 2 +LEG_00 & 2 +WING_00)Referent) "
        "*(e3: +FLY_00 (x1)Agent (x1)Theme (x4)Origin (x5)Goal)"
    ),
    "*((e3: +COMPRISE_00 (x1)Theme (x4: 2 +LEG_00 & 1 +NECK_00)Referent) (e4: +BE_01 (x4)Theme (x5: +LONG_00)Attribute))",
    "+(e1: +LACK_00 (x1: +HUMAN_00)Theme (x2)Referent (f1: (e2: past +PUT_00 (x1)Agent (x2)Theme (x3)Origin (x4)Goal))Reason)",
    "+(e1: +KILL_00 (x1: +ANIMAL_00 ^ +HUMAN_00)Theme (x2: +ANIMAL_00)Referent (f1)Instrument)",
    "*(e1: +BE_01 (x1)Theme (x2: +RED_00)Attribute) +(e2: +BE_00 (x2)Theme (x3: +COLOUR_00)Referent)",
]


@pytest.mark.parametrize("text", THESIS)
def test_parse_roundtrip(text):
    mp = parse(text)
    again = parse(str(mp))
    assert str(again) == str(mp)


def test_structure():
    mp = parse(THESIS[0])
    assert [i.reasoning_op for i in mp.items] == ["+", "*", "*"]
    e2 = mp.items[1].predications[0]
    assert e2.event == "+COMPRISE_00"
    ref = e2.participants[1]
    assert ref.role == "Referent" and ref.filler_concepts() == ["+FEATHER_00", "+LEG_00", "+WING_00"]
    assert ref.filler.items[1].quant == "2"


def test_linked_and_operators():
    mp = parse(THESIS[1])
    assert mp.items[0].linked and len(mp.items[0].predications) == 2
    neg = parse("+(e9: n +FLY_00 (x1)Agent (x1)Theme)")
    assert neg.items[0].predications[0].negated
    sat = parse(THESIS[2]).items[0].predications[0].participants[2]
    assert sat.is_satellite and isinstance(sat.filler, list) and sat.filler[0].operators == ["past"]


def test_syntax_error():
    with pytest.raises(CORELSyntaxError):
        parse("+(e1 +BE_00 (x1)Theme")


def test_extract_bird():
    isas, facts = extract("+BIRD_00", parse(THESIS[0]))
    assert [(i.child, i.parent) for i in isas] == [("+BIRD_00", "+VERTEBRATE_00")]
    keys = {f.prop.key for f in facts}
    assert ("+FLY_00", "Agent", "", "") in keys
    assert ("+COMPRISE_00", "Theme", "Referent", "+LEG_00") in keys
    assert all(not f.strict for f in facts)


def test_disjunctive_filler_kept_whole():
    _, facts = extract("+X_00", parse("+(e1: +EAT_00 (x1)Agent (x2: +BREAD_00 | +FRUIT_00)Theme)"))
    assert facts[0].prop == Prop("+EAT_00", "Agent", "Theme", "+BREAD_00 | +FRUIT_00")

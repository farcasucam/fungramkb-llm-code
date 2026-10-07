from fgkb_llm.corel.facts import Prop

FLY = Prop("+FLY_00", "Agent")


def test_defeasible_inheritance(reasoner):
    assert reasoner.query("+BIRD_00", FLY).status == "true"
    sparrow = reasoner.query("$SPARROW_00", FLY)
    assert sparrow.status == "true" and sparrow.support[0][:2] == ("+BIRD_00", "default")


def test_exception_blocks_default(reasoner):
    ans = reasoner.query("$OSTRICH_00", FLY)
    assert ans.status == "false" and ans.strict
    assert reasoner.query("$PENGUIN_00", FLY).status == "false"


def test_strict_inheritance_depth(reasoner):
    bone = Prop("+COMPRISE_00", "Theme", "Referent", "+BONE_00")
    ans = reasoner.query("$SPARROW_00", bone)
    assert ans.status == "true" and ans.support[0][0] == "+VERTEBRATE_00"
    assert reasoner.depth("$SPARROW_00", "+VERTEBRATE_00") == 2


def test_unknown_and_assertions(reasoner):
    assert reasoner.query("+DOG_00", FLY).status == "unknown"
    assert reasoner.check_assertion("$OSTRICH_00", FLY) == "inconsistent"  # strict exception
    assert reasoner.check_assertion("$SPARROW_00", FLY, negated=True) == "consistent"  # default can be overridden
    hair = Prop("+COMPRISE_00", "Theme", "Referent", "+HAIR_00")
    assert reasoner.check_assertion("+DOG_00", hair, negated=True) == "inconsistent"


def test_multiple_inheritance_conflict(kb):
    import copy

    from fgkb_llm.reasoner import Reasoner

    k = copy.deepcopy(kb)
    # a concept that is both a bird (flies by default) and a penguin-like thing via second parent
    from fgkb_llm.kb.model import Concept

    k.concepts["+NOFLY_00"] = Concept("+NOFLY_00", ["+ANIMAL_00"], "entity", "*(e1: n +FLY_00 (x1)Agent)")
    k.concepts["$ODD_00"] = Concept("$ODD_00", ["+BIRD_00", "+NOFLY_00"], "entity")
    assert Reasoner(k).query("$ODD_00", FLY).status == "conflict"

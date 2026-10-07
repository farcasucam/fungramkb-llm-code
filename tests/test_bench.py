from collections import Counter

from fgkb_llm.bench.generate import balance
from fgkb_llm.bench.schema import read_jsonl, write_jsonl


def test_all_tasks_both_languages(items):
    tasks = Counter((i.task, i.lang) for i in items)
    for t in ("grounding", "entailment", "multihop", "procedural", "consistency"):
        assert tasks[(t, "en")] == tasks[(t, "es")] > 0


def test_ostrich_is_distractor(items):
    hits = [i for i in items if i.task == "entailment" and i.lang == "en"
            and i.hypothesis == "An ostrich flies."]
    assert hits and hits[0].gold == "contradiction" and hits[0].distractor


def test_multihop_has_depth_and_trace(items):
    hop = [i for i in items if i.task == "multihop" and i.template == "hop_prop_v1"]
    assert all(i.depth and i.depth >= 1 and i.trace for i in hop)
    assert max(i.depth for i in hop) >= 3


def test_selection_preference_violation(items):
    stone = [i for i in items if i.pair_id == "selpref:+EAT_00:+STONE_00" and i.lang == "en"]
    assert stone and stone[0].gold == "inconsistent"


def test_splits_and_io(items, tmp_path):
    assert {i.split for i in items} <= {"dev", "test_seen", "test_unseen"}
    p = tmp_path / "b.jsonl"
    write_jsonl(items[:10], p)
    assert [i.id for i in read_jsonl(p)] == [i.id for i in items[:10]]


def test_balance_keeps_twins(items):
    b = balance(items, {"entailment": 40})
    pairs = Counter(i.pair_id for i in b)
    assert all(v == 2 for v in pairs.values())

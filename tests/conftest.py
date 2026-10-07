import subprocess
import sys
from pathlib import Path

import pytest

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def kb():
    from fgkb_llm.kb import load_json

    path = FIX / "toy_kb.json"
    if not path.exists():
        subprocess.run([sys.executable, str(FIX / "make_toy_kb.py")], check=True)
    return load_json(path)


@pytest.fixture(scope="session")
def reasoner(kb):
    from fgkb_llm.reasoner import Reasoner

    return Reasoner(kb)


@pytest.fixture(scope="session")
def items(kb, reasoner):
    from fgkb_llm.bench.generate import BenchmarkGenerator
    from fgkb_llm.bench.splits import assign_item_splits, concept_split

    its = BenchmarkGenerator(kb, reasoner).generate_all()
    return assign_item_splits(its, concept_split(kb))

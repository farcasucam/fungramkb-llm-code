"""Build the SFT corpus for F1/F2 (knowledge injection by LoRA).

Only concepts in the *seen* split are used, so ``test_unseen`` measures
generalisation rather than memorisation. Formats (chat JSONL):

* statement:   "Tell me something about X."            -> verbalised postulate
* yes/no:      "Does X ...?"                              -> "Yes/No, because ..."  (with the trace)
* taxonomy:    "What kind of thing is X?"                 -> IS-A chain
* contrast:    exceptions (defeasible overrides) explained
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from ..corel.verbalize import subject_phrase, verbalise_prop
from ..kb.model import KnowledgeBase
from ..reasoner.asp import Reasoner

Q = {
    "about": {"en": "Tell me one fact about {x}.", "es": "Dime un dato sobre {x}."},
    "yn": {"en": "Is it true that {h}", "es": "¿Es cierto que {h}"},
    "kind": {"en": "What kind of thing is {x}?", "es": "¿Qué tipo de cosa es {x}?"},
}
A_YES = {"en": "Yes. {s} This follows from what is known about {a}.", "es": "Sí. {s} Se deduce de lo que se sabe sobre {a}."}
A_NO = {"en": "No. {s} This follows from what is known about {a}.", "es": "No. {s} Se deduce de lo que se sabe sobre {a}."}


def build_sft(kb: KnowledgeBase, split_map: dict[str, str], out_path: str | Path,
              langs=("en", "es"), seed: int = 5, max_per_concept: int = 40) -> int:
    r = Reasoner(kb)
    rng = random.Random(seed)
    rows = []
    for cid, c in kb.concepts.items():
        if split_map.get(cid) != "seen" or c.semantic_type != "entity" or c.level == "meta":
            continue
        per = []
        for lang in langs:
            x = subject_phrase(kb, cid, lang)
            chain = [a for a in sorted(r.ancestors_or_self(cid) - {cid}, key=lambda a: r.depth(cid, a) or 0)
                     if not a.startswith("#")]
            if chain:
                ans = ", ".join(subject_phrase(kb, a, lang) for a in chain)
                per.append((Q["kind"][lang].format(x=x), ans[0].upper() + ans[1:] + "."))
            for prop, a in r.closure(cid).items():
                if a.status not in ("true", "false"):
                    continue
                s = verbalise_prop(kb, cid, prop, strict=a.strict, negated=a.status == "false", lang=lang)
                anc = kb.label(a.support[0][0], lang)
                per.append((Q["about"][lang].format(x=x), s))
                h = verbalise_prop(kb, cid, prop, strict=True, negated=False, lang=lang, hedge=False)
                h = h[0].lower() + h[1:-1] + "?"
                tmpl = A_YES if a.status == "true" else A_NO
                per.append((Q["yn"][lang].format(h=h), tmpl[lang].format(s=s, a=anc)))
        rng.shuffle(per)
        for q, ans in per[:max_per_concept]:
            rows.append({"messages": [{"role": "user", "content": q}, {"role": "assistant", "content": ans}],
                         "concept": cid})
    rng.shuffle(rows)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.writelines(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    return len(rows)

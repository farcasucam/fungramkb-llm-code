"""GBNF grammar for *query* predications, used for constrained decoding in N1/N2.

The grammar is built per item from a candidate concept list, so the model can
only name concepts that exist in FunGramKB (and are plausible for the item).

    (e1: [n] EVENT (x1: SUBJECT)ROLE [(x2: FILLER)ROLE])
"""

from __future__ import annotations

ROLES = ("Agent", "Theme", "Referent", "Attribute", "Location", "Origin", "Goal",
         "Instrument", "Speed", "Manner", "Purpose", "Time")


def _alt(values) -> str:
    vals = sorted(set(values))
    return " | ".join('"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"' for v in vals) or '"+NONE_00"'


def query_grammar(events: list[str], concepts: list[str], roles=ROLES) -> str:
    return "\n".join([
        'root ::= "(e1: " neg event " " subj obj ")"',
        'neg ::= "n " | ""',
        f"event ::= {_alt(events)}",
        f"concept ::= {_alt(concepts)}",
        f"role ::= {_alt(roles)}",
        'subj ::= "(x1: " concept ")" role',
        'obj ::= " (x2: " concept ")" role | ""',
    ])


# --------------------------------------------------------------------------- JSON-schema variant
# Servers without GBNF support (Ollama) can still constrain decoding with a JSON schema. For the
# one-predication query language used by N1/N2 the two are equivalent: every field is an enum over
# the same candidate events, concepts and roles, and json_to_query() rebuilds the COREL string.

def query_schema(events: list[str], concepts: list[str], roles=ROLES) -> dict:
    concepts = sorted(set(concepts)) or ["+NONE_00"]
    roles = sorted(set(roles))
    return {
        "type": "object",
        "properties": {
            "negated": {"type": "boolean"},
            "event": {"type": "string", "enum": sorted(set(events)) or ["+NONE_00"]},
            "subject": {"type": "string", "enum": concepts},
            "subject_role": {"type": "string", "enum": roles},
            "object": {"type": "string", "enum": [""] + concepts},
            "object_role": {"type": "string", "enum": [""] + roles},
        },
        "required": ["negated", "event", "subject", "subject_role", "object", "object_role"],
        "additionalProperties": False,
    }


def json_to_query(obj: dict) -> str:
    neg = "n " if obj.get("negated") else ""
    q = f"(e1: {neg}{obj['event']} (x1: {obj['subject']}){obj['subject_role']}"
    if obj.get("object") and obj.get("object_role"):
        q += f" (x2: {obj['object']}){obj['object_role']}"
    return q + ")"


def query_schema_role_aware(events: list[str], concepts: list[str], roles_by_event: dict[str, set[str]],
                            roles=ROLES) -> dict:
    """Like query_schema, but each event only admits the roles attested for it (thematic frame and
    meaning postulates): an anyOf with one branch per event."""
    concepts = sorted(set(concepts)) or ["+NONE_00"]
    branches = []
    for ev in sorted(set(events)) or ["+NONE_00"]:
        rs = sorted(roles_by_event.get(ev) or set(roles))
        branches.append({
            "type": "object",
            "properties": {
                "negated": {"type": "boolean"},
                "event": {"type": "string", "enum": [ev]},
                "subject": {"type": "string", "enum": concepts},
                "subject_role": {"type": "string", "enum": rs},
                "object": {"type": "string", "enum": [""] + concepts},
                "object_role": {"type": "string", "enum": [""] + rs},
            },
            "required": ["negated", "event", "subject", "subject_role", "object", "object_role"],
            "additionalProperties": False,
        })
    return {"anyOf": branches}


def query_schema_slots(subjects: list[str], events: list[str], objects: list[str]) -> dict:
    """N1P: the model fills three slots and the polarity; roles are not generated.

    Subjects are restricted to the entities the linker found in the interrogative clause, so the
    model cannot query a concept from the background sentences instead of the one asked about.
    """
    return {
        "type": "object",
        "properties": {
            "negated": {"type": "boolean"},
            "subject": {"type": "string", "enum": sorted(set(subjects)) or ["+NONE_00"]},
            "event": {"type": "string", "enum": sorted(set(events)) or ["+NONE_00"]},
            "object": {"type": "string", "enum": [""] + sorted(set(objects) - {""})},
        },
        "required": ["negated", "subject", "event", "object"],
        "additionalProperties": False,
    }

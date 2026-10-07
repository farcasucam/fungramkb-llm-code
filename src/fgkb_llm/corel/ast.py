"""Typed AST for COREL meaning postulates (subset)."""

from __future__ import annotations

from dataclasses import dataclass, field

POLARITY_OPS = {"n"}
ASPECT_OPS = {"ing", "pro", "egr"}
TENSE_OPS = {"rpast", "past", "npast", "pres", "nfut", "fut", "rfut"}
MODALITY_OPS = {"cert", "prob", "pos", "obl", "adv", "perm"}

ARGUMENT_ROLES = {"Agent", "Theme", "Referent"}
SHARED_ROLES = {"Location", "Origin", "Goal", "Attribute"}
SATELLITE_ROLES = {
    "Beneficiary", "Company", "Comparison", "Condition", "Distance", "Duration", "Frequency",
    "Instrument", "Manner", "Material", "Means", "Position", "Purpose", "Quantity", "Reason",
    "Result", "Role", "Route", "Scene", "Speed", "Time",
}


@dataclass
class SelConcept:
    concept: str
    quant: str | None = None
    negated: bool = False

    def concepts(self) -> list[str]:
        return [self.concept]

    def __str__(self) -> str:
        parts = (["n"] if self.negated else []) + ([self.quant] if self.quant else []) + [self.concept]
        return " ".join(parts)


@dataclass
class SelVar:
    """Coreference to another participant, e.g. (f3: x1)Scene."""

    var: str

    def concepts(self) -> list[str]:
        return []

    def __str__(self) -> str:
        return self.var


@dataclass
class SelGroup:
    """Selection preferences joined by one or more connectors (& | ^)."""

    items: list[Sel]
    connectors: list[str]

    def concepts(self) -> list[str]:
        out: list[str] = []
        for it in self.items:
            out.extend(it.concepts())
        return out

    @property
    def is_conjunctive(self) -> bool:
        return all(c == "&" for c in self.connectors)

    def __str__(self) -> str:
        parts = [str(self.items[0])]
        for conn, it in zip(self.connectors, self.items[1:]):
            s = str(it)
            if isinstance(it, SelGroup):
                s = f"({s})"
            parts.append(f"{conn} {s}")
        return " ".join(parts)


Sel = SelConcept | SelGroup | SelVar


@dataclass
class Participant:
    var: str  # x1, f2, ...
    role: str
    filler: Sel | list[Predication] | None = None

    @property
    def is_satellite(self) -> bool:
        return self.var.startswith("f")

    def filler_concepts(self) -> list[str]:
        if self.filler is None or isinstance(self.filler, list):
            return []
        return self.filler.concepts()

    def __str__(self) -> str:
        if self.filler is None:
            inner = self.var
        elif isinstance(self.filler, list):
            inner = f"{self.var}: " + " ".join(str(p) for p in self.filler)
        else:
            inner = f"{self.var}: {self.filler}"
        return f"({inner}){self.role}"


@dataclass
class Predication:
    evar: str
    event: str
    operators: list[str] = field(default_factory=list)
    participants: list[Participant] = field(default_factory=list)

    @property
    def negated(self) -> bool:
        return any(op in POLARITY_OPS for op in self.operators)

    def participant(self, var: str) -> list[Participant]:
        return [p for p in self.participants if p.var == var]

    def __str__(self) -> str:
        ops = " ".join(self.operators)
        head = f"{self.evar}: {ops + ' ' if ops else ''}{self.event}"
        parts = " ".join(str(p) for p in self.participants)
        return f"({head}{' ' + parts if parts else ''})"


@dataclass
class PostulateItem:
    reasoning_op: str  # "+" strict, "*" defeasible
    predications: list[Predication]

    @property
    def strict(self) -> bool:
        return self.reasoning_op == "+"

    @property
    def linked(self) -> bool:
        return len(self.predications) > 1

    def __str__(self) -> str:
        if self.linked:
            return f"{self.reasoning_op}(" + " ".join(str(p) for p in self.predications) + ")"
        return f"{self.reasoning_op}{self.predications[0]}"


@dataclass
class MeaningPostulate:
    items: list[PostulateItem]

    def predications(self) -> list[tuple[PostulateItem, Predication]]:
        return [(it, p) for it in self.items for p in it.predications]

    def concepts(self) -> set[str]:
        out: set[str] = set()

        def visit(pred: Predication) -> None:
            out.add(pred.event)
            for part in pred.participants:
                if isinstance(part.filler, list):
                    for sub in part.filler:
                        visit(sub)
                else:
                    out.update(part.filler_concepts())

        for _, p in self.predications():
            visit(p)
        return out

    def __str__(self) -> str:
        return "\n".join(str(i) for i in self.items)

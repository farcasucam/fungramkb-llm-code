"""Parse COREL text into the typed AST."""

from __future__ import annotations

from functools import lru_cache
from importlib import resources

from lark import Lark, Token, Transformer
from lark.exceptions import LarkError

from .ast import (
    MeaningPostulate,
    Participant,
    PostulateItem,
    Predication,
    SelConcept,
    SelGroup,
    SelVar,
)


class CORELSyntaxError(ValueError):
    pass


@lru_cache(maxsize=1)
def _parser() -> Lark:
    grammar = resources.files("fgkb_llm.corel").joinpath("corel.lark").read_text(encoding="utf-8")
    return Lark(grammar, parser="earley", maybe_placeholders=False)


def _is_polarity(tok) -> bool:
    return isinstance(tok, Token) and tok.type == "POLARITY"


class _ToAST(Transformer):
    def concept(self, items):
        return str(items[0])

    def pred_op(self, items):
        return str(items[0])

    def sel_concept(self, items):
        concept = items[-1]
        mods = [str(i) for i in items[:-1]]
        neg = bool(mods) and mods[0] == "n" and (len(mods) == 2 or (len(mods) == 1 and _is_polarity(items[0])))
        if neg:
            mods = mods[1:]
        return SelConcept(concept=concept, quant=mods[0] if mods else None, negated=neg)

    def sel_var(self, items):
        return SelVar(var=str(items[0]))

    def sel_group(self, items):
        sels = [i for i in items if not isinstance(i, Token)]
        conns = [str(i) for i in items if isinstance(i, Token)]
        if len(sels) == 1:
            return sels[0]
        return SelGroup(items=sels, connectors=conns)

    def pred_filler(self, items):
        return [i for i in items if isinstance(i, Predication)]

    def participant(self, items):
        var = str(items[0])
        role = str(items[-1])
        filler = items[1] if len(items) == 3 else None
        if isinstance(filler, Predication):
            filler = [filler]
        return Participant(var=var, role=role, filler=filler)

    def participants(self, items):
        return [i for i in items if isinstance(i, Participant)]

    def predication(self, items):
        evar = str(items[0])
        rest = items[1:]
        participants: list[Participant] = []
        if rest and isinstance(rest[-1], list):
            participants = rest[-1]
            rest = rest[:-1]
        event = rest[-1]
        ops = list(rest[:-1])
        return Predication(evar=evar, event=event, operators=ops, participants=participants)

    def free_item(self, items):
        return PostulateItem(reasoning_op=str(items[0]), predications=[items[1]])

    def linked_item(self, items):
        return PostulateItem(reasoning_op=str(items[0]), predications=list(items[1:]))

    def postulate(self, items):
        return MeaningPostulate(items=list(items))


def parse(text: str) -> MeaningPostulate:
    """Parse a meaning postulate. Raises CORELSyntaxError on failure."""
    try:
        tree = _parser().parse(text.strip())
    except LarkError as exc:  # pragma: no cover - message passthrough
        raise CORELSyntaxError(str(exc)) from exc
    return _ToAST().transform(tree)


def try_parse(text: str) -> tuple[MeaningPostulate | None, str | None]:
    try:
        return parse(text), None
    except CORELSyntaxError as exc:
        return None, str(exc).splitlines()[0]

"""Role-aware natural-language generation for FunGramKB properties (English and Spanish).

Why: a property only states which *role* the definiendum plays in an event. "Cannabis" is the
Theme of +SMOKE_01 (it is smoked), not the smoker. The grammatical subject of the sentence is the
highest-ranked role present in the predication (Agent > Theme > Referent), a simplification of
the RRG actor hierarchy used by FunGramKB; the definiendum's own role decides the voice:

  A  definiendum = subject role                 -> active      "An ostrich runs fast."
  B  definiendum = core non-subject (Theme, Referent, Attribute) -> passive
                                                               "Cannabis is smoked by a human."
  C  definiendum = oblique (Location, Goal, Instrument ...) -> the other participant is subject
                                                               "A human lives in a town."
  D  causer Agent of #EMOTION / #COGNITION events -> causative "Cannabis makes a human feel calm."

``describe`` returns (subject, predicate) so callers can build relative clauses
("something that is smoked by a human"). Properties that cannot be stated meaningfully
(light verbs without filler, missing lemmas) return None and are excluded from items.
"""

from __future__ import annotations

from ..kb.model import KnowledgeBase
from .facts import Prop

ROLE_RANK = ["Agent", "Theme", "Referent", "Attribute", "Location", "Goal", "Origin"]
CORE = {"Theme", "Referent", "Attribute"}
DROP_ROLES = {"Time", "Frequency", "Duration", "Position", "Speed"}  # low-information satellites
LIGHT = {"+DO_00", "+BE_00", "+HAPPEN_00", "+EXIST_00", "+HAVE_00", "+FEEL_00"}
CAUSATIVE_META = {"#EMOTION", "#COGNITION"}

PREP = {
    "en": {"Location": "in", "Goal": "to", "Origin": "from", "Instrument": "with", "Means": "by means of",
           "Company": "with", "Beneficiary": "for", "Purpose": "for", "Reason": "because of", "Manner": "",
           "Speed": "", "Duration": "for", "Time": "at", "Frequency": "", "Position": "", "Result": "causing",
           "Scene": "in", "Material": "of", "Condition": "if"},
    "es": {"Location": "en", "Goal": "a", "Origin": "de", "Instrument": "con", "Means": "mediante",
           "Company": "con", "Beneficiary": "para", "Purpose": "para", "Reason": "por", "Manner": "",
           "Speed": "", "Duration": "durante", "Time": "en", "Frequency": "", "Position": "", "Result": "causando",
           "Scene": "en", "Material": "de", "Condition": "si"},
}
# ---------------------------------------------------------------------------------------- English
EN_IRREG = {  # base: (3sg, past participle)
    "be": ("is", "been"), "have": ("has", "had"), "do": ("does", "done"), "say": ("says", "said"),
    "give": ("gives", "given"), "take": ("takes", "taken"), "take away": ("takes away", "taken away"),
    "sell": ("sells", "sold"), "leave": ("leaves", "left"), "feel": ("feels", "felt"), "think": ("thinks", "thought"),
    "burst": ("bursts", "burst"), "shoot": ("shoots", "shot"), "find": ("finds", "found"), "build": ("builds", "built"),
    "hurt": ("hurts", "hurt"), "hold": ("holds", "held"), "throw": ("throws", "thrown"), "put": ("puts", "put"),
    "lend": ("lends", "lent"), "know": ("knows", "known"), "choose": ("chooses", "chosen"), "eat": ("eats", "eaten"),
    "grow": ("grows", "grown"), "see": ("sees", "seen"), "write": ("writes", "written"), "steal": ("steals", "stolen"),
    "buy": ("buys", "bought"), "sleep": ("sleeps", "slept"), "show": ("shows", "shown"), "hide": ("hides", "hidden"),
    "pay": ("pays", "paid"), "stop": ("stops", "stopped"), "get": ("gets", "got"), "fly": ("flies", "flown"),
    "run": ("runs", "run"), "swim": ("swims", "swum"), "go": ("goes", "gone"), "obtain": ("obtains", "obtained"),
    "be located": ("is located", "located"), "comprise": ("consists of", "comprised"),
}
EN_MASS = {"money", "alcohol", "petrol", "tobacco", "cannabis", "information", "food", "metal", "cloth", "soil",
           "violence", "fear", "hatred", "strength", "protection", "damage", "evidence", "cocaine", "heroin",
           "hashish", "marijuana", "sex", "bacteria", "music", "electricity", "poison", "oil", "water", "law",
           "justice", "fraud", "corruption", "terrorism", "slavery", "torture", "custody", "parole", "bail"}
ES_ESTAR = {"vivo", "muerto", "enfermo", "sano", "roto", "lleno", "vacío", "casado", "herido", "preso", "cansado",
            "contento", "nervioso", "feliz", "triste", "borracho", "despierto", "dormido", "situado", "ubicado"}
SUBJ_PLACEHOLDER = {"en": "something", "es": "algo"}


def _en_forms(base: str) -> tuple[str, str]:
    if base in EN_IRREG:
        return EN_IRREG[base]
    head, _, tail = base.partition(" ")
    if head in EN_IRREG:
        s3, pp = EN_IRREG[head]
        return f"{s3} {tail}".strip(), f"{pp} {tail}".strip()
    if head.endswith(("s", "sh", "ch", "x", "z", "o")):
        s3 = head + "es"
    elif head.endswith("y") and head[-2:-1] not in "aeiou":
        s3 = head[:-1] + "ies"
    else:
        s3 = head + "s"
    if head.endswith("e"):
        pp = head + "d"
    elif head.endswith("y") and head[-2:-1] not in "aeiou":
        pp = head[:-1] + "ied"
    else:
        pp = head + "ed"
    return f"{s3} {tail}".strip(), f"{pp} {tail}".strip()


MASS_ANCESTORS = {"+NARCOTIC_00", "+LIQUID_00", "+TOXIN_00", "+GAS_00", "+DRUG_00"}


def is_mass(kb: KnowledgeBase, cid: str) -> bool:
    if cid not in kb.concepts:
        return False
    return bool(MASS_ANCESTORS & (set(kb.ancestors(cid)) | {cid}))


def _en_np(kb: KnowledgeBase, cid: str, quant: str = "") -> str:
    if any(sep in cid for sep in ("|", "^", "&")):
        return _en_list(kb, cid)
    lab = kb.label(cid, "en")
    if is_mass(kb, cid) and not quant:
        return lab
    if quant and quant.isdigit() and quant != "1":
        return f"{quant} {_en_plural(lab)}"
    if quant in ("m", "i"):
        return f"many {_en_plural(lab)}"
    if quant in ("s", "p"):
        return f"some {_en_plural(lab)}"
    abstract = cid in kb.concepts and "#PHYSICAL" not in kb.ancestors(cid)
    if lab in EN_MASS or cid.startswith("#") or (abstract and lab.endswith(("ing", "ism", "ness", "ity", "ery", "ment"))):
        return lab
    return ("an " if lab[:1] in "aeiou" else "a ") + lab


def _en_plural(lab: str) -> str:
    head, _, tail = lab.rpartition(" ")
    w = tail or lab
    if w.endswith(("s", "sh", "ch", "x")):
        w += "es"
    elif w.endswith("y") and w[-2:-1] not in "aeiou":
        w = w[:-1] + "ies"
    elif w in ("man", "woman", "child"):
        w = {"man": "men", "woman": "women", "child": "children"}[w]
    else:
        w += "s"
    return f"{head} {w}".strip() if tail else w


def _split_filler(cid: str) -> tuple[list[tuple[str, str]], str]:
    import re

    conn = "and" if "&" in cid and "|" not in cid and "^" not in cid else "or"
    parts = []
    for tok in re.split(r"[|^&]", cid):
        tok = tok.strip().strip("()").strip()
        bits = tok.split()
        q = bits[0] if len(bits) > 1 else ""
        parts.append((bits[-1], q))
    return parts, conn


def _en_list(kb: KnowledgeBase, cid: str) -> str:
    parts, conn = _split_filler(cid)
    nps = [_en_np(kb, c, q) for c, q in parts]
    return (", ".join(nps[:-1]) + f" {conn} " + nps[-1]) if len(nps) > 1 else nps[0]


def _es_list(kb: KnowledgeBase, cid: str) -> str:
    parts, conn = _split_filler(cid)
    nps = [_es_np(kb, c, q)[0] for c, q in parts]
    c = "y" if conn == "and" else "o"
    return (", ".join(nps[:-1]) + f" {c} " + nps[-1]) if len(nps) > 1 else nps[0]


# ---------------------------------------------------------------------------------------- Spanish
ES_3SG = {
    "ser": "es", "estar": "está", "tener": "tiene", "hacer": "hace", "decir": "dice", "dar": "da", "ir": "va",
    "ver": "ve", "poner": "pone", "salir": "sale", "pensar": "piensa", "sentir": "siente", "elegir": "elige",
    "encontrar": "encuentra", "defender": "defiende", "construir": "construye", "fluir": "fluye", "crecer": "crece",
    "dormir": "duerme", "morir": "muere", "mostrar": "muestra", "contener": "contiene", "obtener": "obtiene",
    "detener": "detiene", "saber": "sabe", "atacar": "ataca", "herir": "hiere", "ingerir": "ingiere",
    "transferir": "transfiere", "percibir": "percibe", "vigilar": "vigila", "moverse": "se mueve",
    "unirse": "se une", "llevarse": "se lleva", "manifestarse": "se manifiesta", "constar de": "consta de",
    "sujetar": "sujeta", "volar": "vuela", "correr": "corre", "nadar": "nada", "lograr": "logra",
    "escribir": "escribe", "describir": "describe", "abusar sexualmente": "abusa sexualmente",
}
ES_PP = {
    "hacer": "hecho", "decir": "dicho", "poner": "puesto", "ver": "visto", "escribir": "escrito",
    "describir": "descrito", "morir": "muerto", "abrir": "abierto", "romper": "roto", "volver": "vuelto",
    "construir": "construido", "llevarse": "llevado", "unirse": "unido", "moverse": "movido",
    "abusar sexualmente": "objeto de abuso sexual", "constar de": "compuesto de",
}
ES_FEM_E = {"gente", "muerte", "noche", "calle", "clase", "sangre", "llave", "carne", "mente", "fuente",
            "frente", "nube", "leche", "suerte", "parte", "base", "corte", "cárcel", "ley", "piel", "red", "sal",
            "flor", "mujer", "imagen", "razón", "superficie", "pared", "costumbre", "orden", "señal", "tos"}
ES_MASC_A = {"día", "mapa", "problema", "programa", "sistema", "tema", "clima", "idioma", "planeta", "poema",
             "terrorista", "pirata", "policía"}
ES_MASS = {"dinero", "alcohol", "gasolina", "tabaco", "cannabis", "información", "comida", "metal", "tela",
           "violencia", "miedo", "odio", "fuerza", "protección", "daño", "cocaína", "heroína", "hachís",
           "marihuana", "sexo", "música", "electricidad", "veneno", "aceite", "agua", "fraude", "corrupción",
           "terrorismo", "esclavitud", "tortura"}


def es_feminine(noun: str) -> bool:
    head = noun.split(" ")[0].lower()
    if head in ES_FEM_E:
        return True
    if head in ES_MASC_A:
        return False
    if head.endswith(("ista", "ita")) and head not in ("cita", "visita"):
        return False  # common-gender nouns (terrorista, homicida): masculine generic
    return head.endswith(("a", "ción", "sión", "dad", "tad", "tud", "umbre", "ie"))


def _es_np(kb: KnowledgeBase, cid: str, quant: str = "", definite: bool = False) -> tuple[str, bool]:
    if any(sep in cid for sep in ("|", "^", "&")):
        return _es_list(kb, cid), False
    lab = kb.label(cid, "es")
    fem = es_feminine(lab)
    if is_mass(kb, cid) and not quant:
        definite = True
    if quant and quant.isdigit() and quant != "1":
        return f"{quant} {_es_plural(lab)}", fem
    if quant in ("m", "i"):
        return f"{'muchas' if fem else 'muchos'} {_es_plural(lab)}", fem
    if quant in ("s", "p"):
        return f"{'algunas' if fem else 'algunos'} {_es_plural(lab)}", fem
    stressed_a = fem and lab.split(" ")[0] in ("arma", "agua", "área", "hacha", "alma", "águila", "aula", "hambre")
    if definite or lab.split(" ")[0] in ES_MASS:
        return ("el " if (not fem or stressed_a) else "la ") + lab, fem
    return ("un " if (not fem or stressed_a) else "una ") + lab, fem


def _es_plural(lab: str) -> str:
    w, _, rest = lab.partition(" ")
    if w[-1:] in "aeiouáéó":
        w += "s"
    elif w.endswith("z"):
        w = w[:-1] + "ces"
    elif w.endswith("ión"):
        w = w[:-3] + "iones"
    elif w.endswith("ón"):
        w = w[:-2] + "ones"
    else:
        w += "es"
    return f"{w} {rest}".strip()


def _es_3sg(v: str) -> str:
    if v in ES_3SG:
        return ES_3SG[v]
    head, _, tail = v.partition(" ")
    if head.endswith("se") and len(head) > 4:
        return "se " + _es_3sg(head[:-2] + (" " + tail if tail else "")).strip()
    if head.endswith("ar"):
        out = head[:-2] + "a"
    elif head.endswith(("er", "ir")):
        out = head[:-2] + "e"
    else:
        out = head
    return f"{out} {tail}".strip()


def _es_3pl(v: str) -> str:
    sg = _es_3sg(v)
    head, _, tail = sg.rpartition(" ") if sg.startswith("se ") else ("", "", sg)
    word, _, rest = tail.partition(" ")
    pl = {"es": "son", "está": "están", "ha": "han"}.get(word, word + "n")
    return " ".join(x for x in (head, pl, rest) if x)


def _es_pp(v: str, fem: bool) -> str:
    pp = ES_PP.get(v)
    if pp is None:
        head = v.split(" ")[0]
        head = head.removesuffix("se")
        pp = head[:-2] + ("ado" if head.endswith("ar") else "ido")
    if fem and pp.endswith("o"):
        pp = pp[:-1] + "a"
    return pp


def _es_adj(adj: str, fem: bool) -> str:
    if fem and adj.endswith("o"):
        return adj[:-1] + "a"
    return adj


NEVER = {"always": "never", "siempre": "nunca"}


def _cop(en: bool, negated: bool, hedge: str | None, es_verb: str = "es") -> str:
    """Copula with polarity and hedge: strict negation reads 'never', defeasible 'typically not'."""
    if en:
        if not negated:
            return f"is {hedge}" if hedge else "is"
        if hedge in NEVER:
            return "is never"
        return f"is {hedge} not" if hedge else "is not"
    if not negated:
        return f"{es_verb} {hedge}" if hedge else es_verb
    if hedge in NEVER:
        return f"nunca {es_verb}"
    return f"{hedge} no {es_verb}" if hedge else f"no {es_verb}"


def _vp(en: bool, negated: bool, hedge: str | None, base: str, finite: str) -> str:
    """Finite verb phrase with polarity and hedge (English base form needed for do-support)."""
    if en:
        if not negated:
            return f"{hedge} {finite}" if hedge else finite
        if hedge in NEVER:
            return f"never {finite}"
        return f"{hedge} does not {base}" if hedge else f"does not {base}"
    if not negated:
        return f"{hedge} {finite}" if hedge else finite
    if hedge in NEVER:
        return f"nunca {finite}"
    return f"{hedge} no {finite}" if hedge else f"no {finite}"


# ------------------------------------------------------------------------------------------- core
def _meta(kb: KnowledgeBase, cid: str) -> str | None:
    seen, todo = set(), [cid]
    while todo:
        c = todo.pop(0)
        if c.startswith("#") and c not in ("#EVENT", "#ENTITY", "#QUALITY"):
            return c
        if c in kb.concepts and c not in seen:
            seen.add(c)
            todo += kb.concepts[c].parents
    return None


# verbs the NLG uses for light events instead of their lemma (see describe); also read by N1P to
# recognise the event in a question
LIGHT_VERBS = {"+DO_00": {"en": ("engage in", "deal with"), "es": ("dedicarse a", "comerciar con")},
               "+COMPRISE_00": {"en": ("have",), "es": ("tener",)}}


def _verb(kb: KnowledgeBase, ev: str, lang: str) -> str | None:
    lem = kb.lemmas(ev, lang)
    if not lem:
        return None
    if ev == "+COMPRISE_00":
        return "have" if lang == "en" else "tener"
    return lem[0]


def describe(kb: KnowledgeBase, x: str, prop: Prop, *, negated: bool = False, lang: str = "en",
             hedge: str | None = None, subject: str | None = None) -> tuple[str, str] | None:
    """Return (subject phrase, predicate) or None if the property cannot be stated well.

    ``subject`` overrides the subject NP for the definiendum (e.g. "something", a pseudoword).
    ``hedge`` is an adverb such as "typically" / "normalmente" (None for test items).
    """
    ev, r0, r1, f = prop.event, prop.self_role, prop.other_role, prop.filler
    if r1 in DROP_ROLES or r0 in DROP_ROLES:
        return None
    is_list = bool(f) and any(sep in f for sep in ("|", "^", "&"))
    if is_list:
        parts, _ = _split_filler(f)
        has_filler = all(kb.lemmas(c, lang) for c, _ in parts)
        if not has_filler:
            return None
    else:
        has_filler = bool(f) and (f in kb.concepts or bool(kb.lemmas(f, lang)))
    if ev in LIGHT and not has_filler:
        return None
    if ev in ("+BE_01", "+BE_02") and not has_filler:
        return None
    v = _verb(kb, ev, lang)
    if ev == "+DO_00" and has_filler and not is_list and r0 == (prop.subj_role or r0):
        ftype = kb.concepts[f].semantic_type if f in kb.concepts else "entity"
        activity = ftype == "event" or "+CRIME_00" in kb.ancestors(f) or kb.label(f, "en").endswith("ing")
        v = LIGHT_VERBS["+DO_00"][lang][0 if activity else 1]
        prop = Prop(ev, r0, "__plain__", f, prop.quant, prop.subj_role)
        r1 = "__plain__"
    if ev == "+DO_00" and v not in LIGHT_VERBS["+DO_00"]["en"] + LIGHT_VERBS["+DO_00"]["es"]:
        return None  # 'is done by' / 'does' carry no content outside the deal/engage readings
    if v is None or (has_filler and not is_list and not kb.lemmas(f, lang)):
        return None
    if f and not has_filler:
        return None
    if subject is None and not kb.lemmas(x, lang):
        return None  # no lemma in this language: a fallback label would mix languages ("un weapon")
    subj_role = prop.subj_role or r0
    meta = _meta(kb, ev)
    if meta == "#MOTION" and r0 == "Theme" and subj_role == "Agent" and r1 != "Agent":
        subj_role = "Theme"  # an unspecified causer of motion: the moving Theme is the subject ("leaves")
    en = lang == "en"
    if en:
        x_np = subject or _en_np(kb, x)
        f_np = _en_np(kb, f, prop.quant) if f else ""
    else:
        x_np, x_fem = (subject, False) if subject else _es_np(kb, x, definite=False)
        f_np = _es_np(kb, f, prop.quant)[0] if f else ""
    if v in ("engage in", "dedicarse a") and kb.concepts.get(f) and kb.concepts[f].semantic_type == "entity":
        lab = kb.label(f, lang)
        f_np = lab if en else _es_np(kb, f, definite=True)[0]

    if f and not is_list and f in kb.concepts and kb.concepts[f].semantic_type == "quality" and r1 == "Manner":
        adj = kb.label(f, lang)
        f_np = f"in {'an' if adj[:1] in 'aeiou' else 'a'} {adj} way" if en else f"de forma {_es_adj(adj, True)}"
        r1 = "__plain__"
    elif f and not is_list and f in kb.concepts and kb.concepts[f].semantic_type == "event":
        vf = kb.label(f, lang)
        f_np = (vf.split(" ")[0] + "ing") if en and not vf.endswith("e") else (vf[:-1] + "ing" if en else vf)

    def obj(role: str, np: str) -> str:
        if not np:
            return ""
        if role == "__plain__":
            return f" {np}"
        p = PREP[lang].get(role, "")
        return f" {p} {np}".replace("  ", " ") if p else f" {np}"

    # copula with attribute / location
    if ev == "+BE_01" and r0 in ("Theme",) and r1 == "Attribute":
        if is_list:
            # "+TERRORIST_00 ^ +CRIMINAL_00" as an attribute: only lists of qualities read as adjectives
            parts, conn = _split_filler(f)
            if not all(kb.concepts.get(c) and kb.concepts[c].semantic_type == "quality" for c, _ in parts):
                return None
            word = {"or": "or" if en else "o", "and": "and" if en else "y"}[conn]
            labs = [kb.label(c, lang) if en else _es_adj(kb.label(c, lang), x_fem) for c, _ in parts]
            return x_np, f"{_cop(en, negated, hedge)} {f' {word} '.join(labs)}"
        adj = kb.label(f, lang)
        if en:
            return x_np, f"{_cop(True, negated, hedge)} {adj}"
        cop = "está" if adj in ES_ESTAR else "es"  # states take estar: "está vivo"
        return x_np, f"{_cop(False, negated, hedge, cop)} {_es_adj(adj, x_fem)}"
    if ev == "+BE_02" and r0 == "Theme" and r1 == "Location":
        if en:
            return x_np, f"{_cop(True, negated, hedge)} located in {f_np}"
        return x_np, f"{_cop(False, negated, hedge, 'está')} en {f_np}"

    if ev in ("+BE_01", "+BE_02"):
        return None  # copulas are only stated in the two patterns above ("is been by" is not English)

    # D: causative
    if r0 == "Agent" and meta in CAUSATIVE_META:
        theme = f_np if f and r1 == "Theme" else ("someone" if en else "alguien")
        attr = (" " + kb.label(f, lang)) if f and r1 == "Attribute" and not is_list else ""
        if ev == "+FEEL_00" and not attr:
            return None  # "makes a human feel" is incomplete without the feeling
        if en:
            return x_np, f"{_vp(True, negated, hedge, 'make', 'makes')} {theme} {v}{attr}"
        sub = {"sentir": "se sienta", "pensar": "piense", "saber": "sepa", "tener": "tenga"}.get(
            v, (v[:-2] + "e") if v.endswith("ar") else (v[:-2] + "a"))
        return x_np, f"{_vp(False, negated, hedge, 'hacer', 'hace')} que {theme} {sub}{attr}"

    if r0 == subj_role:  # A: active
        tail = obj(r1, f_np) if r1 not in CORE else obj("", f_np)
        if en:
            s3, _ = _en_forms(v)
            if v.startswith("be "):
                vp = f"{_cop(True, negated, hedge)} {v[3:]}"
            else:
                vp = _vp(True, negated, hedge, v, s3)
            return x_np, f"{vp}{tail}"
        vp = _vp(False, negated, hedge, v, _es_3sg(v))
        return x_np, f"{vp}{tail}"

    if r0 in CORE:  # B: passive
        by = ""
        if f and r1 == subj_role:
            by = f" by {f_np}" if en else f" por {f_np}"
        elif f:
            by = obj(r1, f_np)
        if en:
            _, pp = _en_forms(v)
            return x_np, f"{_cop(True, negated, hedge)} {pp}{by}"
        return x_np, f"{_cop(False, negated, hedge)} {_es_pp(v, x_fem)}{by}"

    # C: oblique role of the definiendum -> the other participant is the subject
    subj_np = f_np if (f and r1 == subj_role) else SUBJ_PLACEHOLDER[lang]
    p = PREP[lang].get(r0, "")
    xo = x_np
    plural = bool(f) and r1 == subj_role and (prop.quant in ("m", "s", "p", "i") or (prop.quant.isdigit() and prop.quant != "1"))
    if en:
        s3, _ = _en_forms(v)
        if plural:  # "Many humans live in a town."
            vp = (f"{hedge} do not {v}" if hedge and hedge not in NEVER else ("never " + v if hedge else f"do not {v}")) \
                if negated else (f"{hedge} {v}" if hedge else v)
        else:
            vp = _vp(True, negated, hedge, v, s3)
        return subj_np, f"{vp} {p} {xo}".replace("  ", " ")
    vp = _vp(False, negated, hedge, v, _es_3pl(v) if plural else _es_3sg(v))
    return subj_np, f"{vp} {p} {xo}".replace("  ", " ")


def sentence(kb: KnowledgeBase, x: str, prop: Prop, *, negated: bool = False, lang: str = "en",
             hedge: str | None = None, subject: str | None = None) -> str | None:
    d = describe(kb, x, prop, negated=negated, lang=lang, hedge=hedge, subject=subject)
    if d is None:
        return None
    s, p = d
    out = f"{s[0].upper()}{s[1:]} {p}."
    return _es_contract(out) if lang == "es" else out


def _es_contract(text: str) -> str:
    import re

    return re.sub(r"\b([aA]|[dD]e) el\b", lambda m: {"a": "al", "A": "Al", "de": "del", "De": "Del"}[m.group(1)], text)


def relative(kb: KnowledgeBase, f: str, prop: Prop, lang: str = "en") -> str | None:
    """'something that <predicate>' for filler f, only when f is the subject (cases A/B)."""
    if prop.self_role not in CORE and prop.self_role != (prop.subj_role or prop.self_role):
        return None
    d = describe(kb, f, prop, lang=lang, subject=SUBJ_PLACEHOLDER[lang])
    if d is None or d[0] != SUBJ_PLACEHOLDER[lang]:
        return None
    return f"{SUBJ_PLACEHOLDER[lang]} {'that' if lang == 'en' else 'que'} {d[1]}"

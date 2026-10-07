"""Build the toy KB used by the tests and the dry-run pipeline.

ILLUSTRATIVE DATA ONLY. The BIRD and OSTRICH postulates follow Table 3-6 of the
thesis (Arcas Túnez, 2008); every other concept, postulate, frame and script is a
simplified stand-in written for testing. Never report results obtained on it.
"""

import json
from pathlib import Path

C = []


def c(cid, parents, stype, mp=None, frame=None, en="", es=""):
    C.append({
        "id": cid, "parents": parents, "semantic_type": stype,
        "meaning_postulate": mp, "thematic_frame": frame,
        "glosses": {k: v for k, v in (("en", en), ("es", es)) if v},
    })


# metaconcepts
c("#ENTITY", [], "entity"); c("#PHYSICAL", ["#ENTITY"], "entity")
c("#OBJECT", ["#PHYSICAL"], "entity"); c("#SELF_CONNECTED_OBJECT", ["#OBJECT"], "entity")
c("#GROUP", ["#ENTITY"], "entity")
c("#EVENT", [], "event"); c("#MOTION", ["#EVENT"], "event"); c("#STATIVE", ["#EVENT"], "event")
c("#QUALITY", [], "quality")

# entities
c("+ANIMAL_00", ["#SELF_CONNECTED_OBJECT"], "entity",
  "*(e1: +MOVE_00 (x1)Agent (x1)Theme) +(e2: +EAT_00 (x1)Agent (x2: +FOOD_00)Theme)")
c("+VERTEBRATE_00", ["+ANIMAL_00"], "entity",
  "+(e1: +COMPRISE_00 (x1)Theme (x2: +BONE_00)Referent)")
c("+BIRD_00", ["+VERTEBRATE_00"], "entity",
  "+(e1: +BE_00 (x1: +BIRD_00)Theme (x2: +VERTEBRATE_00)Referent) "
  "*(e2: +COMPRISE_00 (x1)Theme (x3: m +FEATHER_00 & 2 +LEG_00 & 2 +WING_00)Referent) "
  "*(e3: +FLY_00 (x1)Agent (x1)Theme (x4)Origin (x5)Goal)")
c("$OSTRICH_00", ["+BIRD_00"], "entity",
  "+(e1: +BE_00 (x1: $OSTRICH_00)Theme (x2: +BIRD_00)Referent) "
  "*(e2: +BE_01 (x1)Theme (x3: +BIG_00)Attribute) "
  "*((e3: +COMPRISE_00 (x1)Theme (x4: 2 +LEG_00 & 1 +NECK_00)Referent) (e4: +BE_01 (x4)Theme (x5: +LONG_00)Attribute)) "
  "+(e9: n +FLY_00 (x1)Agent (x1)Theme (x10)Origin (x11)Goal) "
  "*(e10: +RUN_00 (x1)Agent (x1)Theme (f1: +FAST_00)Speed)")
c("$PENGUIN_00", ["+BIRD_00"], "entity",
  "+(e1: n +FLY_00 (x1)Agent (x1)Theme) *(e2: +SWIM_00 (x1)Agent (x1)Theme)")
c("$SPARROW_00", ["+BIRD_00"], "entity", "*(e1: +BE_01 (x1)Theme (x2: +SMALL_00)Attribute)")
c("+MAMMAL_00", ["+VERTEBRATE_00"], "entity", "+(e1: +COMPRISE_00 (x1)Theme (x2: +HAIR_00)Referent)")
c("+DOG_00", ["+MAMMAL_00"], "entity",
  "*(e1: +COMPRISE_00 (x1)Theme (x2: 4 +LEG_00)Referent) *(e2: +BARK_00 (x1)Agent)")
c("+HUMAN_00", ["+MAMMAL_00"], "entity", "+(e1: +THINK_00 (x1)Agent (x1)Theme) *(e2: +SPEAK_00 (x1)Agent)")
c("$BAT_00", ["+MAMMAL_00"], "entity", "*(e1: +FLY_00 (x1)Agent (x1)Theme)")
for part in ("FEATHER", "LEG", "WING", "NECK", "BONE", "HAIR"):
    c(f"+{part}_00", ["#SELF_CONNECTED_OBJECT"], "entity")
c("+FOOD_00", ["#SELF_CONNECTED_OBJECT"], "entity")
c("+BREAD_00", ["+FOOD_00"], "entity")
c("+STONE_00", ["#SELF_CONNECTED_OBJECT"], "entity", "+(e1: +BE_01 (x1)Theme (x2: +HARD_00)Attribute)")
c("+MONEY_00", ["#OBJECT"], "entity"); c("+RIVER_00", ["#PHYSICAL"], "entity")
c("+RESTAURANT_00", ["#OBJECT"], "entity")
c("+ORGANIZATION_00", ["#GROUP"], "entity")
c("+LAND_00", ["#PHYSICAL"], "entity")
c("+BANK_00", ["+ORGANIZATION_00"], "entity",
  "*(e1: +LEND_00 (x1)Agent (x2: +MONEY_00)Theme (x3: +HUMAN_00)Goal)",
  en="financial institution", es="entidad financiera")
c("+BANK_01", ["+LAND_00"], "entity", "+(e1: +BE_02 (x1)Theme (x2: +RIVER_00)Location)",
  en="land beside a river", es="orilla de un río")

# events (thematic frames carry selection preferences)
c("+BE_00", ["#STATIVE"], "event"); c("+BE_01", ["#STATIVE"], "event"); c("+BE_02", ["#STATIVE"], "event")
c("+COMPRISE_00", ["#STATIVE"], "event")
c("+MOVE_00", ["#MOTION"], "event", frame="(e1: +MOVE_00 (x1)Agent (x2)Theme)")
for ev in ("FLY", "RUN", "SWIM"):
    c(f"+{ev}_00", ["+MOVE_00"], "event", frame=f"(e1: +{ev}_00 (x1: +ANIMAL_00)Agent (x2)Theme)")
c("+EAT_00", ["#EVENT"], "event", frame="(e1: +EAT_00 (x1: +ANIMAL_00)Agent (x2: +FOOD_00)Theme)")
c("+THINK_00", ["#EVENT"], "event", frame="(e1: +THINK_00 (x1: +HUMAN_00)Agent (x2)Theme)")
c("+SPEAK_00", ["#EVENT"], "event", frame="(e1: +SPEAK_00 (x1: +HUMAN_00)Agent)")
c("+BARK_00", ["#EVENT"], "event", frame="(e1: +BARK_00 (x1: +DOG_00)Agent)")
c("+LEND_00", ["#EVENT"], "event",
  frame="(e1: +LEND_00 (x1: +HUMAN_00 | +ORGANIZATION_00)Agent (x2)Theme (x3: +HUMAN_00)Goal)")
for ev in ("ENTER", "SIT", "ORDER", "PAY", "LEAVE"):
    c(f"+{ev}_00", ["#EVENT"], "event")

# qualities
for q in ("BIG", "SMALL", "LONG", "FAST", "HARD"):
    c(f"+{q}_00", ["#QUALITY"], "quality")

LEX = {
    "+ANIMAL_00": ("animal", "animal", "n"), "+VERTEBRATE_00": ("vertebrate", "vertebrado", "n"),
    "+BIRD_00": ("bird", "pájaro", "n"), "$OSTRICH_00": ("ostrich", "avestruz", "n"),
    "$PENGUIN_00": ("penguin", "pingüino", "n"), "$SPARROW_00": ("sparrow", "gorrión", "n"),
    "+MAMMAL_00": ("mammal", "mamífero", "n"), "+DOG_00": ("dog", "perro", "n"),
    "+HUMAN_00": ("human", "humano", "n"), "$BAT_00": ("bat", "murciélago", "n"),
    "+FEATHER_00": ("feather", "pluma", "n"), "+LEG_00": ("leg", "pata", "n"),
    "+WING_00": ("wing", "ala", "n"), "+NECK_00": ("neck", "cuello", "n"),
    "+BONE_00": ("bone", "hueso", "n"), "+HAIR_00": ("hair", "pelo", "n"),
    "+FOOD_00": ("food", "comida", "n"), "+BREAD_00": ("bread", "pan", "n"),
    "+STONE_00": ("stone", "piedra", "n"), "+MONEY_00": ("money", "dinero", "n"),
    "+RIVER_00": ("river", "río", "n"), "+RESTAURANT_00": ("restaurant", "restaurante", "n"),
    "+ORGANIZATION_00": ("organisation", "organización", "n"), "+LAND_00": ("land", "tierra", "n"),
    "+BANK_00": ("bank", "banco", "n"), "+BANK_01": ("bank", "orilla", "n"),
    "+BE_01": ("be", "ser", "v"), "+BE_02": ("be located", "estar", "v"),
    "+COMPRISE_00": ("have", "tener", "v"),
    "+MOVE_00": ("move", "moverse", "v"), "+FLY_00": ("fly", "volar", "v"),
    "+RUN_00": ("run", "correr", "v"), "+SWIM_00": ("swim", "nadar", "v"),
    "+EAT_00": ("eat", "comer", "v"), "+THINK_00": ("think", "pensar", "v"),
    "+SPEAK_00": ("speak", "hablar", "v"), "+BARK_00": ("bark", "ladrar", "v"),
    "+LEND_00": ("lend", "prestar", "v"), "+ENTER_00": ("enter", "entrar", "v"),
    "+SIT_00": ("sit down", "sentarse", "v"), "+ORDER_00": ("order", "pedir", "v"),
    "+PAY_00": ("pay", "pagar", "v"), "+LEAVE_00": ("leave", "salir", "v"),
    "+BIG_00": ("big", "grande", "adj"), "+SMALL_00": ("small", "pequeño", "adj"),
    "+LONG_00": ("long", "largo", "adj"), "+FAST_00": ("fast", "rápido", "adj"),
    "+HARD_00": ("hard", "duro", "adj"),
}
lexicon = []
for cid, (en, es, pos) in LEX.items():
    lexicon.append({"lemma": en, "lang": "en", "pos": pos, "concept": cid})
    lexicon.append({"lemma": es, "lang": "es", "pos": pos, "concept": cid})
lexicon.append({"lemma": "banco", "lang": "es", "pos": "n", "concept": "+BANK_01"})  # deliberate ambiguity

STEPS = [
    ("+ENTER_00", "enter the restaurant", "entrar en el restaurante"),
    ("+SIT_00", "sit down at a table", "sentarse a una mesa"),
    ("+ORDER_00", "order the food", "pedir la comida"),
    ("+EAT_00", "eat the food", "comer la comida"),
    ("+PAY_00", "pay the bill", "pagar la cuenta"),
    ("+LEAVE_00", "leave the restaurant", "salir del restaurante"),
]
scripts = [{
    "id": "EAT_IN_RESTAURANT",
    "name": {"en": "eating in a restaurant", "es": "comer en un restaurante"},
    "participants": ["+HUMAN_00", "+RESTAURANT_00", "+FOOD_00", "+MONEY_00"],
    "steps": [
        {"order": i + 1, "predication": f"(e{i + 1}: {ev} (x1: +HUMAN_00)Agent)", "label": {"en": en, "es": es}}
        for i, (ev, en, es) in enumerate(STEPS)
    ],
    "preconditions": ["+MONEY_00"],
}]

if __name__ == "__main__":
    out = {"version": "toy-0.1", "concepts": C, "lexicon": lexicon, "scripts": scripts, "instances": []}
    Path(__file__).with_name("toy_kb.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(C)} concepts, {len(lexicon)} lexical units")

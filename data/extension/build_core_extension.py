"""Core-concept extension of the FunGramKB export (authored, pending expert validation).

The GlobalCrimeTerm export references 127 basic concepts (in its own postulates) that it does
not define (+DO_00, +USE_00, +COMPUTER_00, +ALCOHOL_00 ...). Without them the reasoner cannot
classify fillers or chain through them. This file defines them following the conventions of
Arcas Túnez (2008, §3.1.7): first predication = strict classification (+BE_00 … Referent),
then defeasible (*) prototypical properties and strict (+) definitional ones.

Every entry carries provenance "authored-2026-10-05" and must be reviewed by a FunGramKB expert
(validation level 1 of the project script). Spanish lemmas are written with correct accents.
Run:  python data/extension/build_core_extension.py   ->  data/extension/core_extension.json
"""

import json
from pathlib import Path

E, V, Q = "entity", "event", "quality"


def c(cid, parent, stype, mp=None, en="", es="", gloss=""):
    return {"id": cid, "parents": [parent], "semantic_type": stype, "meaning_postulate": mp,
            "thematic_frame": None, "glosses": {"en": gloss} if gloss else {},
            "provenance": "authored-2026-10-05", "lemmas": {"en": en, "es": es}}


def isa(cid, parent):
    return f"+(e1: +BE_00 (x1: {cid})Theme (x2: {parent})Referent)"


CORE = [
    # ---------- intermediate entity taxonomy (gives depth for inheritance) ----------
    c("+ORGANISM_00", "#SELF_CONNECTED_OBJECT", E,
      "*(e1: +EXIST_00 (x1)Theme (f1: +LONG_00)Duration) +(e2: +BE_01 (x1)Theme (x2: +ALIVE_00)Attribute)",
      "organism", "organismo", "A living thing."),
    c("+ANIMAL_00", "+ORGANISM_00", E,
      isa("+ANIMAL_00", "+ORGANISM_00") + " *(e2: +MOVE_00 (x1)Agent (x1)Theme (x3)Location (x4)Origin (x5)Goal)"
      " +(e3: +INGEST_00 (x1)Agent (x6: +FOOD_00)Theme)",
      "animal", "animal", "A living being that can move and eats food."),
    c("+PLANT_00", "+ORGANISM_00", E,
      isa("+PLANT_00", "+ORGANISM_00") + " +(e2: n +MOVE_00 (x1)Agent (x1)Theme (x3)Location (x4)Origin (x5)Goal)"
      " *(e3: +GROW_00 (x1)Theme (f1: +SOIL_00)Location)",
      "plant", "planta", "A living thing that grows in the ground."),
    c("+BACTERIA_00", "+ORGANISM_00", E,
      isa("+BACTERIA_00", "+ORGANISM_00") + " +(e2: +BE_01 (x1)Theme (x3: +SMALL_00)Attribute)"
      " *(e3: +CAUSE_00 (x1)Theme (x4: +ILLNESS_00)Referent)",
      "bacteria", "bacteria", "Very small organisms that can cause illness."),
    c("+MAN_00", "+HUMAN_00", E, isa("+MAN_00", "+HUMAN_00") + " +(e2: +BE_01 (x1)Theme (x3: +MALE_00)Attribute)",
      "man", "hombre", "An adult male human."),
    c("+CHILD_00", "+HUMAN_00", E, isa("+CHILD_00", "+HUMAN_00") + " +(e2: +BE_01 (x1)Theme (x3: +YOUNG_00)Attribute)"
      " *(e3: +NEED_00 (x1)Theme (x4: +PROTECTION_00)Referent)",
      "child", "niño", "A young human who needs protection."),
    c("+CUSTOMER_00", "+HUMAN_00", E,
      isa("+CUSTOMER_00", "+HUMAN_00") + " +(e2: +BUY_00 (x1)Agent (x3: +PRODUCT_00)Theme (x4)Origin (x1)Goal)",
      "customer", "cliente", "A person who buys products."),
    c("+ARMY_00", "+GROUP_00", E,
      isa("+ARMY_00", "+GROUP_00") + " +(e2: +COMPRISE_00 (x1)Theme (x3: m +SOLDIER_00)Referent)"
      " *(e3: +DEFEND_00 (x1)Agent (x4: +COUNTRY_00)Theme)",
      "army", "ejército", "A large organised group of soldiers that defends a country."),
    c("+SOLDIER_00", "+HUMAN_00", E, isa("+SOLDIER_00", "+HUMAN_00") + " *(e2: +USE_00 (x1)Theme (x3: +WEAPON_00)Referent)",
      "soldier", "soldado", "A person who serves in an army."),
    c("+GOVERNMENT_00", "+GROUP_00", E,
      isa("+GOVERNMENT_00", "+GROUP_00") + " +(e2: +CONTROL_00 (x1)Theme (x3: +COUNTRY_00)Referent)"
      " +(e3: +CREATE_00 (x1)Theme (x4: m +LAW_00)Referent)",
      "government", "gobierno", "The group of people who control a country and make its laws."),
    c("+COUNTRY_00", "+PLACE_00", E, isa("+COUNTRY_00", "+PLACE_00") + " +(e2: +HAVE_00 (x1)Theme (x3: +GOVERNMENT_00)Referent)",
      "country", "país", "A place with its own government."),
    c("+TOWN_00", "+PLACE_00", E, isa("+TOWN_00", "+PLACE_00") + " +(e2: +COMPRISE_00 (x1)Theme (x3: m +BUILDING_00)Referent)"
      " *(e3: +LIVE_00 (x4: m +HUMAN_00)Theme (x1)Location)",
      "town", "pueblo", "A place with many buildings where people live."),
    c("+COUNTRYSIDE_00", "+PLACE_00", E, isa("+COUNTRYSIDE_00", "+PLACE_00") + " *(e2: +COMPRISE_00 (x1)Theme (x3: m +PLANT_00)Referent)",
      "countryside", "campo", "Land outside towns, with many plants."),
    c("+COAST_00", "+PLACE_00", E, isa("+COAST_00", "+PLACE_00") + " +(e2: +BE_02 (x1)Theme (x3: +SEA_00)Location (f1: +NEAR_00)Position)",
      "coast", "costa", "Land next to the sea."),
    c("+ROAD_00", "+PLACE_00", E, isa("+ROAD_00", "+PLACE_00") + " *(e2: +MOVE_00 (x3: +VEHICLE_00)Agent (x3)Theme (x1)Location (x4)Origin (x5)Goal)",
      "road", "carretera", "A way on which vehicles travel."),
    c("+SKY_00", "+PLACE_00", E, isa("+SKY_00", "+PLACE_00") + " +(e2: +BE_02 (x1)Theme (x3: +EARTH_00)Location (f1: +ABOVE_00)Position)",
      "sky", "cielo", "The space above the earth."),
    c("$FRONTIER_00", "+PLACE_00", E, isa("$FRONTIER_00", "+PLACE_00") + " +(e2: +SEPARATE_00 (x1)Theme (x3: 2 +COUNTRY_00)Referent)",
      "frontier", "frontera", "The line that separates two countries."),
    c("+BUILDING_00", "+ARTEFACT_00", E, isa("+BUILDING_00", "+ARTEFACT_00") + " +(e2: +COMPRISE_00 (x1)Theme (x3: m +WALL_00)Referent)"
      " *(e3: +LIVE_00 (x4: +HUMAN_00)Theme (x1)Location)",
      "building", "edificio", "A structure with walls where people live or work."),
    c("+ARTEFACT_00", "#SELF_CONNECTED_OBJECT", E,
      "+(e1: +CREATE_00 (x2: +HUMAN_00)Theme (x1)Referent) *(e2: +USE_00 (x2)Theme (x1)Referent)",
      "artefact", "artefacto", "An object made by humans."),
    c("+COMPUTER_00", "+ARTEFACT_00", E, isa("+COMPUTER_00", "+ARTEFACT_00") + " +(e2: +STORE_00 (x1)Agent (x3: +INFORMATION_00)Theme)"
      " *(e3: +USE_00 (x4: +HUMAN_00)Theme (x1)Referent (f1: +WORK_00)Purpose)",
      "computer", "ordenador", "An electronic machine that stores information."),
    c("+BOTTLE_00", "+ARTEFACT_00", E, isa("+BOTTLE_00", "+ARTEFACT_00") + " *(e2: +CONTAIN_00 (x1)Theme (x3: +LIQUID_00)Referent)",
      "bottle", "botella", "A container for liquids."),
    c("+CLOTH_00", "+ARTEFACT_00", E, isa("+CLOTH_00", "+ARTEFACT_00") + " *(e2: +BURN_00 (x1)Theme (f1: +EASY_00)Manner)",
      "cloth", "tela", "Material made of woven fibres; it burns easily."),
    c("+WEAPON_00", "+ARTEFACT_00", E, isa("+WEAPON_00", "+ARTEFACT_00") + " +(e2: +USE_00 (x3: +HUMAN_00)Theme (x1)Referent (f1: (e3: +HURT_00 (x3)Agent (x4: +HUMAN_00)Theme))Purpose)",
      "weapon", "arma", "An object used to hurt people."),
    c("+VEHICLE_00", "+ARTEFACT_00", E, isa("+VEHICLE_00", "+ARTEFACT_00") + " +(e2: +TRANSPORT_00 (x1)Agent (x3: +HUMAN_00 | +PRODUCT_00)Theme)",
      "vehicle", "vehículo", "A machine that carries people or goods."),
    c("+PRODUCT_00", "+ARTEFACT_00", E, isa("+PRODUCT_00", "+ARTEFACT_00") + " *(e2: +SELL_00 (x3: +HUMAN_00)Agent (x1)Theme (x3)Origin (x4: +CUSTOMER_00)Goal)",
      "product", "producto", "Something that is made to be sold."),
    c("+SUBSTANCE_CHEM_00", "+SUBSTANCE_00", E, isa("+SUBSTANCE_CHEM_00", "+SUBSTANCE_00"), "chemical", "sustancia química"),
    c("+LIQUID_00", "+SUBSTANCE_00", E, isa("+LIQUID_00", "+SUBSTANCE_00") + " *(e2: +FLOW_00 (x1)Theme)",
      "liquid", "líquido", "A substance that flows."),
    c("+ALCOHOL_00", "+LIQUID_00", E, isa("+ALCOHOL_00", "+LIQUID_00") + " +(e2: +INGEST_00 (x3: +HUMAN_00)Agent (x1)Theme)"
      " *(e3: +CAUSE_00 (x1)Theme (x4: +DRUNK_00)Referent)",
      "alcohol", "alcohol", "A liquid people drink that can make them drunk."),
    c("+PETROL_00", "+LIQUID_00", E, isa("+PETROL_00", "+LIQUID_00") + " +(e2: +BURN_00 (x1)Theme (f1: +EASY_00)Manner)"
      " *(e3: +USE_00 (x3: +VEHICLE_00)Theme (x1)Referent)",
      "petrol", "gasolina", "A liquid fuel for vehicles that burns easily."),
    c("+TOBACCO_00", "+PLANT_00", E, isa("+TOBACCO_00", "+PLANT_00") + " *(e2: +SMOKE_01 (x3: +HUMAN_00)Agent (x1)Theme)"
      " *(e3: +CAUSE_00 (x1)Theme (x4: +ILLNESS_00)Referent)",
      "tobacco", "tabaco", "A plant whose leaves people smoke."),
    c("+METAL_00", "+SUBSTANCE_00", E, isa("+METAL_00", "+SUBSTANCE_00") + " +(e2: +BE_01 (x1)Theme (x3: +HARD_00)Attribute)",
      "metal", "metal", "A hard substance such as iron."),
    c("+BODY_00", "#SELF_CONNECTED_OBJECT", E, "+(e1: +BE_02 (x1)Theme (x2: +ORGANISM_00)Location) +(e2: +COMPRISE_00 (x1)Theme (x3: m +ORGAN_00)Referent)",
      "body", "cuerpo", "The physical structure of an organism."),
    c("+HAND_00", "+BODY_PART_00", E, isa("+HAND_00", "+BODY_PART_00") + " +(e2: +COMPRISE_00 (x1)Theme (x3: 5 +FINGER_00)Referent)"
      " *(e3: +HOLD_00 (x4: +HUMAN_00)Theme (x5)Referent (f1: x1)Instrument)",
      "hand", "mano", "The part of the body at the end of the arm used to hold things."),
    c("+NOSE_00", "+BODY_PART_00", E, isa("+NOSE_00", "+BODY_PART_00") + " *(e2: +SMELL_00 (x3: +ANIMAL_00)Theme (x4)Referent (f1: x1)Means)",
      "nose", "nariz", "The part of the face used to smell."),
    c("+BODY_PART_00", "#SELF_CONNECTED_OBJECT", E, "+(e1: +BE_02 (x1)Theme (x2: +BODY_00)Location (f1: +IN_00)Position)",
      "body part", "parte del cuerpo"),
    c("+ILLNESS_00", "#PROCESS", E, "+(e1: +AFFECT_00 (x1)Theme (x2: +ORGANISM_00)Referent) *(e2: +HURT_00 (x1)Agent (x2)Theme)",
      "illness", "enfermedad", "A state of the body in which an organism is not healthy."),
    c("+FIRE_01", "#PROCESS", E, "+(e1: +BURN_00 (x1)Theme) *(e2: +DAMAGE_00 (x1)Agent (x2: +BUILDING_00 | +PLANT_00)Theme)",
      "fire", "incendio", "Burning that damages things."),
    c("+SOUND_00", "#PROCESS", E, "+(e1: +PERCEIVE_00 (x2: +ANIMAL_00)Theme (x1)Referent (f1: +EAR_00)Means)",
      "sound", "sonido", "Something that is heard."),
    c("+MARK_00", "#SELF_CONNECTED_OBJECT", E, "+(e1: +BE_02 (x1)Theme (x2: +SURFACE_00)Location (f1: +ON_00)Position) *(e2: +SEE_00 (x3: +HUMAN_00)Theme (x1)Referent)",
      "mark", "marca", "A visible sign on a surface."),
    c("+OCCURRENCE_00", "#PROCESS", E, "+(e1: +HAPPEN_00 (x1)Theme)", "event", "suceso", "Something that happens."),
    c("+CORPUSCULAR_00", "#SELF_CONNECTED_OBJECT", E, "+(e1: +BE_01 (x1)Theme (x2: +SMALL_00)Attribute)", "particle", "partícula"),
    # ---------- abstract entities and propositions ----------
    c("+LAW_00", "#PROPOSITION", E, "+(e1: +CREATE_00 (x2: +GOVERNMENT_00)Theme (x1)Referent) +(e2: +SAY_00 (x1)Theme (x3: (e3: obl +DO_00 (x4: +HUMAN_00)Theme (x5)Referent))Referent)"
      " *(e4: +PUNISH_00 (x2)Agent (x4)Theme (f1: (e5: n +DO_00 (x4)Theme (x5)Referent))Reason)",
      "law", "ley", "A rule made by a government that people must obey."),
    c("+CUSTOM_00", "#PROPOSITION", E, "*(e1: +DO_00 (x2: m +HUMAN_00)Theme (x1)Referent (f1: +AGAIN_00)Frequency)",
      "custom", "costumbre", "Something people usually do."),
    c("+PLAN_00", "#PROPOSITION", E, "+(e1: +THINK_00 (x2: +HUMAN_00)Theme (x1)Referent) *(e2: fut +DO_00 (x2)Theme (x1)Referent)",
      "plan", "plan", "Something a person thinks about doing in the future."),
    c("+THOUGHT_00", "#PROPOSITION", E, "+(e1: +THINK_00 (x2: +HUMAN_00)Theme (x1)Referent)", "thought", "pensamiento"),
    c("+QUESTION_00", "#PROPOSITION", E, "+(e1: +SAY_00 (x2: +HUMAN_00)Theme (x1)Referent (x3: +HUMAN_00)Goal (f1: (e2: +KNOW_00 (x2)Theme (x4: +INFORMATION_00)Referent))Purpose)",
      "question", "pregunta", "Something said to get information."),
    c("+TAX_00", "#ABSTRACT", E, "+(e1: +PAY_00 (x2: +HUMAN_00 | +COMPANY_00)Agent (x3: +MONEY_00)Theme (x2)Origin (x4: +GOVERNMENT_00)Goal) +(e2: +BE_01 (x1)Theme (x5: +LEGAL_00)Attribute)",
      "tax", "impuesto", "Money that people must pay to the government."),
    c("+MONEY_00", "#SELF_CONNECTED_OBJECT", E, "+(e1: +USE_00 (x2: +HUMAN_00)Theme (x1)Referent (f1: (e2: +BUY_00 (x2)Agent (x3: +PRODUCT_00)Theme))Purpose)",
      "money", "dinero", "What people use to buy things."),
    c("+COMPANY_00", "+GROUP_00", E, isa("+COMPANY_00", "+GROUP_00") + " *(e2: +SELL_00 (x1)Agent (x3: +PRODUCT_00)Theme (x1)Origin (x4: +CUSTOMER_00)Goal)",
      "company", "empresa", "An organisation that sells products."),
    c("+HATRED_00", "#PSYCHOLOGICAL", E, "+(e1: +FEEL_00 (x2)Agent (x3: +HUMAN_00)Theme (x1)Attribute) *(e2: +CAUSE_00 (x1)Theme (x4: +VIOLENCE_00)Referent)",
      "hatred", "odio", "A strong feeling against someone that can cause violence."),
    c("+FEAR_00", "#PSYCHOLOGICAL", E, "+(e1: +FEEL_00 (x2)Agent (x3: +ANIMAL_00)Theme (x1)Attribute) *(e2: +ESCAPE_00 (x3)Agent (x3)Theme (x4)Origin (x5)Goal)",
      "fear", "miedo", "The feeling caused by danger; it makes animals escape."),
    c("+STRENGTH_00", "#ATTRIBUTE", E, "+(e1: +BE_01 (x2: +ORGANISM_00)Theme (x3: +STRONG_00)Attribute)", "strength", "fuerza"),
    c("+SEX_00", "#PROCESS", E, "+(e1: +DO_00 (x2: 2 +HUMAN_00 | 2 +ANIMAL_00)Theme (x1)Referent)", "sex", "sexo"),
    c("+PERIOD_00", "#TIME", E, "+(e1: +BE_01 (x1)Theme (x2: +LONG_01)Attribute)", "period", "periodo"),
    c("+DAMAGE_01", "#PROCESS", E, "+(e1: +BECOME_00 (x2)Theme (x3: +BAD_00)Attribute)", "damage", "daño"),
    # ---------- qualities ----------
    c("+LEGAL_00", "#SOCIAL_", Q, "*(e1: +BE_01 (x2)Theme (x1)Attribute) +(e2: +ALLOW_00 (x3: +LAW_00)Theme (x2)Referent)",
      "legal", "legal", "Allowed by the law."),
    c("$LEGAL_N_00", "+LEGAL_00", Q, "+(e1: n +BE_01 (x2)Theme (x3: +LEGAL_00)Attribute)", "illegal", "ilegal", "Not allowed by the law."),
    c("+SECRET_00", "#SOCIAL_", Q, "+(e1: n +KNOW_00 (x2: m +HUMAN_00)Theme (x3)Referent)", "secret", "secreto", "Not known by most people."),
    c("+VIOLENT_00", "#BEHAVIOURAL", Q, "+(e1: +USE_00 (x2: +HUMAN_00)Theme (x3: +STRENGTH_00)Referent (f1: (e2: +HURT_00 (x2)Agent (x4: +ORGANISM_00)Theme))Purpose)",
      "violent", "violento", "Using force to hurt someone."),
    c("+SMALL_00", "#PHYSICAL_", Q, "*(e1: +BE_01 (x2)Theme (x1)Attribute) +(e2: +BE_01 (x2)Theme (x3: +SIZE_00)Referent) +(e3: n +BE_01 (x2)Theme (x4: +BIG_00)Attribute)",
      "small", "pequeño"),
    c("+BIG_00", "#PHYSICAL_", Q, "*(e1: +BE_01 (x2)Theme (x1)Attribute) +(e2: +BE_01 (x2)Theme (x3: +SIZE_00)Referent)", "big", "grande"),
    c("+LONG_00", "#PHYSICAL_", Q, "*(e1: +BE_01 (x2)Theme (x1)Attribute) +(e2: +BE_01 (x2)Theme (x3: +LENGTH_00)Referent)", "long", "largo"),
    c("+LONG_01", "#TEMPORAL", Q, "*(e1: +LAST_00 (x2: +OCCURRENCE_00)Theme (f1: m +TIME_00)Duration)", "long (time)", "largo (tiempo)"),
    c("+LITTLE_00", "#QUANTITATIVE", Q, "+(e1: +BE_01 (x2)Theme (x3: p +QUANTITY_00)Attribute)", "little", "poco"),
    c("+STRONG_00", "#PHYSICAL_", Q, "+(e1: +HAVE_00 (x2: +ORGANISM_00)Theme (x3: m +STRENGTH_00)Referent)", "strong", "fuerte"),
    c("+CALM_00", "#PSYCHOLOGICAL_", Q, "+(e1: n +FEEL_00 (x2)Agent (x3: +HUMAN_00)Theme (x4: +FEAR_00 | +ANGRY_00)Attribute)", "calm", "tranquilo"),
    c("+EASY_00", "#PSYCHOLOGICAL_", Q, "+(e1: n +NEED_00 (x2: +OCCURRENCE_00)Theme (x3: m +EFFORT_00)Referent)", "easy", "fácil"),
    c("+IN_00", "#SPATIAL", Q, "+(e1: +BE_02 (x2)Theme (x3)Location (f1: x1)Position)", "in", "dentro"),
    c("+ON_00", "#SPATIAL", Q, "+(e1: +BE_02 (x2)Theme (x3: +SURFACE_00)Location (f1: x1)Position)", "on", "encima"),
    c("+NEAR_00", "#SPATIAL", Q, "+(e1: n +BE_01 (x2)Theme (x3: +FAR_00)Attribute)", "near", "cerca"),
    c("+AGAIN_00", "#TEMPORAL", Q, "+(e1: +HAPPEN_00 (x2: +OCCURRENCE_00)Theme (f1: 2 +TIME_00)Frequency)", "again", "otra vez"),
]

# Events: parent metaconcept + optional postulate (thematic frame comes from the metaconcept schema).
EVENTS = {
    "#MATERIAL": "DO USE ATTACK CREATE BURST SHOOT STOP PROTECT DEFEND CULTIVATE INCREASE CONTROL BUILD HELP HURT INFECT DAMAGE_00 KILL WORK HOLD ABSORB SUCCEED THROW",
    "#TRANSFER": "GIVE TAKE_01 SELL TAKE_00 TRANSFER PAY PUT LEND",
    "#MOTION": "LEAVE ESCAPE ENTER TRAVEL_01 MOVE JOIN",
    "#COMMUNICATION": "SAY COMMAND THREATEN SHOW REQUEST_01 DEMONSTRATE DESCRIBE WRITE",
    "#COGNITION": "THINK CHOOSE KNOW DECEIVE",
    "#PERCEPTION": "WATCH EXAMINE LISTEN PERCEIVE FIND SEARCH",
    "#EMOTION": "FEEL",
    "#POSSESSION": "HAVE",
    "#CONSTITUTION": "COMPRISE",
    "#EXISTENCE": "EXIST REST SLEEP",
    "#IDENTIFICATION": "BE_01",
    "#LOCATION": "BE_02 HIDE",
    "#TRANSFORMATION": "SMOKE_01 INGEST EAT PUNISH",
}
EVENT_LEMMAS = {
    "DO": ("do", "hacer"), "USE": ("use", "usar"), "ATTACK": ("attack", "atacar"), "CREATE": ("create", "crear"),
    "BURST": ("burst", "estallar"), "SHOOT": ("shoot", "disparar"), "STOP": ("stop", "detener"),
    "PROTECT": ("protect", "proteger"), "DEFEND": ("defend", "defender"), "CULTIVATE": ("cultivate", "cultivar"),
    "INCREASE": ("increase", "aumentar"), "CONTROL": ("control", "controlar"), "BUILD": ("build", "construir"),
    "HELP": ("help", "ayudar"), "HURT": ("hurt", "herir"), "INFECT": ("infect", "infectar"),
    "DAMAGE_00": ("damage", "dañar"), "KILL": ("kill", "matar"), "WORK": ("work", "trabajar"), "HOLD": ("hold", "sujetar"),
    "ABSORB": ("absorb", "absorber"), "SUCCEED": ("succeed", "lograr"), "THROW": ("throw", "lanzar"),
    "GIVE": ("give", "dar"), "TAKE_01": ("take", "tomar"), "SELL": ("sell", "vender"), "TAKE_00": ("take away", "llevarse"),
    "TRANSFER": ("transfer", "transferir"), "PAY": ("pay", "pagar"), "PUT": ("put", "poner"), "LEND": ("lend", "prestar"),
    "LEAVE": ("leave", "salir"), "ESCAPE": ("escape", "escapar"), "ENTER": ("enter", "entrar"), "TRAVEL_01": ("travel", "viajar"),
    "MOVE": ("move", "moverse"), "JOIN": ("join", "unirse"), "SAY": ("say", "decir"), "COMMAND": ("order", "ordenar"),
    "THREATEN": ("threaten", "amenazar"), "SHOW": ("show", "mostrar"), "REQUEST_01": ("request", "solicitar"),
    "DEMONSTRATE": ("demonstrate", "manifestarse"), "DESCRIBE": ("describe", "describir"), "WRITE": ("write", "escribir"),
    "THINK": ("think", "pensar"), "CHOOSE": ("choose", "elegir"), "KNOW": ("know", "saber"), "DECEIVE": ("deceive", "engañar"),
    "WATCH": ("watch", "vigilar"), "EXAMINE": ("examine", "examinar"), "LISTEN": ("listen", "escuchar"),
    "PERCEIVE": ("perceive", "percibir"), "FIND": ("find", "encontrar"), "SEARCH": ("search", "buscar"),
    "FEEL": ("feel", "sentir"), "HAVE": ("have", "tener"), "COMPRISE": ("comprise", "constar de"), "EXIST": ("exist", "existir"),
    "REST": ("rest", "descansar"), "SLEEP": ("sleep", "dormir"), "BE_01": ("be", "ser"), "BE_02": ("be located", "estar"),
    "HIDE": ("hide", "esconder"), "SMOKE_01": ("smoke", "fumar"), "INGEST": ("ingest", "ingerir"), "EAT": ("eat", "comer"),
    "PUNISH": ("punish", "castigar"),
}
EVENT_MP = {
    "+SELL_00": "+(e1: +GIVE_00 (x1)Agent (x2)Theme (x3)Origin (x4)Goal (f1: (e2: +PAY_00 (x4)Agent (x5: +MONEY_00)Theme (x4)Origin (x1)Goal))Condition)",
    "+KILL_00": "+(e1: +DO_00 (x1)Theme (x2)Referent (f1: (e2: +DIE_00 (x3: +ORGANISM_00)Theme))Result)",
    "+EAT_00": "+(e1: +INGEST_00 (x1: +ANIMAL_00)Agent (x2: +FOOD_00)Theme)",
    "+PUNISH_00": "+(e1: +DO_00 (x1: +HUMAN_00 | +GOVERNMENT_00)Theme (x2)Referent (f1: (e2: past +DO_00 (x3: +HUMAN_00)Theme (x4: +CRIME_00)Referent))Reason)",
    "+LEND_00": "+(e1: +GIVE_00 (x1)Agent (x2)Theme (x1)Origin (x3)Goal (f1: (e2: fut +GIVE_00 (x3)Agent (x2)Theme (x3)Origin (x1)Goal))Condition)",
}
for meta, names in EVENTS.items():
    for n in names.split():
        cid = f"+{n}" if n[-3:-2] == "_" and n[-2:].isdigit() else f"+{n}_00"
        en, es = EVENT_LEMMAS.get(n, (n.lower(), ""))
        CORE.append(c(cid, meta, V, EVENT_MP.get(cid), en, es))

if __name__ == "__main__":
    out = Path(__file__).with_name("core_extension.json")
    out.write_text(json.dumps(CORE, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(CORE)} authored concepts -> {out}")

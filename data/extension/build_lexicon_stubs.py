"""Lemma stubs (authored 2026-10-05, pending validation).

(1) Concepts referenced by postulates but undefined anywhere: minimal concept entries with a
    metaconcept parent and EN/ES lemmas, so items can be verbalised. No postulate is invented.
(2) Missing EN/ES lemmas for exported concepts.
"""
import json
from pathlib import Path

STUBS = {  # id: (type, parent, en, es)
    "+ABOVE_00": ("quality", "#SPATIAL", "above", "encima"), "+AFFECT_00": ("event", "#MATERIAL", "affect", "afectar"),
    "+ALIVE_00": ("quality", "#PHYSICAL_", "alive", "vivo"), "+BURN_00": ("event", "#TRANSFORMATION", "burn", "arder"),
    "+BUY_00": ("event", "#TRANSFER", "buy", "comprar"), "+CAUSE_00": ("event", "#MATERIAL", "cause", "causar"),
    "+CONTAIN_00": ("event", "#CONSTITUTION", "contain", "contener"), "+DRUNK_00": ("quality", "#PHYSICAL_", "drunk", "borracho"),
    "+EARTH_00": ("entity", "#SELF_CONNECTED_OBJECT", "earth", "tierra"), "+EAR_00": ("entity", "#SELF_CONNECTED_OBJECT", "ear", "oído"),
    "+FINGER_00": ("entity", "#SELF_CONNECTED_OBJECT", "finger", "dedo"), "+FLOW_00": ("event", "#MOTION", "flow", "fluir"),
    "+FOOD_00": ("entity", "#SELF_CONNECTED_OBJECT", "food", "comida"), "+GROW_00": ("event", "#TRANSFORMATION", "grow", "crecer"),
    "+HAPPEN_00": ("event", "#EXISTENCE", "happen", "ocurrir"), "+HARD_00": ("quality", "#PHYSICAL_", "hard", "duro"),
    "+LIVE_00": ("event", "#LOCATION", "live", "vivir"), "+MALE_00": ("quality", "#PHYSICAL_", "male", "varón"),
    "+NEED_00": ("event", "#POSSESSION", "need", "necesitar"), "+OBTAIN_00": ("event", "#TRANSFER", "obtain", "obtener"),
    "+ORGAN_00": ("entity", "#SELF_CONNECTED_OBJECT", "organ", "órgano"), "+SEA_00": ("entity", "#REGION", "sea", "mar"),
    "+SEE_00": ("event", "#PERCEPTION", "see", "ver"), "+SEPARATE_00": ("event", "#MATERIAL", "separate", "separar"),
    "+SOIL_00": ("entity", "#MATERIAL", "soil", "suelo"), "+STORE_00": ("event", "#POSSESSION", "store", "almacenar"),
    "+SURFACE_00": ("entity", "#SELF_CONNECTED_OBJECT", "surface", "superficie"), "+TRANSPORT_00": ("event", "#TRANSFER", "transport", "transportar"),
    "+WALL_00": ("entity", "#SELF_CONNECTED_OBJECT", "wall", "pared"), "+YOUNG_00": ("quality", "#PHYSICAL_", "young", "joven"),
    "+STEAL_00": ("event", "#TRANSFER", "steal", "robar"), "+DIE_00": ("event", "#EXISTENCE", "die", "morir"),
    "+CRIME_00": ("entity", "#ABSTRACT", "crime", "delito"), "+VIOLENCE_00": ("entity", "#ABSTRACT", "violence", "violencia"),
    "+PROTECTION_00": ("entity", "#ABSTRACT", "protection", "protección"), "+INFORMATION_00": ("entity", "#PROPOSITION", "information", "información"),
}
LEMMAS = {  # existing concepts: lang -> lemma
    "$ALTERNATIVE_REMITTANCE_00": {"es": "remesa alternativa"}, "$CUCKOO_SMURFING_00": {"es": "pitufeo cuco"},
    "$LAYERING_00": {"es": "estratificación"}, "$PHARMING_00": {"es": "pharming"}, "$PHISHING_00": {"es": "phishing"},
    "$VISHING_00": {"es": "vishing"}, "+WEAPON_00": {"es": "arma"}, "$WATERBOARDING_00": {"es": "ahogamiento simulado"},
    "+ACCESSORY_OFFENCE_00": {"es": "delito accesorio"}, "+ANTITRAFFICKING_00": {"es": "lucha contra la trata"},
    "+ARTIFICIAL_AREA_00": {"en": "artificial area", "es": "área artificial"}, "+ART_THEFT_00": {"es": "robo de arte"},
    "+ART_TRAFFICKING_00": {"es": "tráfico de arte"}, "+BULK_CASH_SMUGGLING_00": {"es": "contrabando de efectivo"},
    "+BUTTLEGGER_00": {"en": "bootlegger", "es": "contrabandista de alcohol"}, "+CHILD_ABUSE_00": {"es": "maltrato infantil"},
    "+CLANDESTINE_00": {"en": "clandestine", "es": "clandestino"}, "+CONTROL_ORDER_00": {"es": "orden de control"},
    "+CURTAIN_SLASHING_00": {"es": "robo con corte de lona"}, "+IDENTITY_THEFT_00": {"es": "robo de identidad"},
    "+JEWELRY_THEFT_00": {"es": "robo de joyas"}, "+MARKET_MANIPULATION_00": {"en": "market manipulation", "es": "manipulación del mercado"},
    "+MOTOR_VEHICLE_THEFT_00": {"es": "robo de vehículos"}, "+ORIENTED_CLUSTER_00": {"es": "grupo orientado"},
    "+OUTLAW_00": {"en": "outlaw", "es": "proscribir"}, "+POINT_SHAVING_00": {"es": "amaño de puntos"},
    "+PRESUMPTION_OF_INNOCENCE_00": {"en": "presumption of innocence", "es": "presunción de inocencia"},
    "+Q_FEVER_00": {"es": "fiebre Q"}, "+SCIENTER_00": {"en": "scienter", "es": "conocimiento doloso"},
    "+TARGETED_KILLING_00": {"es": "asesinato selectivo"},
}
if __name__ == "__main__":
    concepts = [{"id": k, "parents": [p], "semantic_type": t, "meaning_postulate": None, "thematic_frame": None,
                 "glosses": {}, "provenance": "stub-lemma-only-2026-10-05", "lemmas": {"en": en, "es": es}}
                for k, (t, p, en, es) in STUBS.items()]
    out = Path(__file__).with_name("lexicon_stubs.json")
    out.write_text(json.dumps({"concepts": concepts, "lemmas": LEMMAS}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(len(concepts), "stubs,", len(LEMMAS), "lemma additions")

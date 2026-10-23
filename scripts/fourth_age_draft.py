"""Write the provisional Fourth Age scenario (draft data; names from the vault, numbers placeholders)."""
import json
from pathlib import Path

ROOT = Path("src/renasci/renascita")
ROOT.mkdir(parents=True, exist_ok=True)

HOUSES = ["Medani", "Tharashk", "Vadalis", "Jorasco", "Silverhand", "Cannith", "Orien", "Sivis", "Deneith",
          "Phiarlan", "Lyrandar", "Kundarak"]
# (id, name, province, masses, commoners); provinces from the city notes' "Province" sections
CITIES = [("v:lions-rest", "Lion’s Rest", "v:ashen-plains", 4000, 60),
          ("v:lux-oescus", "Lux Oescus", "v:ashen-plains", 1500, 30),
          ("v:port-ardere", "Port Ardere", "v:ashen-plains", 1500, 30),
          ("v:magnus-rest", "Magnus’ Rest", "v:ashen-plains", 800, 20),  # province not in the vault: draft
          ("v:old-westgate", "Old Westgate", "v:ember-peaks", 1000, 25),
          ("v:raining-bay", "Raining Bay", "v:flame-coast", 1000, 25)]

human = {"f": [0.05, 0.006, 0.004, 0.006, 0.009, 0.01, 0.011, 0.012, 0.013, 0.016, 0.02, 0.026, 0.035, 0.05,
               0.07, 0.1, 0.15, 0.22, 0.3, 0.45],
         "m": [0.055, 0.006, 0.005, 0.008, 0.01, 0.011, 0.012, 0.013, 0.015, 0.018, 0.022, 0.03, 0.04, 0.055,
               0.08, 0.11, 0.16, 0.24, 0.32, 0.47]}
leonin = {sex: [round(q * 0.85, 4) for q in qs] for sex, qs in human.items()}  # draft: a little hardier
fertility = [0, 0, 0, 0.15, 0.3, 0.3, 0.25, 0.2, 0.12, 0.04] + [0] * 10
dwarf = {sex: [round(q * 0.6, 4) for q in qs] for sex, qs in human.items()}  # draft: long-lived
RACES = [
    {"id": "r:leonin", "mortality": leonin, "fertility": fertility, "fertile": [16, 45], "spacing_days": 540,
     "marriage": [16, 60], "twins": 0.02, "male": 0.5,
     "names": {"f": ["Ama", "Bessa", "Cyra", "Daia", "Erin", "Fera", "Hela", "Ira", "Kesh", "Lyra"],
               "m": ["Arn", "Brak", "Cass", "Dorn", "Eron", "Garr", "Hask", "Ivo", "Kael", "Lorn"]}},
    {"id": "r:human", "mortality": human, "fertility": fertility, "fertile": [16, 45], "spacing_days": 540,
     "marriage": [16, 60], "twins": 0.012, "male": 0.51,
     "names": {"f": ["Alys", "Bryn", "Cara", "Della", "Edda", "Fen", "Gwen", "Hild", "Isa", "Jo"],
               "m": ["Alder", "Bram", "Cole", "Dain", "Ewan", "Finn", "Gareth", "Hugh", "Ivor", "Jory"]}},
    {"id": "r:dwarf", "mortality": dwarf,
     "fertility": [0, 0, 0, 0, 0.12, 0.15, 0.15, 0.15, 0.12, 0.1, 0.08, 0.05, 0.02] + [0] * 7,
     "fertile": [20, 64], "spacing_days": 900, "marriage": [20, 90], "twins": 0.005, "male": 0.52,
     "names": {"f": ["Aud", "Brenna", "Dagny", "Edda", "Frida", "Gunna", "Hild", "Ingrid"],
               "m": ["Bardin", "Dorrek", "Grimm", "Harn", "Korin", "Morgrim", "Thrain", "Ulf"]}}]
# The vault: Leonin at Lion's Rest, the Flamebound Dwarves at Magnus' Rest; humans elsewhere (draft).
RACE_OF = {"v:lions-rest": "r:leonin", "v:magnus-rest": "r:dwarf"}
# The vault's city notes name these seats; Cannith has none there, so it stays at the capital (draft).
SEATS = {"Deneith": "v:lions-rest", "Jorasco": "v:lions-rest", "Medani": "v:lions-rest", "Silverhand": "v:lions-rest",
         "Tharashk": "v:lions-rest", "Cannith": "v:lions-rest", "Kundarak": "v:lux-oescus", "Sivis": "v:lux-oescus",
         "Vadalis": "v:old-westgate", "Orien": "v:port-ardere", "Lyrandar": "v:raining-bay",
         "Phiarlan": "v:raining-bay"}


def dominant(lid, variants, trait, values, freqs):
    return ({"id": lid, "variants": variants, "model": "dominant", "order": variants, "mutation": 0.00001,
             "traits": {trait: dict(zip(variants, values))}}, freqs)


def additive(lid, trait, effect, plus):
    return ({"id": lid, "variants": ["+", "-"], "model": "additive", "mutation": 0.00001,
             "traits": {trait: {"+": effect, "-": -effect}}}, {"+": plus, "-": round(1 - plus, 4)})


# Q1 on the review queue: a provisional, generic trait set until the lore names its own.
loci = [
    dominant("eye", ["brown", "amber", "grey", "blue"], "eye", [0, 0.33, 0.66, 1],
             {"brown": 0.5, "amber": 0.25, "grey": 0.15, "blue": 0.1}),
    dominant("hair", ["black", "brown", "red", "fair"], "hair", [0, 0.33, 0.66, 1],
             {"black": 0.35, "brown": 0.4, "red": 0.1, "fair": 0.15}),
    additive("stature1", "stature", 0.08, 0.5), additive("stature2", "stature", 0.08, 0.5),
    additive("build", "build", 0.15, 0.5),
    additive("constitution", "constitution", 0.15, 0.55), additive("longevity", "longevity", 0.12, 0.5),
    additive("fertility", "fertility", 0.12, 0.5), additive("wits", "wits", 0.15, 0.5),
    additive("charm", "charm", 0.15, 0.5), additive("will", "will", 0.15, 0.5), additive("temper", "temper", 0.15, 0.5),
    ({"id": "gift", "variants": ["g", "n"], "model": "threshold", "threshold": 2, "mutation": 0.00001,
      "traits": {"gift": {"g": 1, "n": 0}}}, {"g": 0.12, "n": 0.88}),
]
catalogue = {
    "loci": [lo for lo, _ in loci],
    "groups": {"pyrosia": {lo["id"]: f for lo, f in loci}},
    "traits": {"eye": {"base": 0}, "hair": {"base": 0}, "gift": {"base": 0},
               **{t: {"base": 0.5, "range": [0, 1]} for t in
                  ("stature", "build", "constitution", "longevity", "fertility", "wits", "charm", "will", "temper")}},
}

regions: dict = {}
settlements = []
for sid, name, region, masses, commoners in CITIES:
    regions.setdefault(region, []).append(sid)
    settlements.append({"id": sid, "name": name, "region": region,
                        "race": RACE_OF.get(sid, "r:human"), "genome_group": "pyrosia",
                        "masses": masses, "commoners": commoners, "capacity": 3 * (masses + commoners),
                        "notable_target": commoners, "danger": 0.0})

scenario = {
    "draft": True,
    "geography": "pyrosia.json",  # scripts/pyrosia_draft.py (S4, #76)
    "about": ("PROVISIONAL Fourth Age scenario for 4A 1 (#73). Names come from the vault (the 12 Great Houses; "
              "Pyrosia's cities and provinces); every number is a placeholder, and none of it is canon. "
              "Open questions are on the review queue (#150)."),
    "start": [4, 1, 0],
    "params": {"house_from": "father", "residence": "husband", "kin_degree": 2, "market_rate": 0.35,
               "traits": {"wits": "wits", "charm": "charm", "temper": "temper"}},
    "races": RACES,
    "catalogue": catalogue,
    "regions": regions,
    "settlements": settlements,
    "houses": [{"id": f"v:house-{h.lower()}", "name": h, "seat": SEATS[h], "rank": 1,
                "rule": "male_preference_primogeniture"} for h in HOUSES],
}
(ROOT / "fourth_age.json").write_text(json.dumps(scenario, indent=1, ensure_ascii=False) +"\n", encoding="utf-8")
print("written", len(settlements), "settlements,", len(scenario["houses"]), "houses")

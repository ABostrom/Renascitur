"""The paraphrase table of the canon-check benchmark (S12 spec §4): claims rendered as sentences, in
several voices, date forms, clause orders and placings of "of House H". The extractor
(`renasci.story.prose`) never imports this module, so the benchmark doesn't grade it on its own phrasings.

`render(kind, slots, variant)`: `slots` holds the people (already qualified: "Cara of House Kundarak"),
the date (age abbreviation, age name, year) and the like; `variant` picks the phrasing, deterministically.
"""

from __future__ import annotations

SENTENCES = {
    "killed": ["{by} killed {victim}{when}.", "{When}{victim} was slain by {by}.", "{victim} died at the hands of {by}{when}.",
               "{When}{by} struck down {victim}.", "{victim} was murdered by {by}{when}.", "{When}{by} did away with {victim}."],
    "died_in": ["{who} died{when}.", "{When}{who} passed away.", "{who} perished{when}.", "{When}{who} died."],
    "married": ["{a} married {b}.", "{a} and {b} were married.", "{a} wed {b}.", "{a} took {b} as spouse.",
                "{a} was wed to {b}."],
    "alive_at": ["{When}{who} {act}.", "{who} {act}{when}."],
    "ruled": ["{who} became head of {house}{when}.", "{When}{who} took the headship of {house}.",
              "{When}{who} became the head of {house}."],
}
ACTS = ["spoke before the guild", "signed a trade pact", "paid the tithe", "swore an oath to the house",
        "bought a string of mules", "argued with the tax collector", "built a new hall"]
TRAILING = [" in {ab} {y}", " in the year {y} of the {age}", " in the {ord} year of the {age}"]
LEADING = ["In {ab} {y}, ", "In the year {y} of the {age}, ", "In the {ord} year of the {age}, ", "In {ab} {y} "]
HOUSE_FIRST = ["{n} of House {h}", "{n}, of House {h},", "{n} (House {h})", "House {h}'s {n}"]
HOUSE_LATER = ["{n} of House {h}", "{n} (House {h})"]


def _ord(y: int) -> str:
    return f"{y}{'th' if 10 <= y % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(y % 10, 'th')}"


def person(name: str, house: str | None, town: str | None, variant: int, first: bool) -> str:
    if house:
        forms = HOUSE_FIRST if first else HOUSE_LATER
        return forms[variant % len(forms)].format(n=name, h=house)
    return f"{name} of {town}"


def render(kind: str, slots: dict, variant: int) -> str:
    t = SENTENCES[kind][variant % len(SENTENCES[kind])]
    date = slots.get("date")
    when = When = ""
    if date:
        d = {"ab": date[0], "age": date[1], "y": date[2], "ord": _ord(date[2])}
        when = TRAILING[(variant // 3) % len(TRAILING)].format(**d)
        When = LEADING[(variant // 5) % len(LEADING)].format(**d)
    text = t.format(when=when, When=When, act=ACTS[variant % len(ACTS)], **{k: v for k, v in slots.items() if k != "date"})
    text = text.replace(",,", ",").replace(", .", ".").replace(",.", ".")
    return text[0].upper() + text[1:]

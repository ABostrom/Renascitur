"""Type-inference rules for the typed-vault initial-pass migration.

ORDER MATTERS: rules are tried in order; first match wins. Patterns are
Python regexes matched against the path relative to docs/, using forward
slashes (e.g. "Realms/Renascita/Geography/Arcturia/Cities/Runehart.md").

Each rule yields:
- `type`: the inferred `type:` value
- `extras`: callable taking the relpath and returning a dict of extra
  frontmatter to merge (e.g. `era:` derived from a parent folder).
  Use `lambda _: {}` for no extras.

The script `00_infer_types.py` walks docs/, applies these rules, and emits
inference_preview.csv for Aaron's review before any file is mutated.
"""

from __future__ import annotations

import re
from typing import Callable, Dict, List, Tuple

Extras = Callable[[str], Dict[str, str]]

# Map from old Age folder name to canonical Age wikilink.
AGE_WIKILINK = {
    "First Age":  "[[Age of the Endless Sun]]",
    "Second Age": "[[Age of Forging]]",
    "Third Age":  "[[Age of Stagnation]]",
    "Fourth Age": "[[Age of Night]]",
    # Already-renamed forms (idempotency)
    "Age of the Endless Sun": "[[Age of the Endless Sun]]",
    "Age of Forging":         "[[Age of Forging]]",
    "Age of Stagnation":      "[[Age of Stagnation]]",
    "Age of Night":           "[[Age of Night]]",
}


def era_from_history_path(relpath: str) -> Dict[str, str]:
    """Infer `era:` from a History/<age>/... path."""
    parts = relpath.split("/")
    if len(parts) >= 2 and parts[0] == "History":
        age = parts[1]
        link = AGE_WIKILINK.get(age)
        if link:
            return {"era": link}
    return {}


def realm_from_renascita_path(relpath: str) -> Dict[str, str]:
    """For files under Realms/Renascita/Geography/<Continent>/..., add continent."""
    parts = relpath.split("/")
    # Realms / Renascita / Geography / <Continent> / ...
    if len(parts) >= 5 and parts[0] == "Realms" and parts[1] == "Renascita" and parts[2] == "Geography":
        return {"continent": "[[{}]]".format(parts[3])}
    return {}


# Each tuple: (compiled regex, type, extras callable).
# None type means "skip — don't add frontmatter to this file".
RULES: List[Tuple[re.Pattern, str, Extras]] = [
    # ---------- Meta files: skip ----------
    (re.compile(r"^_meta/.*\.md$"), None, lambda _: {}),

    # ---------- Realm-level summary files ----------
    # The realm itself: Realms/Renascita/Renascita.md
    (re.compile(r"^Realms/Renascita/Renascita\.md$"), "continent", lambda _: {}),
    (re.compile(r"^Realms/Renascita/Constellations\.md$"), "essay", lambda _: {}),

    # ---------- Geography: Islands (extra nesting level) ----------
    # Island self-named: Geography/Islands/<Island>/<Island>.md
    (re.compile(r"^Realms/Renascita/Geography/Islands/([^/]+)/\1\.md$"),
     "continent", lambda _: {"kind": "island"}),
    # Locations under an island
    (re.compile(r"^Realms/Renascita/Geography/Islands/([^/]+)/Locations/[^/]+\.md$"),
     "landmark", lambda relpath: {"continent": "[[{}]]".format(relpath.split("/")[4])}),

    # ---------- Geography (most specific first) ----------
    # Continent self-named file: Geography/Arcturia/Arcturia.md
    (re.compile(r"^Realms/Renascita/Geography/([^/]+)/\1\.md$"), "continent", lambda _: {}),

    # Locations inside a city: Geography/.../Cities/<City>/Locations/<X>.md
    (re.compile(r"^Realms/Renascita/Geography/[^/]+/Cities/[^/]+/Locations/[^/]+\.md$"),
     "landmark", realm_from_renascita_path),

    # City self-named file: Geography/.../Cities/<City>/<City>.md
    (re.compile(r"^Realms/Renascita/Geography/[^/]+/Cities/([^/]+)/\1\.md$"),
     "settlement", realm_from_renascita_path),

    # Cities (flat): Geography/.../Cities/<X>.md
    (re.compile(r"^Realms/Renascita/Geography/[^/]+/Cities/[^/]+\.md$"),
     "settlement", realm_from_renascita_path),

    # Provinces (subfolder or flat)
    (re.compile(r"^Realms/Renascita/Geography/[^/]+/Provinces/.*\.md$"),
     "region", realm_from_renascita_path),

    # Mountains
    (re.compile(r"^Realms/Renascita/Geography/[^/]+/Mountains/.*\.md$"),
     "range", realm_from_renascita_path),

    # Rivers
    (re.compile(r"^Realms/Renascita/Geography/[^/]+/Rivers/.*\.md$"),
     "waterway", realm_from_renascita_path),

    # World Beneath: same shape as a continent but separate
    (re.compile(r"^Realms/Renascita/Geography/The World Beneath/Locations/.*\.md$"),
     "landmark", lambda _: {"continent": "[[The World Beneath]]"}),

    # Generic locations under a continent
    (re.compile(r"^Realms/Renascita/Geography/[^/]+/Locations/.*\.md$"),
     "landmark", realm_from_renascita_path),

    # Anything else directly in a city folder (e.g. Magnus' Rest/Cascadia.md
    # where Cascadia is a sub-district without an explicit Locations/ subfolder)
    (re.compile(r"^Realms/Renascita/Geography/[^/]+/Cities/[^/]+/[^/]+\.md$"),
     "landmark", realm_from_renascita_path),

    # ---------- Societies ----------
    # Society self-named: Societies/<Society>/<Society>.md  → faction (Aaron may relabel to culture)
    (re.compile(r"^Realms/Renascita/Societies/([^/]+)/\1\.md$"), "faction", lambda _: {"realm": "[[Renascita]]"}),

    (re.compile(r"^Realms/Renascita/Societies/.*/Characters/.*\.md$"), "character", lambda _: {}),
    (re.compile(r"^Realms/Renascita/Societies/.*/Clans/.*\.md$"), "organisation", lambda _: {}),
    (re.compile(r"^Realms/Renascita/Societies/.*/Orders/.*\.md$"), "organisation", lambda _: {}),
    (re.compile(r"^Realms/Renascita/Societies/.*/Traditions/.*\.md$"), "tradition", lambda _: {}),
    (re.compile(r"^Realms/Renascita/Societies/.*/Locations/.*\.md$"), "landmark", lambda _: {}),
    # Anything else under a society that isn't the self-named summary
    (re.compile(r"^Realms/Renascita/Societies/.*\.md$"), "essay", lambda _: {}),

    # ---------- Legendarium ----------
    (re.compile(r"^Realms/Renascita/Legendarium/Artifacts/.*\.md$"), "artifact", lambda _: {}),
    (re.compile(r"^Realms/Renascita/Legendarium/Characters/.*\.md$"), "character", lambda _: {}),
    (re.compile(r"^Realms/Renascita/Legendarium/Technology/.*\.md$"), "technology", lambda _: {}),
    (re.compile(r"^Realms/Renascita/Legendarium/Natural Resources/.*\.md$"), "resource", lambda _: {}),
    (re.compile(r"^Realms/Renascita/Legendarium/Magic/.*\.md$"), "technology", lambda _: {}),
    (re.compile(r"^Realms/Renascita/Legendarium/Monsters/.*\.md$"), "character", lambda _: {}),
    (re.compile(r"^Realms/Renascita/Legendarium/Prophecies/.*\.md$"), "prophecy", lambda _: {}),
    # Anything else loose under Legendarium: treat as artifact (named, singular)
    (re.compile(r"^Realms/Renascita/Legendarium/[^/]+\.md$"), "artifact", lambda _: {}),

    # ---------- Factions ----------
    (re.compile(r"^Realms/Renascita/Factions/Organisations/.*\.md$"), "organisation", lambda _: {}),
    (re.compile(r"^Realms/Renascita/Factions/Orders/.*\.md$"), "organisation", lambda _: {}),
    (re.compile(r"^Realms/Renascita/Factions/Religions/.*\.md$"), "faction", lambda _: {}),
    (re.compile(r"^Realms/Renascita/Factions/Cults/.*\.md$"), "faction", lambda _: {}),

    # ---------- Other realms / planes (single-file stubs being promoted) ----------
    # Each plane gets its own folder in Task 7; for now we just classify them.
    (re.compile(r"^Realms/(Solirion|Nihilum|Thargrun|Veltharyn|Woudum|Sigmora|Infernum|Imperium)\.md$"),
     "landmark", lambda _: {}),
    (re.compile(r"^Realms/(Solirion|Nihilum|Thargrun|Veltharyn|Woudum|Sigmora|Infernum|Imperium)/.*\.md$"),
     "landmark", lambda _: {}),

    # Elementis
    (re.compile(r"^Realms/Elementis/.*\.md$"), "landmark", lambda _: {}),

    # Planes summary file
    (re.compile(r"^Realms/Planes\.md$"), "essay", lambda _: {}),

    # ---------- History ----------
    # Timeline meta file
    (re.compile(r"^History/Timeline\.md$"), "index", lambda _: {}),
    # Era summary files (self-named in age folder): handled by skeleton script
    (re.compile(r"^History/[^/]+/[^/]+\.md$"), "event", era_from_history_path),

    # ---------- Cosmology ----------
    (re.compile(r"^Cosmology/Gods/.*\.md$"), "deity", lambda _: {}),
    (re.compile(r"^Cosmology/Elementals/.*\.md$"), "deity", lambda _: {}),
    (re.compile(r"^Cosmology/Creation/The God Hand/.*\.md$"), "deity", lambda _: {}),
    (re.compile(r"^Cosmology/Cosmic Functions/.*\.md$"), "cosmic-force", lambda _: {}),
    (re.compile(r"^Cosmology/Creation/Corruption/.*\.md$"), "cosmic-force", lambda _: {}),
    (re.compile(r"^Cosmology/Creation/.*\.md$"), "essay", lambda _: {}),

    # ---------- Races ----------
    (re.compile(r"^Races/[^/]+/[^/]+/Variants/[^/]+\.md$"), "race", lambda _: {}),
    (re.compile(r"^Races/[^/]+/[^/]+/[^/]+\.md$"), "race", lambda _: {}),
    (re.compile(r"^Races/[^/]+/[^/]+\.md$"), "race", lambda _: {}),
    (re.compile(r"^Races/[^/]+\.md$"), "race", lambda _: {}),

    # ---------- Languages ----------
    (re.compile(r"^Languages/.*\.md$"), "language", lambda _: {}),

    # ---------- Story ----------
    (re.compile(r"^Story/.*\.md$"), "essay", lambda _: {}),

    # ---------- Top-level index ----------
    (re.compile(r"^index\.md$"), "essay", lambda _: {}),

    # ---------- Realms top-level files (Planes.md handled above; others) ----------
    (re.compile(r"^Realms/[^/]+\.md$"), "essay", lambda _: {}),
]


def classify(relpath: str) -> Tuple[str, Dict[str, str], str]:
    """Return (inferred_type, extras_dict, matched_rule_repr).

    Returns ("UNCLASSIFIED", {}, "") if no rule matches.
    """
    for pattern, type_, extras in RULES:
        if pattern.match(relpath):
            if type_ is None:
                return ("SKIP", {}, pattern.pattern)
            extra_fields = extras(relpath) if extras else {}
            return (type_, extra_fields, pattern.pattern)
    return ("UNCLASSIFIED", {}, "")

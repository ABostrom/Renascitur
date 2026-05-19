---
type: essay
status: canon
topic: front-page
tags: []
---

# Renascitur

> *"When the gods fell and the stars bled, the world was reborn in ash and memory. Thus began the age of Renascitur."*

A mythic fantasy setting spanning four Ages. The Solarans built the Endless Sun and then fell. The Hexweave bound the world and then broke. The dark gods rose, the bright gods answered, and the Night War is now. This wiki is the lore.

## The Four Ages

| Code | Age | Folder | Themes |
|------|-----|--------|--------|
| `ES` | [[Age of the Endless Sun]] | `events/Age of the Endless Sun/` | Creation; the rise and fall of Solaran civilization |
| `AF` | [[Age of Forging]]          | `events/Age of Forging/`          | The Hexweave bound; Ishna sealed; the Forge Wars |
| `AS` | [[Age of Stagnation]]       | `events/Age of Stagnation/`       | The Hexweave broken; the long decline |
| `AN` | [[Age of Night]]            | `events/Age of Night/`            | The present — the Night War |

## Major realms

- **[[Renascita]]** — the mortal continent, where most of the world lives. Eight regions: Aquaria, Arcturia, Mokoweri, Pyrosia, Qethusiyya, the World Beneath, plus the islands of Draumhavn and Thundrakar.
- **[[Elementis]]** — the four elemental planes (Aqua, Ignis, Terra, Ventus).
- **The outer planes** — Solirion, Nihilum, Thargrun, Veltharyn, Woudum, Sigmora, Infernum, Imperium.

## Major societies

- **[[Firebrand Empire]]** — anti-magic imperial civilization in Pyrosia; the 12 Great Houses; lux-lapis-walled cities.
- **[[Thraysian Magocracy]]** — arcane council based at Eltabarr; the Athenaeum and the Majlis of Arcane Sovereignty.
- **[[Dwarven Holds]]** — the four united holds: Tidebound (Draumhavn), Icebound (Uftine), Stormbound (Thundrakar), Flamebound (Magnus' Rest).
- **[[Saurian Enclave]]** — bioengineered guardians of Mokoweri; council of Elders at Aeloria; keepers of the Archive of the Ancients.
- **[[Rahalan Nomads]]** — matriarchal desert culture sailing living Gaia-ships.
- **[[The Blackiron Collective]]** — gladiatorial industrial society; the Ironclad Arena.
- **[[The Solaran Federation of Worlds]]** — the lost interstellar civilization of the First Age.

## Cosmology

- **Pantheons**: [[Noxar Gods]] (the dark), [[Luxar Gods]] (the bright), [[The God Hand]] (Ishna's corrupted Quintumvirate), [[Elementals]] (the four elemental forces)
- **Cosmic forces**: Concorda, Specular, Luminis, Entropy, and [[Hexweave|the Hexweave]] — the broken lattice
- **Corruption**: [[Ishna]], the Aberrations, the Machinery of Death

## Where to find things

Top-level folders are flat by type. Every reference page is one click from here.

| Folder | Holds |
|--------|-------|
| `characters/` | Every named NPC |
| `settlements/` | Cities, towns, holds |
| `continents/`, `regions/`, `landmarks/`, `ranges/`, `waterways/` | Geography by scale |
| `planes/` | Non-Renascita realms |
| `factions/`, `houses/`, `cultures/`, `organisations/` | People in groups |
| `races/<lineage>/<race>/` | Races and variants (depth 3) |
| `deities/<pantheon>/` | Gods grouped by pantheon |
| `cosmic-forces/` | Abstract forces (incl. Hexweave, Corruption) |
| `eras/`, `events/<era>/`, `chronicles/`, `myths/`, `prophecies/` | The temporal spine |
| `artifacts/`, `items/`, `resources/<category>/`, `technologies/<discipline>/` | Things |
| `languages/<kind>/`, `traditions/` | Concepts |
| `essays/` | Long-form prose |
| `_meta/` | Dashboards, conventions, indices |

## Live dashboards

```dataview
LIST FROM "_meta"
WHERE type = "index"
SORT file.name ASC
```

## Recent activity

```dataview
TABLE WITHOUT ID
  file.link AS "Note",
  type AS "Type",
  status AS "Status"
FROM ""
WHERE !contains(string(file.path), "_meta/")
SORT file.mtime DESC
LIMIT 15
```

## Stub backlog

Notes whose structural shape is in place but whose prose has yet to be written. Open one, write it, set `status: draft` or `status: canon`.

```dataview
TABLE WITHOUT ID
  file.link AS "Note",
  type AS "Type",
  file.folder AS "Folder"
FROM ""
WHERE status = "stub"
SORT type ASC, file.name ASC
LIMIT 30
```

(Full list in `_meta/Stub Backlog.md`.)

---

*See `notes/working-model.md` and `notes/refactor-design.md` (at repo root) for the structure rationale, and `_meta/Conventions.md` for the authoring rules.*

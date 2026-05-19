---
aliases:
- Goliaths
tags:
- race
- elemental
- grundthain
- nomadic
lineage: '[[Dwarf|Dwarves]]'
origin_plane: '[[Renascita]]'
aat-race-tier: distinct
spoken_language:
- '[[Karathic]]'
- '[[Titanic]]'
- '[[Imperial Common]]'
type: race
status: draft
---
# Goliaths

**Summary:**  
The Goliaths are a nomadic, hardy people descended from the [[Grundthain]], known for their strength and survival skills. They travel in herds across the continent of [[Pyrosia]] and often serve as mercenaries.

---

## Origins

- Descended from elemental [[Grundthain]] stock, adapted for harsh wilderness survival.  
- Known for their tribal culture and tight-knit clans.

---

## Appearance

- Tall and muscular with stone-like skin.  
- Usually have tribal tattoos and markings denoting clan affiliations.

---

## Culture

- Nomadic and pragmatic, valuing strength and honor.  
- Strong sense of community and family bonds.

---

## Abilities

- Exceptional physical endurance and combat prowess.  
- Skilled in mountain and wilderness survival.

---

## Notes

- Speak [[Titanic]], their ancient ceremonial language.  
- Often hired by the [[Firebrand Empire]] for muscle and warriors.

---

> “The herd survives as one.”

---

## Contents

<!-- AUTO-INJECTED-DYNAMIC-CONTENTS — delete this comment and everything below to opt out; safe to edit otherwise -->

### Variants

```dataview
LIST FROM ""
WHERE type = "race" AND parent_race = this.file.link
SORT file.name ASC
```

### Characters of this race

```dataview
TABLE WITHOUT ID
  file.link AS "Name",
  culture AS "Culture",
  affiliation AS "Affiliation"
FROM ""
WHERE type = "character" AND race = this.file.link
SORT file.name ASC
```

### Languages spoken

```dataview
LIST FROM ""
WHERE type = "language" AND contains(spoken_by, this.file.link)
SORT file.name ASC
```

### Cultures associated with this race

```dataview
LIST FROM ""
WHERE type = "culture" AND contains(races, this.file.link)
SORT file.name ASC
```

### Other notes referencing this race

```dataview
LIST WHERE contains(file.inlinks, this.file.link)
  AND !contains(string(file.path), "_meta/")
SORT file.name ASC
```


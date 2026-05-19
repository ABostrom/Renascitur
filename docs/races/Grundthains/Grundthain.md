---
aliases:
- Grundthain
tags:
- race
- elder
- elemental
origin_plane: '[[Thargrun]]'
aat-race-tier: '[[Elder Races]]'
spoken_language: '[[Karathic]]'
type: race
status: draft
lineage: Grundthains
nature: mortal
importance: major
lifespan: ''
magic_affinity: []
---
# Grundthain

**Summary:**  
The Grundthain are towering beings of elemental power and harmony, intrinsically bound to Earth, Fire, Water, and Air. They served as stewards of creation in [[the First Age]], devoted to balance and unity.

---

## Origins

- Born in the plane of [[Thargrun]], connected deeply to primal elemental forces.  
- Divided into elemental clans: Frost, Fire, Storm, and Hill Giants.

---

## Appearance

- Massive and imposing, often reflecting their elemental affinity.  
- Features range from icy blue skin to fiery red, or storm-cloud hues.

---

## Culture

- Elemental clans hold ancient traditions and elemental worship.  
- Guardians of natural cycles, resisting corruption by [[Ishna]].

---

## Abilities

- Innate elemental powers linked to their clan.  
- Great strength and resilience.

---

## Languages

- Speak and write [[Karathic]], the ancient language of the Grundthain.

---

## Notes

- [[Muradin]], a visionary Grundthain, split from elemental traditions to forge the [[Dwarf|dwarves]].  
- Related groups include [[Varkuun]], [[Goliaths]], and the dwarven clans.

---

> “We are the mountain, the storm, the flame — eternal.”

---

## Contents

<!-- AUTO-INJECTED-DYNAMIC-CONTENTS — delete this comment and everything below to opt out; safe to edit otherwise -->

### Variants

```dataview
LIST FROM ""
WHERE type = "race" AND string(parent_race) = string(this.file.link)
SORT file.name ASC
```

### Characters of this race

```dataview
TABLE WITHOUT ID
  file.link AS "Name",
  culture AS "Culture",
  affiliation AS "Affiliation"
FROM ""
WHERE type = "character" AND string(race) = string(this.file.link)
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


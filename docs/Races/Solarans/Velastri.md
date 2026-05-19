---
aliases:
- Velastri
tags:
- race
- distinct
- solarans
- infernal
lineage: '[[Solaran]]'
origin_plane: '[[Infernum]]'
aat-race-tier: distinct
spoken_language:
- '[[Zytherin]]'
type: race
status: draft
nature: ''
importance: ''
lifespan: ''
magic_affinity: []
---
# Velastri

**Summary:**  
The Velastri are a distinct and fearsome race descended from [[Solaran|Solarans]] who became corrupted and twisted by the harsh environment of [[Infernum]]. They embody infernal might and arcane power.

---

## Origins

- Evolved from [[Solaran|Solarans]] trapped in [[Infernum]] during [[the First Age]].  
- Developed infernal traits due to harsh plane conditions.

---

## Appearance

- Red skin, white hair, devilish features including tails and horns.  
- Intimidating, often adorned with arcane sigils.

---

## Culture

- Militaristic, valuing strength, cunning, and survival.  
- Known for mastery of spellguns and soulblades.

---

## Abilities

- Proficient in infernal magic and advanced weaponry.  
- Natural resilience to extreme conditions.

---

## Notes

- Governed by powerful mage-rulers; one such ruler is [[Zariel]].

---

> “From fire and shadow, we rise eternal.”

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


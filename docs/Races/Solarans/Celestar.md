---
aliases:
- Celestars
tags:
- race
- distinct
- solarans
- celestial
lineage: '[[Solaran]]'
origin_plane: '[[Imperium]]'
aat-race-tier: distinct
spoken_language:
- '[[Serethi]]'
type: race
status: draft
nature: celestial
importance: major
lifespan: ''
magic_affinity: []
---
# Celestar

**Summary:**  
The Celestar, are a distinct race evolved from [[Solaran|Solarans]]. Known for their radiant appearance and powerful celestial magic, they serve as shining beacons in the cosmos.

---

## Origins

- Diverged from [[Solaran|Solarans]] during [[the First Age]] to embrace pure celestial magic.  

---

## Appearance

- Radiant golden skin, with glowing markings and ethereal features.  
- Often adorned in robes or armor imbued with celestial sigils.

---

## Culture

- Guardians of cosmic balance and celestial order.  
- Highly spiritual and magical society with strict codes.

---

## Abilities

- Exceptional manipulation of celestial energies and light magic.

---

## Notes

- Maintain close ties with [[Solaran]] knowledge but chart independent destiny.

---

> “Light is the forge of our souls.”

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


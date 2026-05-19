---
aliases:
- Dwarves
tags:
- race
- elemental
- grundthain
- crafts
lineage: '[[Dwarf|Dwarves]]'
origin_plane: '[[Thargrun]]'
aat-race-tier: distinct
spoken_language: '[[Dwarven]]'
type: race
status: draft
nature: mortal
importance: major
lifespan: ''
magic_affinity: []
---
# Dwarves

**Summary:**  
The Dwarves are descendants of the [[Grundthain]] who embraced Metal as a fifth element, forging a new path of craftsmanship and resilience. Known for their stout builds and expert rune-smithing, they form four major clans guarding elemental legacies.

---

## Origins

- Forged by [[Muradin]]’s vision to combat corruption with metal and innovation.  
- Transformed from elemental [[Grundthain]] into stout, resilient beings.

---

## Appearance

- Stocky, muscular builds with weathered skin.  
- Facial hair common, often braided and adorned with runes.

---

## Culture

- Reverence for craftsmanship, innovation, and tradition.  
- Society structured around clan loyalty and rune magic.

---

## Abilities

- Skilled in metallurgy, rune forging, and elemental magic.  
- Natural resilience and toughness.

---

## Languages

- Speak [[Karathic]] and [[Dwarven]].

---

## Notes

- Clans include [[Tidebound]], [[Stormbound]], [[Icebound]], and [[Flamebound]].  
- Maintain close ties to [[Grundthain]] roots and elemental gods.

---

> “Our anvils ring with the song of the earth.”

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


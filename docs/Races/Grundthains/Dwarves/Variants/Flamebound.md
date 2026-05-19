---
aliases:
- Flamebound Dwarves
tags:
- race
- variant
- dwarves
- elemental
- lineage/grundthains
- race/dwarves
lineage: '[[Dwarf|Dwarves]]'
origin_plane: '[[Thargrun]]'
aat-race-tier: variant
spoken_language: '[[Dwarven]]'
type: race
status: draft
parent_race: '[[Dwarves]]'
---
# Flamebound [[Dwarf|Dwarves]]

## Overview  
The [[Flamebound|Flamebound Dwarves]] are the fiery clan of [[Dwarf|dwarves]] who dwell in the city of [[Magnus’ Rest]]. They guard the sacred embers and the flame-fragment sealed by [[Muradin]] in [[the First Age]], channelling the power of [[Phenos]], the elemental god of fire and renewal.

Their spirits burn bright, fuelled by both creation and destruction.

## Ancestry and Legacy  
Descended from the ancient [[Grundthain]], the Flamebound embraced the destructive and creative forces of fire. Their forges are renowned for crafting legendary weapons and artifacts imbued with elemental power.

## Society and Culture  
Flamebound culture is passionate and bold, celebrating craftsmanship and innovation. Their forges are places of worship, and their rituals honour the eternal flame and their elemental patron.


## Physical Traits  
- Warm-toned skin with occasional flame-like markings.  
- Hair often reddish or blackened like cooled lava.

## Elemental Materials  


## Beliefs  
The Flamebound revere fire as a force of renewal and transformation, embracing its dual nature.

## Quotes  
> “From the ashes, we rise stronger.”  
> — Flamebound Proverb

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


---
aliases:
- Elasi
tags:
- race
- elemental
- mortal-descendant
lineage: Humans
origin_plane:
- - Elemental Plane
aat-race-tier: mortal-descendant
spoken_language:
- - Elemental Tongue
written_language:
- - Elemental Script
type: race
status: draft
nature: mortal
importance: major
lifespan: ''
magic_affinity: []
---
# Elasi

**Summary:**  
The Elasi are descendants of humans who migrated and adapted to the [[Elemental Plane]]. They are attuned to elemental forces and have developed unique elemental cultures.

---

## Origins

- Born from humans who ventured into the elemental realms and adapted over generations.

---

## Appearance

- Varies depending on elemental affinity (fire, water, earth, air).  
- Often marked by elemental traits like glowing skin, hair like flame or water, or stony textures.

---

## Culture

- Deeply connected to elemental forces and the natural cycles of their plane.  
- Societies often revolve around elemental worship and mastery.

---

## Abilities

- Elementally attuned abilities related to their specific plane.  
- Skilled elemental magic users and artisans.

---

## Languages

- Speak [[Elemental Tongue]], a mystical language tied to the elemental forces.

---

## Notes

- Maintain cultural and trade links with Terran humans and other mortal races.  
- Play key roles in elemental politics and conflicts.

---

> “Born of the elements, shaped by the world.”

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


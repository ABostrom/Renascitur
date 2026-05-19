---
aliases:
- Ferrun
tags:
- race
- cultural-variant
- solarans
- industrial
lineage: '[[Solaran]]'
origin_plane: '[[Renascita]]'
aat-race-tier: variant
spoken_language:
- '[[Thraysian Common]]'
- '[[Elyssan]]'
- '[[Dwarven]]'
type: race
status: draft
---
# Ferrun

**Summary:**  
The Ferrun are descendants of the [[Solaran|Solarans]] who rejected the arcane and natural paths to embrace innovation and craftsmanship. They founded the industrial city of [[Thelassia]], mastering metallurgy, rune magic, and engineering.

---

## Origins

- Splintered from [[Solaran|Solarans]] post-Solara collapse, focusing on science and industry.  
- Deep respect for [[Muradin]] in his original [[Grundthain]] form.

---

## Appearance

- Dusky skin from charcoal to deep violet, white or silver hair, and glowing eyes.  
- Functional attire featuring circuitry and rune motifs.

---

## Culture

- Meritocratic and experimental, valuing intellect and adaptability.  
- View misuse of arcane knowledge as cause of Solara’s fall.

---

## Abilities

- Experts in alchemy, engineering, and psionics.  
- Skilled creators of technology blending rune magic and machinery.

---

## Notes

- Rekindled ties with [[Dwarf|dwarves]] via underground railroads.  
- Their city [[Thelassia]] hums with steam, gears, and innovation.

---

> “Progress is the forge where the future is born.”

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


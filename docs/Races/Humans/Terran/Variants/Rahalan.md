---
aliases:
- Rahalan Humans
tags:
- race
- cultural-variant
- humans
- tribal
lineage: '[[Terran]]'
origin_plane: '[[Renascita]]'
aat-race-tier: variant
spoken_language:
- '[[Thraysian Common]]'
type: race
status: draft
parent_race: '[[Terran]]'
nature: ''
importance: ''
lifespan: ''
magic_affinity: []
---
# Rahalan Humans

**Summary:**  
The Rahalan are nomadic desert tribes descended from Terran humans. Known for their resilience and adaptability, they navigate the harsh desert and survive through tight-knit tribal bonds.

---

## Origins

- Exiles and wanderers who adapted to the [[Al-Ramal]] desert to the north of the [[Qethusiyya]].

---

## Appearance

- Sun-darkened skin, lean and muscular builds.  
- Often adorned with practical desert garb and tribal markings.

---

## Culture

- Tribal, valuing honor, survival, and oral traditions.  
- Skilled in desert navigation and resource management.

---

## Abilities

- Expert survivalists and desert warriors.  
- Proficient in stealth, tracking, and desert combat.

---

## Notes

- Known for their independence and fierce loyalty to kin.  
- Often traders, scouts, or raiders on the empire’s fringes.

---

> “The sands hide many secrets.”

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


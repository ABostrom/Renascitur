---
aliases:
- Uftine Humans
tags:
- race
- cultural-variant
- humans
- hardy
lineage: Humans
origin_plane: '[[Renascita]]'
aat-race-tier: variant
spoken_language:
- '[[Imperial Common]]'
- '[[Dwarven]]'
type: race
status: draft
parent_race: '[[Terran]]'
nature: mortal
importance: notable
lifespan: ''
magic_affinity: []
---
# Uftine Humans

**Summary:**  
The [[Uftine]] are hardy [[Terran|Terrans]] adapted to the frozen, harsh northern regions. They have developed thick builds and a resilience born of endless winters.

---

## Origins

- Descendants of [[Terran|Terrans]] who settled the icy north.

---

## Appearance

- Fair to ruddy skin with rosy cheeks from cold exposure.  
- Often light eyes and hair, suited for snowy environments.

---

## Culture

- Practical and community-focused, skilled in survival and craftsmanship.  
- Strong bonds with nearby [[Icebound]] [[Dwarf|Dwarves]].

---

## Abilities

- Adapted for cold climates with endurance and fortitude.  
- Skilled hunters, fishers, and craftspeople.

---

## Notes

- Known for their stoic nature and strong family ties.  
- Maintain trade and cultural exchanges with dwarven clans.

---

> “The frost does not break us.”

---

## Contents

<!-- AUTO-INJECTED-DYNAMIC-CONTENTS — delete this comment and everything below to opt out; safe to edit otherwise -->

### Variants

```dataview
LIST FROM ""
WHERE type = "race" AND contains(file.outlinks, this.file.link)
SORT file.name ASC
```

### Characters of this race

```dataview
TABLE WITHOUT ID
  file.link AS "Name",
  culture AS "Culture",
  affiliation AS "Affiliation"
FROM ""
WHERE type = "character" AND contains(file.outlinks, this.file.link)
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


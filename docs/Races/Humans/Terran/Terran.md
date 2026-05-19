---
aliases:
- Humans
- Terrans
tags:
- race
- mortal
- adaptable
- lineage/humans
- race/terran
origin_plane: '[[Renascita]]'
spoken_language:
- '[[Imperial Common|Imperial]]'
type: race
status: draft
lineage: Human
---
# Terran Humans

**Summary:**  
Terran Humans are the widespread and adaptable peoples inhabiting the material world. Known for their versatility and ambition, they thrive in almost every environment.

---

## Origins

- Originating on the [[Material Plane]], humans have diversified into many cultures and societies.

---

## Appearance

- Highly varied in height, skin tone, hair, and eye color.  
- Physically resilient but less specialized than [[elder races]].

---

## Culture

- Diverse cultures spanning from tribal to imperial societies.  
- Often value ambition, adaptability, and innovation.

---

## Abilities

- Adaptable to different environments and challenges.  
- Natural learners and inventors.

---

## Languages

- Speak [[Common]], with various dialects including [[Terran Dialect]].

---

## Notes

- Known for shaping the geopolitical landscape of Renascitur.  
- Often caught between [[elder races]] and aberrant threats.

---

> “From many paths, we carve our own.”

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


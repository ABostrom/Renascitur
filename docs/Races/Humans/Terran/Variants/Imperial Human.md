---
aliases:
- Imperial Humans
tags:
- race
- cultural-variant
- humans
- imperial
lineage: '[[Terran]]'
origin_plane: '[[Renascita]]'
aat-race-tier: variant
spoken_language:
- '[[Imperial Common]]'
type: race
status: draft
parent_race: '[[Terran]]'
nature: ''
importance: ''
lifespan: ''
magic_affinity: []
---
# Imperial Humans

**Summary:**  
Imperial Humans hail from the [[Firebrand Empire]], known for their strict adherence to order, honor, and martial prowess. They are disciplined, proud, and maintain a deep mistrust of magic.

---

## Origins

- Descended from Terran humans integrated into the empire’s militaristic and political systems.

---

## Appearance

- Tall and muscular, with sharp features and usually dark hair.  
- Favor fine clothes and armor denoting social status.

---

## Culture

- Hierarchical, valuing loyalty, discipline, and tradition.  
- Fear and suppress magic, emphasizing structure and law.

---

## Abilities

- Skilled warriors and administrators.  
- Adapt well to military and bureaucratic roles.

---

## Notes

- Central to maintaining the empire’s power and influence.  
- Often at odds culturally with magic users and other races.

---

> “Strength through order, honor through discipline.”

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


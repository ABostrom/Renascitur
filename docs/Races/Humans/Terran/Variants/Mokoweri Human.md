---
aliases:
- Mokoweri Humans
tags:
- race
- cultural-variant
- humans
- tribal
- lineage/humans
- race/terran
lineage:
- '[[Terran]]'
origin_plane:
- '[[Renascita]]'
aat-race-tier: variant
spoken_language:
- '[[Imperial Common]]'
- '[[Thraysian Common]]'
- '[[Mokoweran]]'
type: race
status: draft
parent_race: '[[Terran]]'
---
# [[Mokoweri]] Humans

**Summary:**  
The [[Mokoweri]] are tribal [[Terran|Terrans]] living in harmony with the natural world on the island of [[docs/Realms/Renascita/Locations and Cities/Mokoweri/Mokoweri|Mokoweri]]. They have embraced a lifestyle centred around community, nature, and coexistence.

---

## Origins

- Descendants of Terran humans adapted to island jungle life.

---

## Appearance

- Shorter, lean builds with skin tones ranging from light to dark brown.  
- Often bear tribal tattoos and markings.

---

## Culture

- Deeply connected to nature and the [[Saurian|Saurians]].  
- Communal and spiritual, with strong traditions in hunting and crafting.

---

## Abilities

- Skilled hunters, gatherers, and craftsmen.  
- Unique communication abilities with jungle creatures.

---

## Notes

- Maintain a symbiotic relationship with the island’s ecosystem.  
- Distrust outsiders and protect their homeland fiercely.

---

> “The jungle breathes through us.”

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


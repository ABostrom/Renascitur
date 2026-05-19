---
aliases:
- Imperial Orcs
tags:
- race
- cultural-variant
- orcs
- imperial
lineage: Kyojin
origin_plane: '[[Renascita]]'
aat-race-tier: variant
spoken_language:
- '[[Imperial Common]]'
- '[[Orcish]]'
type: race
status: draft
parent_race: '[[Orcs]]'
nature: mortal
importance: notable
lifespan: ''
magic_affinity: []
---
# Imperial [[Orc|Orcs]]

**Summary:**  
Imperial [[Orc|Orcs]] are a martial and disciplined branch of [[Orc|Orcs]] who serve the [[Firebrand Empire]]. They combine traditional orcish strength with imperial military discipline.

---

## Origins

- [[Orc]] clans integrated into the imperial structure of the [[Firebrand Empire]].

---

## Appearance

- Greyish-green skin with battle scars and armor crafted from beast hides and metal.  
- Often heavily muscled and imposing.

---

## Culture

- Fierce warriors and skilled metalworkers.  
- Honor military service and clan loyalty.

---

## Abilities

- Skilled combatants with knowledge of weapons and tactics.  
- Retain shamanistic traditions adapted to imperial service.

---

## Notes

- Fluent in [[Common]] and [[Orcish]].  
- Often employed as elite soldiers or mercenaries.

---

> “Strength guided by discipline makes the empire unbreakable.”

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


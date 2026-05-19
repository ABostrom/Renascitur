---
aliases:
- Orcs
tags:
- race
- cultural-variant
- kyojin
- primal
lineage: '[[docs/Races/Kyojin/Leonin/Leonin|Leonin]]'
origin_plane: '[[Renascita]]'
aat-race-tier: distinct
spoken_language:
- '[[Orcish]]'
type: race
status: draft
---
# Orcs

**Summary:**  
Orcs are a fierce and powerful race descended from the primal [[Kyojin]]. They are known for their strength, resilience, and spiritual traditions.

---

## Origins

- Descended from [[Kyojin]] clans, adapted to harsh environments and tribal life.

---

## Appearance

- Rough, greyish-green skin, muscular with prominent facial features.  
- Often adorned with scars, tattoos, and tribal markings.

---

## Culture

- Spiritual and tribal, valuing strength and community.  
- Skilled craftsmen and hunters with a deep respect for the natural world.

---

## Abilities

- Exceptional physical strength and endurance.  
- Natural affinity for shamanistic magic and rites.

---

## Notes

- Speak [[Orcish]], a derivative of [[Natsugen]] with spiritual influences.  
- Many serve as fierce warriors and mercenaries in larger empires.

---

> “The strength of the tribe is the strength of the orc.”

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


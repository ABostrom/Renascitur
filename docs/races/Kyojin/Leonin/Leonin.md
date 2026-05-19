---
aliases:
- Leonin
tags:
- race
- cultural-variant
- kyojin
- primal
lineage: Kyojin
origin_plane: '[[Renascita]]'
aat-race-tier: distinct
spoken_language:
- '[[docs/Languages/Modern/Leonin|Leonin]]'
type: race
status: draft
nature: mortal
importance: major
lifespan: ''
magic_affinity: []
---
# Leonin

**Summary:**  
The Leonin are a noble and proud race descended from the [[Kyojin]], known for their feline features, wisdom, and prowess in combat.

---

## Origins

- Descended from [[Kyojin]] clans who developed refined culture and martial traditions.

---

## Appearance

- Humanoid felines with golden to tawny fur, muscular builds, and sharp claws.  
- Eyes typically green or yellow, with regal bearing.

---

## Culture

- Wise and honorable, guardians of tradition and empire’s cultural heritage.  
- Skilled fighters and leaders.

---

## Abilities

- Agile and powerful combatants.  
- Natural affinity for tactics and leadership.

---

## Notes

- Speak [[Leonin]], a tactical derivative of [[Natsugen]].  
- Hold high positions in the [[Firebrand Empire]].

---

> “Pride is our strength; honor is our path.”

---

## Contents

<!-- AUTO-INJECTED-DYNAMIC-CONTENTS — delete this comment and everything below to opt out; safe to edit otherwise -->

### Variants

```dataview
LIST FROM ""
WHERE type = "race" AND string(parent_race) = string(this.file.link)
SORT file.name ASC
```

### Characters of this race

```dataview
TABLE WITHOUT ID
  file.link AS "Name",
  culture AS "Culture",
  affiliation AS "Affiliation"
FROM ""
WHERE type = "character" AND string(race) = string(this.file.link)
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


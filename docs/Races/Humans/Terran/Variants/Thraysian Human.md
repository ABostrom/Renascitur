---
aliases:
- Thraysian Humans
tags:
- race
- cultural-variant
- humans
- magocratic
lineage:
- '[[Terran]]'
origin_plane:
- '[[Renascita]]'
aat-race-tier: variant
spoken_language:
- '[[Thraysian Common]]'
type: race
status: draft
---
# Thraysian Humans

**Summary:**  
Thraysian Humans are desert dwellers from the [[Thraysian Magocracy]], known for their intelligence, magical prowess, and resourcefulness in harsh environments.

---

## Origins

- Descended from [[Terran|Terrans]] adapted to desert and arid lands.

---

## Appearance

- Medium height with tan to dark skin tones.  
- Often have dark hair and eyes.

---

## Culture

- Highly skilled magic users with an emphasis on knowledge and resource management.  
- Society governed by a magocratic council.

---

## Abilities

- Adept at magic and arcane arts.  
- Skilled in desert survival and water conservation.

---

## Notes

- Thrive in harsh desert conditions.  
- Influence regional politics through magic and scholarship.

---

> “Knowledge is the wellspring of power.”

---

## Contents

<!-- AUTO-INJECTED-DYNAMIC-CONTENTS — delete this comment and everything below to opt out; safe to edit otherwise -->

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
LIST FROM [[]]
WHERE !contains(string(file.path), "_meta/")
SORT file.name ASC
```


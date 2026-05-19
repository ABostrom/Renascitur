---
aliases:
- Mokoweri
tags:
- race
- cultural-variant
- solarans
- nature
- lineage/solarans
lineage: '[[Solaran]]'
origin_plane: '[[Renascita]]'
aat-race-tier: variant
spoken_language:
- '[[Mokoweran]]'
- '[[Imperial Common]]'
- '[[Thraysian Common]]'
type: race
status: draft
---
# Mokuun

**Summary:**  
The [[Mokuun]] are [[Solaran|Solarans]] who embraced nature and live in harmony with the jungles of their island home. They are spiritual, resilient, and guardians of the sacred tree [[Irasandra]].

---

## Origins

- Descendants of [[Solaran|Solarans]] who rejected technology for symbiosis with nature.  
- Inhabit the jungle island of [[Mokuun]].

---

## Appearance

- Scaly skin tones in greens, browns, and greys, often adorned with bright markings.  
- Muscular build with reptilian features.

---

## Culture

- Community-focused and deeply spiritual.  
- Worship [[Irasandra]] and live sustainably with the environment.

---

## Abilities

- Natural resistance to aberrant energy.  
- Skilled hunters, gatherers, and craftsmen.

---

## Notes

- Governance by Elders’ Council and rites that reveal their origins.  
- Known for treetop cities built within ancient trees.

---

> “The jungle whispers the secrets of balance.”

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


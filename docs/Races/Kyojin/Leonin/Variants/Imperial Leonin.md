---
aliases:
- Imperial Leonin
tags:
- race
- cultural-variant
- leonin
- imperial
- lineage/kyojin
- race/leonin
lineage: '[[docs/Races/Kyojin/Leonin/Leonin|Leonin]]'
origin_plane: '[[Renascita]]'
aat-race-tier: variant
spoken_language:
- '[[Imperial Common]]'
- '[[docs/Languages/Modern/Leonin|Leonin]]'
type: race
status: draft
parent_race: '[[Leonin]]'
---
# Imperial [[docs/Races/Kyojin/Leonin/Leonin|Leonin]]

**Summary:**  
Imperial [[docs/Races/Kyojin/Leonin/Leonin|Leonin]] are the cultured, tactical elite within the [[Firebrand Empire]]. They blend primal nobility with imperial sophistication.

---

## Origins

- Refined [[docs/Races/Kyojin/Leonin/Leonin|Leonin]] integrated into the empire’s military and political structures.

---

## Appearance

- Larger, more muscular than common [[docs/Races/Kyojin/Leonin/Leonin|Leonin]] with polished armor.  
- Exhibit regality and martial discipline.

---

## Culture

- Emphasize wisdom, strategy, and honor.  
- Act as guardians of imperial culture and tradition.

---

## Abilities

- Skilled tacticians and combat leaders.  
- Maintain a proud and disciplined demeanor.

---

## Notes

- Fluent in [[Common]] and [[Leonin]].  
- Occupy key military and governance roles.

---

> “In wisdom and steel, we find our legacy.”

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


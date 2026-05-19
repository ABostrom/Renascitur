---
aliases:
- Varkuun
tags:
- race
- elemental
- grundthain
lineage: Grundthains
origin_plane: [[Thargrun]]
aat-race-tier: distinct
spoken_language:
- [[Titanic]]
type: race
status: draft
nature: mortal
importance: major
lifespan: ''
magic_affinity: []
---
# Varkuun

**Summary:**  
The Varkuun are a proud elemental race descended from the [[Grundthain]], embodying the raw power of the primal forces. They are often seen as mystical giants with deep ties to the elements.

---

## Origins

- A branch of [[Grundthain]] who embraced a fusion of elemental power.  
- Keepers of ancient elemental rites and knowledge.

---

## Appearance

- Towering and muscular, often with skin tones and features reflecting elemental forces.  
- Mystical markings and tattoos common.

---

## Culture

- Deeply spiritual, with rituals honouring the elemental gods.  
- Hold sacred sites throughout [[Thargrun]].

---

## Abilities

- Command elemental magics and physical might.  
- Often possess enhanced longevity and resilience.

---

## Notes

- Speak the [[Titanic]] tongue.  
- Related to other elemental [[Grundthain]] descendants.

---

> “The elements breathe through us.”

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


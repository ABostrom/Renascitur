---
aliases:
- Kyojin
tags:
- race
- elder
- primal
lineage: Elder Races
origin_plane: '[[Veltharyn]]'
aat-race-tier: elder
spoken_language:
- '[[Natsugen]]'
type: race
status: draft
nature: mortal
importance: major
lifespan: ''
magic_affinity: []
---
# Kyojin

**Summary:**  
The Kyojin are a primal and spiritual race deeply connected to the cycles of life, death, and the spirit world. Their origins trace back to the plane of [[Woudum]], where they maintain a profound bond with nature and ancestral spirits.

---

## Origins

- Born in [[Woudum]], embodying spirit and harmony.  
- Divided into clans that would give rise to descendants like [[Orcs]] and [[Leonin]].

---

## Appearance

- Strong, muscular builds with features reflecting animalistic grace or primal fierceness.  
- Skin tones vary from earth tones to golden hues.

---

## Culture

- Deeply spiritual, with shamanistic traditions and reverence for the [[Machinery of Death]].  
- Emphasis on honor, family, and the balance of life and death.

---

## Abilities

- Natural attunement to spiritual magic and [[soul]] communication.  
- Skilled hunters, warriors, and spirit mediums.

---

## Languages

- Speak and write [[Natsugen]], a language rich in spiritual symbolism.

---

## Notes

- The noble [[Leonin]] and primal [[Orcs]] trace their lineage to the Kyojin.  
- Dragons and other powerful beasts may share echoes of their primal souls.

---

> “The spirit guides the flesh, and the flesh honors the spirit.”

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


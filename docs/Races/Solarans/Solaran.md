---
aliases:
- Solarans
tags:
- race
- elder
- celestial
lineage: '[[Elder Races]]'
origin_plane: '[[Solirion]]'
aat-race-tier: elder
spoken_language: '[[Elyssan]]'
type: race
status: draft
nature: ''
importance: ''
lifespan: ''
magic_affinity: []
---
# Solaran

**Summary:**  
The Solarans are an ancient and advanced civilization deeply connected to celestial energies. They blend science, magic, and spirituality, believing every individual carries a small sun within, giving life and purpose.

---

## Origins

- Born in the plane of [[Libertum]], the Solarans embody cosmic balance and enlightenment.  
- Once rulers of the star city of [[Solara]], their civilization fell after catastrophic events tied to aberrant corruption and entropy.

---

## Appearance

- Radiant skin tones ranging from warm gold to ethereal iridescence.  
- Luminous eyes that reflect their sunbound heritage.  
- Often tall and slender with elegant features and pointed ears.

---

## Culture

- Valuing knowledge, wisdom, and cosmic harmony.  
- Society structured around scholars known as Sun Speakers, custodians of arcane and scientific knowledge.  
- Art, music, and poetry are sacred expressions tied to celestial worship and the cycles of life and death.  
- They revere the balance of the [[Machinery of Death]] and the cycle of souls.

---

## Abilities

- Innate affinity for sunlight and celestial magic.  
- Mastery over arcane arts and advanced bioengineering.  
- Spiritual attunement to [[Weave|the weave]] and cosmic forces.

---

## Languages

- Speak and write [[Luxan]], the ancient language of the Solarans.

---

## Notes

- Their legacy endures in relics and ruins scattered across the world.  
- Descendants and cultural variants include [[Arcanii]], [[Ferrun]], and [[Mokuun]].  
- Related races such as [[Celestar]] and [[Velastri]] have diverged into distinct lineages.

---

> “Each dawn carries the light of our ancestors and the hope of balance renewed.”

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


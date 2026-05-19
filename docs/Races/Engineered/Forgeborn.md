---
aliases:
- Forgeborn
tags:
- race
- engineered
- undead
- constructs
lineage: Engineered Race
origin_plane: '[[Renascita]]'
aat-race-tier: engineered
spoken_language:
- '[[Valeshi]]'
type: race
status: draft
nature: ''
importance: ''
lifespan: ''
magic_affinity: []
---
# Forgeborn

**Summary:**  
The Forgeborn are souldbound constructs created by [[Vecna]] in [[the Second Age]], forged by binding souls into mechanical bodies powered by dark magic and arcane technology. Their mission is to eradicate entropy and [[aberrations]] from the multiverse.

---

## Origins

- Created by [[Vecna]] from his son [[Hephaestus]]’s [[soul]], becoming the Forgeborn Prime.  
- Mass-produced during the [[Forge Wars]] as unstoppable legions.

---

## Appearance

- Mechanical and skeletal, with arcane runes and crystal cores glowing with dark energy.  
- Varying designs from humanoid to monstrous war machines.

---

## Culture

- No culture; operate on strict protocols and directives.  
- Communication limited to arcane pulse signals and mage scholars’ commands.

---

## Abilities

- Immune to corruption and entropy.  
- Possess immense strength, resilience, and arcane weaponry.

---

## Languages

- Use **Arcanometric Protocols**, a pulse-based written-only language used by mage scholars and arcane engineers.

---

## Notes

- Serve as tools of [[Vecna]]’s vision to restore order through eradication of chaos.  
- Fearless and relentless in their mission, devoid of mercy or free will.

---

> “Souls bound in steel, the hammer of order.”

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


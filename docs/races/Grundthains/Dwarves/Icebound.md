---
aliases:
- Icebound Dwarves
tags:
- race
- variant
- dwarves
- elemental
lineage: Grundthains
origin_plane: '[[Thargrun]]'
aat-race-tier: variant
spoken_language: '[[Dwarven]]'
type: race
status: draft
parent_race: '[[Dwarves]]'
nature: mortal
importance: notable
lifespan: ''
magic_affinity: []
---
# Icebound [[Dwarf|Dwarves]]

## Overview  
The [[Icebound|Icebound Dwarves]] are a stoic and enduring clan who dwell in the frost-veined city of [[Uftine Human]], nestled amid the glaciers and frozen peaks of the far North. They are the wardens of the **Pulsecore**, a slumbering wound where [[Zaratan]] — the elemental of earth and endurance — was fractured by corruption in [[the First Age]] and sealed by [[Muradin]].

Their hearts beat slow, like the mountains they inhabit.  
They do not rage. They endure — and remember.

## Ancestry and Legacy  
Descended from the ancient [[Grundthain]], the Icebound were once mountain builders and rune-scribes. When [[Muradin]] returned from his pilgrimage through the elemental planes, he tasked their ancestors with **watching over the corrupted stillness buried beneath the world**.

The Pulsecore beats faintly beneath [[Uftine Human]], and its resonance has shaped every inch of their stone-and-ice halls.

## Society and Culture  
The Icebound are contemplative, silent, and ritual-bound. They **listen to stone**, study glacial drift, and believe that memory is strongest when carved into stillness. Their society is built on patience — even their justice is measured in **cycles of the frost moon**.

Their leader, the **Stillheart**, is selected not for strength, but for **emotional immovability**, chosen to be the axis around which the entire hold turns. The current Stillheart is [[Gromdir Stillhand]], a legend among the Icebound and a symbol of their unshaken resolve.

The Icebound maintain the [[Uftine Express]], a miracle of engineering and rune-work that links their frozen realm to the greater dwarven world.

## Physical Traits  
- Pale or bluish-grey skin, often patterned with frost-burned veins.  
- Hair tends toward white, silver, or deep iron hues, often kept under furred hoods or wrapped in iceweave cords.  
- Some Icebound are “stone-voiced,” their tone naturally resonant with subterranean vibration.

## Elemental Materials  
Their smithing, known as [[Iceforging]], uses the **cold to shape**, rather than heat to melt. It is a whispering process of patience, pressure, and time.

- [[Icevein Steel]]  
- [[Stillstone Ore]]  
- [[Echo Diamond]]

These materials are **infused with memory and cold**, retaining the essence of glaciers, stalactites, and the silence of the deep.

## Beliefs  
The Icebound believe the world is a great stillness waiting to be shattered — and that their purpose is to **prevent that moment**. They do not shout. They **carve runes to bind what should not stir**, and keep eternal vigil over the **Pulsecore**.

To be Icebound is to **embrace the long watch** — and know you may not live to see its end.

## Quotes  
> “The frost remembers. So must we.”  
> — Icebound Inscription, Echo Hall

> “Stillness is not weakness. Stillness is strength waiting.”  
> — Stillheart Gromdir Stillhand

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


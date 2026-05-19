---
aliases: null
continent: ''
province: ''
society: '[[Tidebound of Draumhavn]]'
leadership:
- '[[Dagrin Thorne]]'
type: continent
status: draft
kind: island
tags: []
realm: '[[Renascita]]'
climate: ''
dominant_culture: ''
population_density: ''
---
![[f1e5b90b-25db-47d1-ab4a-f5ab53ee54af.png]]
## Overview

Draumhavn is a dwarven island-state nestled in a perilous cluster of volcanic isles between the continents of [[Pyrosia]] and [[Qethusiyya]]. It stands as a fortress-port, a neutral bastion of trade between empires too proud or too bitter to speak directly. The sea around it is treacherous, haunted by abyssal horrors and cursed shoals, making Draumhavn both gateway and gatekeeper.

Its lifeline lies beneath the earth: the **Deep Road**, a vast subterranean rail and tunnel network connecting it to the mainland dwarven cities—**Uftine**, **Mithral Hall**, **[[Magnus]]' Rest**—and, more recently, the [[Ferrun]] stronghold of **Thelassia**. But no Deep Road runs south. There lies only the **Wakened Trench**, a chasm of unspeakable depth and hungering darkness.

## Locations of Note
- [[Salt Cradle]] – The underground harbor and drydock heart of the city
- [[Stormgates]] – Outer sea-wall, studded with ballistae and elemental coils
- [[The Wakened Trench]] – Abyssal rift to the south, source of horrors

## The Deep Road
A secret, rune-reinforced tunnel system that connects Draumhavn to:
- [[Uftine Human]]
- [[Thundrakar]]
- [[Magnus’ Rest]]
- [[Thelassia]]

No tunnel runs south. The earth there falls away into the void.

> _“Stone holds fast, but south lies the Hunger’s Maw.”_

---

## Contents

<!-- AUTO-INJECTED-DYNAMIC-CONTENTS — delete this comment and everything below to opt out; safe to edit otherwise -->

### Regions

```dataview
LIST FROM ""
WHERE type = "region" AND continent = this.file.link
SORT file.name ASC
```

### Settlements

```dataview
TABLE WITHOUT ID
  file.link AS "Settlement",
  size AS "Size",
  controlled_by AS "Held by",
  status AS "Status"
FROM ""
WHERE type = "settlement" AND continent = this.file.link
SORT file.name ASC
```

### Mountain ranges

```dataview
LIST FROM ""
WHERE type = "range" AND continent = this.file.link
SORT file.name ASC
```

### Rivers & waterways

```dataview
LIST FROM ""
WHERE type = "waterway" AND continent = this.file.link
SORT file.name ASC
```

### Landmarks

```dataview
LIST FROM ""
WHERE type = "landmark" AND continent = this.file.link
SORT file.name ASC
```

### Characters located here

```dataview
TABLE WITHOUT ID
  file.link AS "Name",
  race AS "Race",
  affiliation AS "Affiliation"
FROM ""
WHERE type = "character" AND location = this.file.link
SORT file.name ASC
```

### Events here

```dataview
TABLE WITHOUT ID
  file.link AS "Event",
  era AS "Era",
  year_display AS "When"
FROM ""
WHERE type = "event" AND location = this.file.link
SORT year ASC
```

### Other notes referencing this place

```dataview
LIST WHERE contains(file.inlinks, this.file.link)
  AND !contains(string(file.path), "_meta/")
SORT file.name ASC
```


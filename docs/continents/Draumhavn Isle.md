---
type: continent
status: draft
kind: island
tags: []
realm: "[[Renascita]]"
climate: temperate-volcanic
dominant_culture: "[[The Tidebound of Draumhavn|Tidebound Dwarves]]"
population_density: sparse
controlled_by: "[[The Tidebound of Draumhavn]]"
leadership:
- "[[Dagrin Thorne]]"
terrain:
- volcanic isles
- sea cliffs
- underground tunnels
- ocean
inhabited_by:
- "[[The Tidebound of Draumhavn|Tidebound Dwarves]]"
cities:
- "[[Draumhavn]]"
provinces:
- "[[Salt Cradle]]"
- "[[Stormgates]]"
- "[[The Wakened Trench]]"
mountains: []
rivers: []
aliases:
- Draumhavn Isle
---
# Draumhavn Isle

*A perilous cluster of volcanic isles between [[Pyrosia]] and [[Qethusiyya]], dominated by the fortress-port of [[Draumhavn]] — seat of the [[The Tidebound of Draumhavn|Tidebound Dwarves]] and gateway between bitter empires.*

---

## Overview

Draumhavn Isle is a volcanic island-state nestled between the continents of [[Pyrosia]] and [[Qethusiyya]]. The island itself is a hostile landscape of sea cliffs, lava-scarred rock, and subterranean passages carved out over centuries by dwarven hands. The sea around it is treacherous — haunted by abyssal horrors and cursed shoals — making the isle both gateway and gatekeeper to the civilizations that surround it.

The island's only city, [[Draumhavn]], clings to its northern coast: a fortress-port and neutral bastion of trade between empires too proud or too bitter to speak directly. Beneath the surface, the **Deep Road** network connects the isle to the mainland dwarven cities of the realm.

To the south lies no road, no tunnel, no hope — only the **[[The Wakened Trench|Wakened Trench]]**, an abyssal rift of unspeakable depth and hungering darkness.

> _"Stone holds fast, but south lies the Hunger's Maw."_

## Geography

The isle is dominated by three distinct zones:

- **[[Salt Cradle]]** — the underground harbor and drydock carved into the island's northern cliffs, the beating heart of Draumhavn's maritime power
- **[[Stormgates]]** — the outer sea-wall fortifications studded with ballistae and elemental coils, guarding the approaches
- **[[The Wakened Trench]]** — the abyssal southern rift, a chasm of ungodly depth from which horrors have crawled for generations

---

## Contents

<!-- AUTO-INJECTED-DYNAMIC-CONTENTS — delete this comment and everything below to opt out; safe to edit otherwise -->

### Regions

```dataview
LIST FROM ""
WHERE type = "region" AND contains(file.outlinks, this.file.link)
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
WHERE type = "settlement" AND contains(file.outlinks, this.file.link)
SORT file.name ASC
```

### Mountain ranges

```dataview
LIST FROM ""
WHERE type = "range" AND contains(file.outlinks, this.file.link)
SORT file.name ASC
```

### Rivers & waterways

```dataview
LIST FROM ""
WHERE type = "waterway" AND contains(file.outlinks, this.file.link)
SORT file.name ASC
```

### Landmarks

```dataview
LIST FROM ""
WHERE type = "landmark" AND contains(file.outlinks, this.file.link)
SORT file.name ASC
```

### Characters located here

```dataview
TABLE WITHOUT ID
  file.link AS "Name",
  race AS "Race",
  affiliation AS "Affiliation"
FROM ""
WHERE type = "character" AND contains(file.outlinks, this.file.link)
SORT file.name ASC
```

### Events here

```dataview
TABLE WITHOUT ID
  file.link AS "Event",
  era AS "Era",
  year_display AS "When"
FROM ""
WHERE type = "event" AND contains(file.outlinks, this.file.link)
SORT year ASC
```

### Other notes referencing this place

```dataview
LIST WHERE contains(file.inlinks, this.file.link)
  AND !contains(string(file.path), "_meta/")
SORT file.name ASC
```

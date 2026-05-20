---
aliases: null
type: settlement
continent: "[[Draumhavn Isle]]"
leadership:
- "[[Dagrin Thorne]]"
status: draft
kind: city-state
tags: []
realm: "[[Renascita]]"
controlled_by: "[[The Tidebound of Draumhavn]]"
region: ''
size: large
populated_by:
- "[[The Tidebound of Draumhavn|Tidebound Dwarves]]"
era_founded: ''
---
![[f1e5b90b-25db-47d1-ab4a-f5ab53ee54af.png]]
## Overview

Draumhavn is the fortress-port city of [[The Tidebound of Draumhavn|the Tidebound Dwarves]], carved into the volcanic cliffs of [[Draumhavn Isle]]. It stands as a neutral bastion of trade between the continents of [[Pyrosia]] and [[Qethusiyya]] — empires too proud or too bitter to speak directly, but willing to let coin pass through dwarven hands.

Its lifeline lies beneath the earth: the **Deep Road**, a vast subterranean rail and tunnel network connecting it to the mainland dwarven cities — **Uftine**, **[[Magnus' Rest]]** — and, more recently, the [[Ferrun]] stronghold of **Thelassia**. Every tunnel runs north. No tunnel runs south.

> _"Every empire needs a city that belongs to no one. That is what we are."_
> — [[Dagrin Thorne]]

## The Deep Road

A secret, rune-reinforced tunnel network connecting Draumhavn to:
- [[Uftine Human]]
- [[Thundrakar]]
- [[Magnus' Rest]]
- [[Thelassia]]

No tunnel runs south. The earth there falls away into the void of the [[The Wakened Trench|Wakened Trench]].

## Key Districts

- [[Salt Cradle]] – The underground harbor and drydock heart of the city
- [[Stormgates]] – Outer sea-wall, studded with ballistae and elemental coils

---

## Contents

<!-- AUTO-INJECTED-DYNAMIC-CONTENTS — delete this comment and everything below to opt out; safe to edit otherwise -->

### Districts and landmarks inside

```dataview
LIST FROM ""
WHERE type = "landmark" AND contains(file.outlinks, this.file.link)
SORT file.name ASC
```

### Characters here

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

### Other notes referencing this settlement

```dataview
LIST WHERE contains(file.inlinks, this.file.link)
  AND !contains(string(file.path), "_meta/")
SORT file.name ASC
```

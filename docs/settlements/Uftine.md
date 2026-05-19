---
aliases: []
type: settlement
continent: '[[Arcturia]]'
leadership:
- '[[Gromdir Stillhand]]'
status: draft
tags: []
realm: '[[Renascita]]'
controlled_by: '[[Icebound of Uftine]]'
region: '[[Calderian Mountains]]'
size: ''
populated_by: []
era_founded: ''
---
![[2a6dc07c-2481-498a-96e7-b1cbae589bb1.png]]
## Overview

Uftine is the glacial capital of the [[Icebound]], a dwarven city-state carved from stone and ice deep in the northern reaches of the world. Built into a frozen mountainside and fortified by nature itself, Uftine is a bastion of cold precision, ancestral duty, and unbreakable engineering.

The city is lit by ice-embedded glowcrystals, its buildings carved with runes of frost and stability. Despite the endless winter beyond its walls, Uftine thrives through mastery of rune-bound [[Iceforging]], powerful frost-infused forges, and a culture of unshakable resilience.

Beneath its icy foundations lies the [[The Pulsecore|Pulsecore]], a sealed chamber containing the corrupted progeny of [[Zaratan]], the Great Elemental of Stone. This ancient burden, entombed by [[Muradin]], pulses faintly beneath the city—unseen by most, but felt in the stillness of the air and the weight of its silence.

Each dwarven city was founded over such a prison, and each holds vigil over a corrupted fragment of a Great Elemental. These corrupted cores, too dangerous to destroy, were carved away and sealed so the world might endure. Uftine is both sanctuary and seal.


## Locations of Note
- [[Frostforge]] – Uftine’s central coldforge, humming with runes of pressure
- [[Glacier Library]] – A frozen archive of rune-etched crystal slabs
- [[The Pulsecore]] – A hidden and ancient prison sealed within the glacier beneath the city
- [[Crystalward Gate]] – Main entrance to the city, guarded by rune-powered frost engines  

## Relations

- View the [[Draumhavn|Tidebound]] of [[Draumhavn]] as bold but reckless
- Respect the silence of [[Magnus’ Rest]], though find them overly insular
- Collaborate closely with [[Thundrakar]] on rune engineering, though debate philosophy  

> “Ice breaks slowly. That is its strength.”

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


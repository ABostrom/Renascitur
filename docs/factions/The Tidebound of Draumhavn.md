---
type: faction
status: draft
tags: []
realm:
- - Renascita
parent_faction:
- - Dwarven Holds
nature: mortal
importance: notable
alignment: lawful-neutral
society_form: martial
government: monarchy
economy: mercantile
seat:
- - Draumhavn
size: regional
allies: []
rivals: []
magic:
- - - Rune Magic
leadership: []
aliases:
- Tidebound
- Tidebound of Draumhavn
---
The [[Dwarf|dwarves]] of [[Draumhavn]] are known as the **[[The Tidebound of Draumhavn]]**. They are not mountain-folk but sea-dwellers, their lives shaped by storm and salt. Rather than religion, they follow a **Creed**—a philosophy of survival, discipline, and bond.

They revere the elemental forces of the sea without worshipping them, naming them:

- He Who Hungers ([[Leviathan]]): hunger, darkness, pressure
- She Who Wakes ([[Tempus]]): fury, rebirth, awakening

> _“We do not pray. We endure.”_ —[[The Tidebound of Draumhavn]] Saying

## Government: Naval Hierarchy
Draumhavn is ruled like a fleet, not a kingdom.

### High Tide Admiral: [[Dagrin Thorne]]

- Commands the city from the harbored warship _[[Leviathan]]’s Mercy_
- Enforces the **Code of Salt**, etched in a coral slab in the harbor square

Beneath him:
- **Stormcaptains** – Clan leaders and district commanders
- **Wavespeakers** – Oceanic strategists and tide-readers
- **Chainmasters** – Dockmasters and engineers
## Society & Industry

### Shipwright Clans
Draumhavn’s three great clans form the bedrock of its maritime power:
- [[Clan Blackwake]] – Leviathan-hunters, brute warships
- [[Clan Brinevein]] – Merchants and salvagers, sleek and swift
- [[Clan Deepforge]] – Submersibles and mechanized hulls

Each clan forges ships in its own style, with vessels detailed on their respective pages.
### Tideforging
Draumhavn’s unique craft, salt-tempered and rune-bound:

- Forging timed to the tides
- Metal quenched in brine, not water
- Runes sung into steel
See: [[Tideforging]]

### Salt-Blessed
Some [[The Salt-Blessed|Tidebound]] return from the deep changed:

- Gills, glowing veins, barnacle growths
- Deepwater vision, storm-sense, abyssal influence
- Feared and honoured; many serve in the silent order known as the [[Abysswatch]]
See: [[The Salt-Blessed]]

---

## Contents

<!-- AUTO-INJECTED-DYNAMIC-CONTENTS — delete this comment and everything below to opt out; safe to edit otherwise -->

### Sub-factions

```dataview
LIST FROM ""
WHERE type = "faction" AND contains(file.outlinks, this.file.link)
SORT file.name ASC
```

### Members

```dataview
TABLE WITHOUT ID
  file.link AS "Name",
  race AS "Race",
  location AS "Location"
FROM ""
WHERE type = "character" AND contains(file.outlinks, this.file.link)
SORT file.name ASC
```

### Organisations within

```dataview
LIST FROM ""
WHERE type = "organisation" AND contains(file.outlinks, this.file.link)
SORT file.name ASC
```

### Events involving this faction

```dataview
TABLE WITHOUT ID
  file.link AS "Event",
  era AS "Era",
  year_display AS "When"
FROM ""
WHERE type = "event" AND contains(participants, this.file.link)
SORT year ASC
```

### Other notes referencing this faction

```dataview
LIST WHERE contains(file.inlinks, this.file.link)
  AND !contains(string(file.path), "_meta/")
SORT file.name ASC
```


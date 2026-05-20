---
type: faction
status: draft
tags: []
realm: "[[Renascita]]"
parent_faction: "[[Dwarven Holds]]"
nature: mortal
importance: notable
alignment: lawful-neutral
society_form: feudal
government: monarchy
economy: mining
seat: "[[Uftine]]"
size: regional
allies: []
rivals: []
magic:
- "[[Rune Magic]]"
leadership:
- "[[Gromdir Stillhand]]"
aliases:
- Icebound
- Icebound of Uftine
era_founded: "[[Age of Forging]]"
---
The [[Dwarf|dwarves]] of [[Uftine]] are known collectively as the [[The Icebound of Uftine]]—those who are bound to the glacier not just in body, but in purpose. This identity defines their culture, their duty, and their [[soul]]. Among them, the term Icebreakers refers more specifically to those who carve the frozen stone, forge in the cold, and mine the glacier’s deep veins. They are artisans, engineers, and delvers who shape the silence beneath Uftine.
  
>They are stoic, highly disciplined, and bound by deep tradition.

They channel the teachings of [[Muradin]], the ancient [[Grundthain]], through a refined form of [[The Icebound of Uftine]] Rune Magic—blending frost, pressure, and silence with the power of runic invocation. They also honour [[Magnus]], the newer dwarven god, as the divine successor who continues [[Muradin]]’s legacy of endurance and craft.


Though they do not know it, the [[The Icebound of Uftine]]’s elemental rune tradition resonates deeply with the Great Elemental [[Zaratan]], the Unmoving Stone. This affinity expresses itself in their runes of pressure, their glacial patience, and their enduring resistance to corruption. Like all dwarven clans, this connection was not of their choosing—and remains largely unknown to them.

> “Hold fast, break nothing but the ice.” — Icebreaker Proverb

## Leadership: The [[The Icebound of Uftine]] Thane

Uftine is ruled by a singular leader known as the [[The Icebound of Uftine]] Thane, the embodiment of stillness, memory, and burden. The current Icebound Thane is [[Gromdir Stillhand]], a frost-veined elder with a mind like bedrock and a silence that commands reverence. He serves as both sovereign and spiritual anchor—his word carries the weight of ice millennia deep.
  
Their rune magic embraces:
- **Pressure over heat**
- **Stillness over spark**
- **Memory over change**

### Coldsmithing

[[Iceforging]] is the sacred art of the [[The Icebound of Uftine]]:
- Metals are tempered through frost-pressure rather than fire
- Ice is used as both mold and medium for rune channeling
- Their alloys are dense, crystalline, and nearly unbreakable

### The Uftine Express

An extension of the [[Deep Road]], the [[Uftine Express]] is a marvel of subterranean glacial engineering:
- Heated rune-rails resist ice creep
- Pressure valves and wind-vents harmonize tunnel flow
- Regularly connects to [[Draumhavn]], [[Thundrakar]], and [[Magnus' Rest]]


## Beliefs

- The [[The Icebound of Uftine]] do not worship, but they revere the **Glacier Mother**, a symbolic manifestation of endurance, clarity, and memory
- They believe ice remembers—every crack, fracture, and whisper etched into its ancient mass
- [[Aberrations]] are seen as **entropy given form**—to be held, not destroyed
- Their reverence for [[Muradin]] and [[Magnus]] is tied to their belief in preservation through craftsmanship and silence

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


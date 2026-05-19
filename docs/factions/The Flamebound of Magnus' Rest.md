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
economy: mining
seat: [[Magnus' Rest]]
size: regional
allies: []
rivals: []
magic:
- - - Rune Magic
- - - Forge Magic
leadership: []
aliases:
- Flamebound
- Flamebound of Magnus' Rest
---
## Cultural Themes – The [[The Flamebound of Magnus' Rest]] [[Dwarf|Dwarves]]

The [[Dwarf|dwarves]] of Magnus’ Rest are known as the **[[The Flamebound of Magnus' Rest]]**, and they live by the creed of **rebirth through fire**. Fire is more than a tool—it is a crucible of the [[soul]]. Through radiant heat, they believe that all things are tested, all weakness burned away.

They revere [[Magnus]] not only as a divine protector but as the living embodiment of radiant defiance. His doctrine, passed down through the [[Magnesium Devouts]], teaches that in the face of overwhelming night, the only righteous answer is to burn brighter.

The [[The Flamebound of Magnus' Rest]] value:
- **Sacrifice through hardship**
- **Perseverance under pressure**
- **Creation as a sacred act**

To forge is to pray. To endure is to worship.


## Radiant Forging – Sacred Craft of the [[The Flamebound of Magnus' Rest]]

The [[The Flamebound of Magnus' Rest]] are masters of **Radiant Forging**, a sacred and arduous discipline that merges divine heat, volcanic material, and dwarven craftsmanship.

All true Radiant Forging is performed within the [[Everburn Forges]], which are powered directly by the [[Eternal Flame]]. The process requires not only metallurgical skill but spiritual worthiness—flame, in [[The Flamebound of Magnus' Rest]] belief, reveals the truth of all things.

Radiant-forged weapons and armor:

- Glow with inner fire, especially in the presence of [[aberrations]] or corrupted beings  
- Never rust or cool fully; they carry the warmth of the Eternal Flame itself  
- Are often etched with runes of protection, memory, or purification  
- Can only be completed under the guidance of the [[Magnesium Devouts]]

Some relics of the First Flame, like the [[Sunforged Anvil]] and the sacred **Everburn Blades**, are considered holy objects, believed to carry echoes of [[Muradin]] and [[Magnus]]’ divine intent.

> "The flame does not shape metal. It shapes the [[soul]]. The steel is just what survives the truth."  
> — [[Maerra Vulkess]], High Devout of the [[Watch of the Dying Flame]]

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


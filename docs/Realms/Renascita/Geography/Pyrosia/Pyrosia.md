---
type: continent
terrain:
- mountains
- volcanic plains
- coastal cliffs
- temperate forests
- grasslands
- tropical bays
- river deltas
inhabited_by:
- '[[Leonin]]'
- '[[Orc]]'
- '[[Flamebound|Flamebound Dwarves]]'
- '[[Goliath]]'
- '[[Gnome]]'
- '[[Imperial Human]]'
provinces:
- '[[Ashen Plains]]'
- '[[Ashgatar]]'
- '[[Ember Peaks]]'
- '[[Flame Coast]]'
- '[[Frontier''s Edge]]'
- '[[Burnt Reach]]'
cities:
- '[[Lux Oescus]]'
- '[[Old Westgate]]'
- '[[Port Ardere]]'
- '[[Raining Bay]]'
- '[[Lion’s Rest]]'
- '[[Magnus’ Rest]]'
mountains:
- '[[Mount Earthspur]]'
- '[[Ashen Range]]'
- '[[Dawnspire Mountains]]'
- '[[Veilsmoke Ridge]]'
rivers:
- '[[Redwash River]]'
- '[[Glowtongue Stream]]'
- '[[Moltren Delta]]'
status: draft
tags: []
realm: '[[Renascita]]'
climate: ''
dominant_culture: ''
population_density: ''
---
**Pyrosia** is a vast and diverse land of elemental tension, tectonic fire, and sprawling nations. Bordered by volcanic coastlines and inland mountain arcs, the continent hosts an enormous range of biomes — from the charred [[Ashgatar]] highlands to the verdant woodlands near [[Raining Bay]].

The region is shared by an array of peoples, from the imperial courts of the [[Imperial Human]] to the fire-worshipping [[Flamebound Dwarves]] of [[Magnus' Rest]], and the coastal strongholds of the [[Leonin]] at [[Lion's Rest]].

The [[Ashen Range]] and [[Veilsmoke Ridge]] dominate the center of the continent, forming natural borders and spiritual frontiers. Rivers like the [[Redwash River]] flow southward from the molten peaks, bringing warmth and danger to the lowlands.



This is the content that is majority controlled by the [[Firebrand Empire]] although some of the more remote regions are as yet untamed and unexplored. 

# Flame Coast

![[Port Ardere]]

![[Old Westgate]]

# Ashen Plains

![[The Bright Tavern]]

![[The Ruins of Elturel]]

![[The Forge of Souls]]

# [[Ember Peaks]]

![[Mount Earthspur]]

![[Raining Bay]]

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


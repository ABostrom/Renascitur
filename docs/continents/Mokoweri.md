---
type: continent
terrain:
- jungle
- rainforests
- river basins
- coastal lowlands
- cloud forests
- highland ridges
inhabited_by:
- [[Mokuun]]
- [[Saurian]]
- [[Mokoweri Human]]
provinces:
- [[Obsidian Peaks]]
- [[Ruins of the Ancients]]
- [[Canopy Height]]
- [[Verdant Coast]]
- [[Riverlands]]
cities:
- [[Aeloria]]
- [[Port Zyranzaru]]
- [[Waterfall City]]
mountains:
- [[Obsidian Spine]]
- [[Jal'korran Ridge]]
- - - Temple Heights
rivers:
- [[Zyran River]]
- [[Tir'Zal Tributary]]
- [[Coatl's Vein]]
- [[Mira'ko Stream]]
- - - River of Ancients
status: draft
tags: []
realm: [[Renascita]]
climate: ''
dominant_culture: ''
population_density: ''
aliases:
- Mokoweri
- Mokoweri Island
---
**Mokoweri** is a lush and vibrant continent of tangled life — a primeval realm where rivers run like veins and trees stretch toward the sun in layers of living canopy. It is the home of the [[Mokuun]], the [[Mokoweri Human]], and the bioengineered [[Saurian]], all united in their reverence for the sacred world tree [[Irasandra]].

The vast [[Zyran River]] winds through the [[Riverlands]] and past cities like [[Aeloria]] and [[Port Zyranzaru]], fed by thousands of hidden tributaries such as the [[Tir'Zal Tributary]] and [[Coatl's Vein]]. Towering ridges like the [[Obsidian Spine]] loom above the forest, hiding ancient [[Solaran]] ruins and pulse-reactive flora.

To outsiders, Mokoweri is a realm of mystery and danger — to its people, it is a living soul.

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


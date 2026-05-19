---
type: region
status: draft
continent: '[[Pyrosia]]'
tags: []
realm: '[[Renascita]]'
region: '[[Ashen Plains]]'
climate: volcanic
terrain: []
dominant_culture: ''
population_density: ''
---
The Obsidian Fortress, the formidable stronghold of General Tau and the central bastion of [[Ishna]]'s forces, is located in a desolate and inhospitable region of [[Pyrosia]] known as the Scorched Wastes. This harsh, barren expanse of land stretches for miles in every direction, with little sign of life or vegetation.

The Scorched Wastes are aptly named, as the very ground seems to radiate heat, creating a shimmering mirage that distorts the horizon. The earth is cracked and parched, and jagged rock formations jut out of the arid landscape like the teeth of some ancient, slumbering beast.

The Obsidian Fortress itself is a towering monolith of obsidian, rising from the desolation like a dark sentinel. Its imposing walls seem to meld with the surrounding scorched earth, making it blend seamlessly with its environment. The fortress is constructed with a fusion of dark stone and a mysterious black metal, both materials seemingly impervious to the relentless heat of the Scorched Wastes.

Massive obsidian spires and battlements adorn the fortress, giving it an ominous, otherworldly appearance. The outer walls are adorned with wickedly sharp spikes and intricate, rune-covered arches. The entire structure is a testament to the dark power and malevolence that resides within.

General Tau's stronghold is surrounded by a formidable moat of molten lava, a natural barrier that deters all but the most daring intruders. Bridge-like pathways made of reinforced obsidian span the molten abyss, granting access to the inner sanctum to those who dare to approach.

Within the Obsidian Fortress, secrets of [[Ishna]]'s dark magic and her relentless pursuit of power are rumored to be hidden away. [[Unimus]] and his vassals know that they face a daunting challenge to breach these dark walls, confront General Tau, and bring an end to the oppressive reign of [[Ishna]]'s forces.

---

## Contents

<!-- AUTO-INJECTED-DYNAMIC-CONTENTS — delete this comment and everything below to opt out; safe to edit otherwise -->

### Settlements

```dataview
TABLE WITHOUT ID
  file.link AS "Settlement",
  size AS "Size",
  controlled_by AS "Held by"
FROM ""
WHERE type = "settlement" AND region = this.file.link
SORT file.name ASC
```

### Landmarks

```dataview
LIST FROM ""
WHERE type = "landmark" AND region = this.file.link
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

### Other notes referencing this region

```dataview
LIST WHERE contains(file.inlinks, this.file.link)
  AND !contains(string(file.path), "_meta/")
SORT file.name ASC
```


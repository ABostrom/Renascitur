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
Owner: [Breona](https://docs.google.com/document/d/17UBeTKd3Fl4TwHLNa-uxBUu0vXz8Ud6m6s0cmIC5HpY/edit#heading=h.w5rdmvg40p64)

This tavern is a roadside tavern along the [[Vialux]] between [[Lion’s Rest]] and [[Lux Oescus]].

The tavern is owned by a [[Human]] woman named: [[Breona]]. She is a strong tempered woman, who will take no nonsense.

  

The tavern is not exclusively for citizens of the empire. But non-citizens by extortionate rates, and are required to sit in a segregated area. Bar fights naturally result from the animosity between citizens and foreigners, and the shunned.

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


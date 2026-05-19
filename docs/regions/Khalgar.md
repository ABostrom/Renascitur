---
type: region
status: draft
continent: '[[Qethusiyya]]'
tags: []
realm: '[[Renascita]]'
climate: arid
terrain: []
dominant_culture: ''
population_density: ''
settlements: []
---
A low mist-haunted region southeast of the [[Kaldar Range]], Khalgar is plagued by memory-warping fogs and abandoned villages. Glyphs distort here, refusing to hold form. Travelers lose track of time, and sometimes of self.

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
WHERE type = "settlement" AND string(region) = string(this.file.link)
SORT file.name ASC
```

### Landmarks

```dataview
LIST FROM ""
WHERE type = "landmark" AND string(region) = string(this.file.link)
SORT file.name ASC
```

### Characters located here

```dataview
TABLE WITHOUT ID
  file.link AS "Name",
  race AS "Race",
  affiliation AS "Affiliation"
FROM ""
WHERE type = "character" AND string(location) = string(this.file.link)
SORT file.name ASC
```

### Events here

```dataview
TABLE WITHOUT ID
  file.link AS "Event",
  era AS "Era",
  year_display AS "When"
FROM ""
WHERE type = "event" AND string(location) = string(this.file.link)
SORT year ASC
```

### Other notes referencing this region

```dataview
LIST WHERE contains(file.inlinks, this.file.link)
  AND !contains(string(file.path), "_meta/")
SORT file.name ASC
```


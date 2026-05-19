---
type: region
status: stub
continent: '[[Qethusiyya]]'
tags: []
realm: '[[Renascita]]'
climate: arid
terrain:
- coast
dominant_culture: ''
population_density: ''
settlements: []
---
The western coastline of [[Qethusiyya]], the Shazir Coast is a region of spell-sailed trade vessels, glowing reef glyphs. Its cliffside ports shimmer like glass in the sun—and whisper at night.

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


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
settlements: []
---
Candle Keep was a famous library of great renown the world over. Before the [[Psychic Schism]] it contained tomes that could change the very nature of the world. Since the [[Psychic Schism|schism]] the keep has fallen into disrepair, and a small number of scholars have managed to keep the library safeguarded. Though knowledge of its location, and the tomes contained within, are forbidden within the [[Firebrand Empire]] there are some that would seek the lore for their own purposes.

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


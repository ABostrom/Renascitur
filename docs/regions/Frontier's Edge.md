---
aliases:
- Frontier's Edge
tags:
- province
- region
type: region
status: draft
continent: [[Pyrosia]]
realm: [[Renascita]]
climate: volcanic
terrain: []
dominant_culture: ''
population_density: ''
settlements: []
---
## Overview
A war-torn and reclaimed expanse once ruled by [[Orc|orcs]] and aberrant creatures. Now it stands as the Empire’s final shield wall, fiercely protected by border clans and militant orders.

## Major Cities
- [[Ashgatar]]

## Notes
Seen as a punishment posting by some, a sacred duty by others. Imperators here are often hardened veterans or ascendant generals.

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
WHERE type = "settlement" AND contains(file.outlinks, this.file.link)
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

### Other notes referencing this region

```dataview
LIST WHERE contains(file.inlinks, this.file.link)
  AND !contains(string(file.path), "_meta/")
SORT file.name ASC
```


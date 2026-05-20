---
aliases:
- Flame Coast
tags:
- province
- region
type: region
status: draft
continent: "[[Pyrosia]]"
realm: "[[Renascita]]"
climate: volcanic
terrain:
- coast
dominant_culture: ''
population_density: ''
settlements: []
---
## Overview
Strategically vital, the Flame Coast manages the Empire’s naval strength, diplomatic outreach, and maritime commerce. Its skies are ever stormy, and its towers shine with arcane light.

## Major Cities
- [[Raining Bay]]

## Notes
Often under the guidance of a cosmologically inclined Imperator from [[House Lyrandar]].

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


---
aliases:
- Ashen Plains
tags:
- province
- region
type: region
status: draft
continent: '[[Pyrosia]]'
realm: '[[Renascita]]'
climate: volcanic
terrain: []
dominant_culture: ''
population_density: ''
settlements: []
---
## Overview
The political and cultural heartland of the Empire. Fertile, stable, and heavily patrolled, this region is home to many noble houses, institutions of power, and imperial bureaucracy.

## Major Cities
- [[Lion’s Rest]]
- [[Lux Oescus]]
- [[Candle Keep]]
- [[Port Ardere]]

## Notes
Home to the capital and central bureaucracy. The seat of the High Imperator.

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


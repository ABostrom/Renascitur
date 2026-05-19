---
type: index
status: canon
tags:
- view
view: Mokoweri — Overview
---
# Mokoweri — Overview

*Everything inside the Mokoweri continent.*

## Regions
```dataview
LIST FROM "" WHERE type = "region" AND continent = [[Mokoweri]]
SORT file.name ASC
```

## Settlements
```dataview
TABLE WITHOUT ID
  file.link AS "Settlement",
  size AS "Size",
  controlled_by AS "Held by"
FROM ""
WHERE type = "settlement" AND continent = [[Mokoweri]]
SORT file.name ASC
```

## Landmarks
```dataview
LIST FROM "" WHERE type = "landmark" AND continent = [[Mokoweri]]
SORT file.name ASC
```

## Ranges
```dataview
LIST FROM "" WHERE type = "range" AND continent = [[Mokoweri]]
SORT file.name ASC
```

## Waterways
```dataview
LIST FROM "" WHERE type = "waterway" AND continent = [[Mokoweri]]
SORT file.name ASC
```

## Characters located here
```dataview
TABLE WITHOUT ID
  file.link AS "Name",
  race AS "Race",
  affiliation AS "Faction"
FROM ""
WHERE type = "character" AND location = [[Mokoweri]]
SORT file.name ASC
```

## Events here
```dataview
TABLE WITHOUT ID file.link AS "Event", era AS "Era", year_display AS "When"
FROM "" WHERE type = "event" AND location = [[Mokoweri]]
SORT year ASC
```

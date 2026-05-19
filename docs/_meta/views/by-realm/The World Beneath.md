---
type: index
status: canon
tags:
- view
view: The World Beneath — Overview
---
# The World Beneath — Overview

*Everything inside the The World Beneath continent.*

## Regions
```dataview
LIST FROM "" WHERE type = "region" AND continent = [[The World Beneath]]
SORT file.name ASC
```

## Settlements
```dataview
TABLE WITHOUT ID
  file.link AS "Settlement",
  size AS "Size",
  controlled_by AS "Held by"
FROM ""
WHERE type = "settlement" AND continent = [[The World Beneath]]
SORT file.name ASC
```

## Landmarks
```dataview
LIST FROM "" WHERE type = "landmark" AND continent = [[The World Beneath]]
SORT file.name ASC
```

## Ranges
```dataview
LIST FROM "" WHERE type = "range" AND continent = [[The World Beneath]]
SORT file.name ASC
```

## Waterways
```dataview
LIST FROM "" WHERE type = "waterway" AND continent = [[The World Beneath]]
SORT file.name ASC
```

## Characters located here
```dataview
TABLE WITHOUT ID
  file.link AS "Name",
  race AS "Race",
  affiliation AS "Faction"
FROM ""
WHERE type = "character" AND location = [[The World Beneath]]
SORT file.name ASC
```

## Events here
```dataview
TABLE WITHOUT ID file.link AS "Event", era AS "Era", year_display AS "When"
FROM "" WHERE type = "event" AND location = [[The World Beneath]]
SORT year ASC
```

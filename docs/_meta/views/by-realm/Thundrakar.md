---
type: index
status: canon
tags:
- view
view: Thundrakar — Overview
---
# Thundrakar — Overview

*Everything inside the Thundrakar continent.*

## Regions
```dataview
LIST FROM "" WHERE type = "region" AND continent = [[Thundrakar]]
SORT file.name ASC
```

## Settlements
```dataview
TABLE WITHOUT ID
  file.link AS "Settlement",
  size AS "Size",
  controlled_by AS "Held by"
FROM ""
WHERE type = "settlement" AND continent = [[Thundrakar]]
SORT file.name ASC
```

## Landmarks
```dataview
LIST FROM "" WHERE type = "landmark" AND continent = [[Thundrakar]]
SORT file.name ASC
```

## Ranges
```dataview
LIST FROM "" WHERE type = "range" AND continent = [[Thundrakar]]
SORT file.name ASC
```

## Waterways
```dataview
LIST FROM "" WHERE type = "waterway" AND continent = [[Thundrakar]]
SORT file.name ASC
```

## Characters located here
```dataview
TABLE WITHOUT ID
  file.link AS "Name",
  race AS "Race",
  affiliation AS "Faction"
FROM ""
WHERE type = "character" AND location = [[Thundrakar]]
SORT file.name ASC
```

## Events here
```dataview
TABLE WITHOUT ID file.link AS "Event", era AS "Era", year_display AS "When"
FROM "" WHERE type = "event" AND location = [[Thundrakar]]
SORT year ASC
```

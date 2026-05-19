---
type: index
status: canon
tags:
- view
view: Draumhavn — Overview
---
# Draumhavn — Overview

*Everything inside the Draumhavn continent.*

## Regions
```dataview
LIST FROM "" WHERE type = "region" AND string(continent) = "[[Draumhavn]]"
SORT file.name ASC
```

## Settlements
```dataview
TABLE WITHOUT ID
  file.link AS "Settlement",
  size AS "Size",
  controlled_by AS "Held by"
FROM ""
WHERE type = "settlement" AND string(continent) = "[[Draumhavn]]"
SORT file.name ASC
```

## Landmarks
```dataview
LIST FROM "" WHERE type = "landmark" AND string(continent) = "[[Draumhavn]]"
SORT file.name ASC
```

## Ranges
```dataview
LIST FROM "" WHERE type = "range" AND string(continent) = "[[Draumhavn]]"
SORT file.name ASC
```

## Waterways
```dataview
LIST FROM "" WHERE type = "waterway" AND string(continent) = "[[Draumhavn]]"
SORT file.name ASC
```

## Characters located here
```dataview
TABLE WITHOUT ID
  file.link AS "Name",
  race AS "Race",
  affiliation AS "Faction"
FROM ""
WHERE type = "character" AND string(location) = "[[Draumhavn]]"
SORT file.name ASC
```

## Events here
```dataview
TABLE WITHOUT ID file.link AS "Event", era AS "Era", year_display AS "When"
FROM "" WHERE type = "event" AND string(location) = "[[Draumhavn]]"
SORT year ASC
```

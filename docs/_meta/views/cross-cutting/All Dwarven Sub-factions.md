---
type: index
status: canon
tags:
- view
view: All Dwarven Sub-factions
---
# All Dwarven Sub-factions

*The 4 Dwarven holds + their characters.*

## The four holds
```dataview
LIST FROM "" WHERE type = "faction" AND parent_faction = "[[Dwarven Holds]]"
SORT file.name ASC
```

## All Dwarven characters
```dataview
TABLE WITHOUT ID
  file.link AS "Name",
  affiliation AS "Hold",
  role AS "Role"
FROM "" WHERE type = "character" AND race = "[[Dwarf]]"
SORT affiliation ASC, file.name ASC
```

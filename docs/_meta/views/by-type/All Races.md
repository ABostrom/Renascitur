---
type: index
status: canon
tags:
- view
view: All Races
---
# All Races

*Races and variants, grouped by lineage.*

```dataview
TABLE WITHOUT ID
  file.link AS "Race",
  lineage AS "Lineage",
  parent_race AS "Parent",
  nature AS "Nature",
  importance AS "Importance"
FROM ""
WHERE type = "race"
SORT lineage ASC, file.name ASC
```

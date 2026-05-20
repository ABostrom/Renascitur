---
type: index
status: canon
tags:
- view
view: All Settlements
---
# All Settlements

*Cities, towns, holds, and villages.*

```dataview
TABLE WITHOUT ID
  file.link AS "Settlement",
  continent AS "Continent",
  region AS "Region",
  size AS "Size",
  controlled_by AS "Controlled by",
  importance AS "Importance"
FROM ""
WHERE type = "settlement"
SORT continent ASC, file.name ASC
```

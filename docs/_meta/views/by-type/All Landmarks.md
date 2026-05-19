---
type: index
status: canon
tags:
- view
view: All Landmarks
---
# All Landmarks

*Points of interest, ruins, sacred sites, in-city districts.*

```dataview
TABLE WITHOUT ID
  file.link AS "Landmark",
  continent AS "Continent",
  region AS "Region",
  inside AS "Inside",
  nature AS "Nature"
FROM ""
WHERE type = "landmark"
SORT continent ASC, file.name ASC
```

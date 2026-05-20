---
type: index
status: canon
tags:
- view
view: All Continents
---
# All Continents

*Major landmasses across all realms.*

```dataview
TABLE WITHOUT ID
  file.link AS "Continent",
  realm AS "Realm",
  climate AS "Climate",
  status AS "Status"
FROM ""
WHERE type = "continent"
SORT realm ASC, file.name ASC
```

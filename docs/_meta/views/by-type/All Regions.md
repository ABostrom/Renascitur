---
type: index
status: canon
tags:
- view
view: All Regions
---
# All Regions

*Provinces and political subdivisions, grouped by continent.*

```dataview
TABLE WITHOUT ID
  file.link AS "Region",
  continent AS "Continent",
  climate AS "Climate",
  status AS "Status"
FROM ""
WHERE type = "region"
SORT continent ASC, file.name ASC
```

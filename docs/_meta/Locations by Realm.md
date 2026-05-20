---
type: index
status: canon
tags:
- meta
---
# Locations by Realm

```dataview
TABLE WITHOUT ID
  file.link AS "Place",
  type AS "Kind"
FROM ""
WHERE contains(list("settlement","landmark","region","range","waterway","continent"), type)
GROUP BY continent
SORT continent ASC, type ASC, file.name ASC
```

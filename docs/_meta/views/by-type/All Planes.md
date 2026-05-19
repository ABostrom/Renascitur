---
type: index
status: canon
tags:
- view
view: All Planes
---
# All Planes

*Non-Renascita realms (outer planes, elemental planes, etc.).*

```dataview
TABLE WITHOUT ID
  file.link AS "Plane",
  type AS "Type",
  status AS "Status"
FROM "planes"
SORT file.name ASC
```

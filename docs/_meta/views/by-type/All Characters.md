---
type: index
status: canon
tags:
- view
view: All Characters
---
# All Characters

*Every named NPC across the world.*

```dataview
TABLE WITHOUT ID
  file.link AS "Name",
  race AS "Race",
  culture AS "Culture",
  affiliation AS "Faction",
  location AS "Location",
  gender AS "Gender",
  living_status AS "Status"
FROM ""
WHERE type = "character"
SORT affiliation ASC, file.name ASC
```

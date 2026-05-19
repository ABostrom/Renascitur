---
type: index
status: canon
tags:
- view
view: Notable NPCs
---
# Notable NPCs

*Characters with importance: major or legendary.*

```dataview
TABLE WITHOUT ID
  file.link AS "Name",
  race AS "Race",
  affiliation AS "Faction",
  role AS "Role",
  importance AS "Tier"
FROM ""
WHERE type = "character" AND (importance = "major" OR importance = "legendary")
SORT importance ASC, file.name ASC
```

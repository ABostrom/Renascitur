---
type: index
status: canon
tags:
- view
view: Characters by Role
---
# Characters by Role

*NPCs grouped by what they do.*

```dataview
TABLE WITHOUT ID file.link AS "Name", race AS "Race", affiliation AS "Faction"
FROM "" WHERE type = "character" AND role != null AND length(role) > 0
GROUP BY role
```

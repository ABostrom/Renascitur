---
type: index
status: canon
tags:
- view
view: All Factions
---
# All Factions

*Political and organized groups. Includes Houses (kind: house).*

```dataview
TABLE WITHOUT ID
  file.link AS "Faction",
  realm AS "Realm",
  society_form AS "Form",
  government AS "Government",
  seat AS "Seat",
  size AS "Scale",
  importance AS "Importance"
FROM ""
WHERE type = "faction"
SORT realm ASC, importance ASC, file.name ASC
```

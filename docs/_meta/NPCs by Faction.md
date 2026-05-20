---
type: index
status: canon
tags:
- meta
---
# NPCs by Faction

```dataview
TABLE WITHOUT ID
  file.link AS "Character",
  race AS "Race",
  location AS "Location"
FROM ""
WHERE type = "character"
GROUP BY affiliation
SORT affiliation ASC, file.name ASC
```

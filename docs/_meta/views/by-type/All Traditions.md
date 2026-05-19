---
type: index
status: canon
tags:
- view
view: All Traditions
---
# All Traditions

*Rituals, practices, customs.*

```dataview
TABLE WITHOUT ID
  file.link AS "Tradition",
  culture AS "Culture",
  realm AS "Realm",
  era AS "Era"
FROM ""
WHERE type = "tradition"
SORT culture ASC, file.name ASC
```

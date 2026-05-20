---
type: index
status: canon
tags:
- view
view: Legendary Things
---
# Legendary Things

*Anything tagged as legendary in importance.*

```dataview
TABLE WITHOUT ID file.link AS "Note", type AS "Type", era AS "Era"
FROM "" WHERE importance = "legendary"
SORT type ASC, file.name ASC
```

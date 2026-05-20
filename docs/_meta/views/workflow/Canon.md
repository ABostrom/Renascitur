---
type: index
status: canon
tags:
- view
view: Canon
---
# Canon

*Notes marked canonical.*

```dataview
TABLE WITHOUT ID file.link AS "Note", type AS "Type"
FROM "" WHERE status = "canon" AND !contains(string(file.path), "_meta/")
SORT type ASC, file.name ASC
```

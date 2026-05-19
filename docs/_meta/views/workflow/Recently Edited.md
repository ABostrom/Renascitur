---
type: index
status: canon
tags:
- view
view: Recently Edited
---
# Recently Edited

*30 most-recently-modified notes.*

```dataview
TABLE WITHOUT ID file.link AS "Note", type AS "Type", file.mtime AS "When"
FROM "" WHERE !contains(string(file.path), "_meta/")
SORT file.mtime DESC
LIMIT 30
```

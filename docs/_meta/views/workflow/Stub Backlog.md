---
type: index
status: canon
tags:
- view
view: Stub Backlog
---
# Stub Backlog

*Notes whose structure is in place but prose unwritten.*

```dataview
TABLE WITHOUT ID file.link AS "Note", type AS "Type", file.folder AS "Folder"
FROM ""
WHERE status = "stub" AND !contains(string(file.path), "_meta/")
SORT type ASC, file.name ASC
```

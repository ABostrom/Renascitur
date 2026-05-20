---
type: index
status: canon
tags:
- view
view: Drafts
---
# Drafts

*Notes in draft (typed but not yet canonical).*

```dataview
TABLE WITHOUT ID file.link AS "Note", type AS "Type", file.mtime AS "Last edit"
FROM ""
WHERE status = "draft" AND !contains(string(file.path), "_meta/")
SORT file.mtime DESC
```

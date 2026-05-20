---
type: index
status: canon
tags:
- view
view: All Artifacts
---
# All Artifacts

*Named magical items and legendary objects.*

```dataview
TABLE WITHOUT ID
  file.link AS "Artifact",
  era_of_creation AS "Created",
  current_bearer AS "Bearer",
  cursed AS "Cursed",
  divine AS "Divine",
  importance AS "Importance"
FROM ""
WHERE type = "artifact"
SORT importance ASC, file.name ASC
```

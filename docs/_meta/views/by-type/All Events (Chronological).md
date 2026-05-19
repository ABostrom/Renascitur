---
type: index
status: canon
tags:
- view
view: All Events (Chronological)
---
# All Events (Chronological)

*Historical events across all four Ages.*

```dataview
TABLE WITHOUT ID
  file.link AS "Event",
  era AS "Era",
  year_display AS "When",
  location AS "Where",
  importance AS "Importance",
  status AS "Status"
FROM ""
WHERE type = "event"
SORT era ASC, year ASC, file.name ASC
```

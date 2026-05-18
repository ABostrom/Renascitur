---
type: index
status: canon
tags:
- meta
---
# Timeline

All events sorted chronologically.

```dataview
TABLE WITHOUT ID
  file.link AS "Event",
  era AS "Era",
  year AS "Year"
FROM ""
WHERE type = "event"
SORT era ASC, year ASC, file.name ASC
```

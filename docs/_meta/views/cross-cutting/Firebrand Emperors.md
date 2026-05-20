---
type: index
status: canon
tags:
- view
view: Firebrand Emperors
---
# Firebrand Emperors

*All Emperors and Empresses of Firebrand (historical and current).*

```dataview
TABLE WITHOUT ID
  file.link AS "Name",
  race AS "Race",
  living_status AS "Status",
  era AS "Era"
FROM "" WHERE type = "character" AND affiliation = "[[Firebrand Empire]]" AND contains(role, "ruler")
SORT file.name ASC
```

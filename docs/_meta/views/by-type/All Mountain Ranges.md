---
type: index
status: canon
tags:
- view
view: All Mountain Ranges
---
# All Mountain Ranges

*Mountain ranges and named peaks.*

```dataview
TABLE WITHOUT ID file.link AS "Range", continent AS "Continent", kind AS "Kind"
FROM "" WHERE type = "range" SORT continent ASC, file.name ASC
```

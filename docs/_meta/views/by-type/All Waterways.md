---
type: index
status: canon
tags:
- view
view: All Waterways
---
# All Waterways

*Rivers, lakes, seas, and coasts.*

```dataview
TABLE WITHOUT ID file.link AS "Waterway", continent AS "Continent", kind AS "Kind"
FROM "" WHERE type = "waterway" SORT continent ASC, file.name ASC
```

---
type: index
status: canon
tags:
- view
view: All Chronicles
---
# All Chronicles

*In-world source texts.*

```dataview
TABLE WITHOUT ID file.link AS "Chronicle", attributed_to AS "By", era_of_composition AS "Era", housed_in AS "Housed in"
FROM "" WHERE type = "chronicle" SORT era_of_composition ASC, file.name ASC
```

---
type: index
status: canon
tags:
- view
view: All Resources
---
# All Resources

*Materials, substances, ores, herbs — grouped by category.*

```dataview
TABLE WITHOUT ID
  file.link AS "Resource",
  category AS "Category",
  realm AS "Realm"
FROM ""
WHERE type = "resource"
SORT category ASC, file.name ASC
```

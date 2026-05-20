---
type: index
status: canon
tags:
- view
view: All Technologies & Magic Schools
---
# All Technologies & Magic Schools

*Techniques, inventions, magic disciplines.*

```dataview
TABLE WITHOUT ID
  file.link AS "Technology",
  discipline AS "Discipline",
  era_of_invention AS "Invented",
  invented_by AS "By"
FROM ""
WHERE type = "technology"
SORT discipline ASC, file.name ASC
```

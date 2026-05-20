---
type: index
status: canon
tags:
- view
view: All Languages
---
# All Languages

*Spoken languages, grouped by Ancient/Modern.*

```dataview
TABLE WITHOUT ID
  file.link AS "Language",
  kind AS "Kind",
  era_bloom AS "Bloomed",
  still_spoken AS "Living",
  parent_language AS "Parent"
FROM ""
WHERE type = "language"
SORT kind ASC, file.name ASC
```

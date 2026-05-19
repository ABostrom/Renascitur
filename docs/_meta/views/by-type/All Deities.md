---
type: index
status: canon
tags:
- view
view: All Deities
---
# All Deities

*Gods, grouped by pantheon.*

```dataview
TABLE WITHOUT ID
  file.link AS "Deity",
  pantheon AS "Pantheon",
  domain AS "Domain",
  alignment AS "Alignment",
  era_of_emergence AS "Emerged"
FROM ""
WHERE type = "deity"
SORT pantheon ASC, file.name ASC
```

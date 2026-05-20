---
type: index
status: canon
tags:
- view
view: Saurian Elders
---
# Saurian Elders

*The current Saurian Enclave council.*

```dataview
TABLE WITHOUT ID file.link AS "Elder", living_status AS "Status", role AS "Role"
FROM "" WHERE type = "character" AND affiliation = "[[Saurian Enclave]]"
SORT file.name ASC
```

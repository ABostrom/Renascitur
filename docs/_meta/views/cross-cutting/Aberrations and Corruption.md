---
type: index
status: canon
tags:
- view
view: Aberrations and Corruption
---
# Aberrations and Corruption

*Aberrant and corrupted entities.*

```dataview
TABLE WITHOUT ID file.link AS "Entity", type AS "Type", nature AS "Nature"
FROM "" WHERE nature = "aberrant" OR nature = "corrupted"
SORT type ASC, file.name ASC
```

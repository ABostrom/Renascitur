---
type: index
status: canon
tags:
- view
view: All Prophecies
---
# All Prophecies

*Prophecies, omens, dreams.*

```dataview
TABLE WITHOUT ID file.link AS "Prophecy", kind AS "Kind", attributed_to AS "By", era AS "Era"
FROM "" WHERE type = "prophecy" SORT file.name ASC
```

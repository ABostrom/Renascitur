---
aliases:
- Silverhand
type: house
status: draft
tags: []
realm: '[[Renascita]]'
parent_faction: '[[Firebrand Empire]]'
nature: mortal
importance: notable
alignment: ''
government: oligarchy
size: ''
allies: []
rivals: []
---
## Domain
*Hospitality*
_Responsible for trade, inns, taverns, and diplomacy within the Firebrand Empire._

## Leadership
- **Current Head**: [[Yoren Silverhand]]
- **Race**: [[Gnome]]

## Headquarters
- **City**: [[Lion’s Rest]]
- **Primary Seat**: [[Gatherhold]]

## Political Alignment
- **Primary Faction(s)**: Stability Bloc
- **Allied Houses**: [[House Cannith|Cannith]], [[House Jorasco|Jorasco]], [[House Orien|Orien]]
- **Rival Houses**: None

## Overview

House Silverhand serves a critical role within the Firebrand Empire, overseeing trade, inns, taverns, and diplomacy. Known for their domain of hospitality, they are headquartered in [[Lion’s Rest]] at the [[Gatherhold]].

---

## Contents

<!-- AUTO-INJECTED-DYNAMIC-CONTENTS — delete this comment and everything below to opt out; safe to edit otherwise -->

### Members

```dataview
LIST FROM ""
WHERE type = "character" AND affiliation = this.file.link
SORT file.name ASC
```

### Events involving this house

```dataview
TABLE WITHOUT ID
  file.link AS "Event",
  era AS "Era",
  year_display AS "When"
FROM ""
WHERE type = "event" AND contains(participants, this.file.link)
SORT year ASC
```

### Other notes referencing this house

```dataview
LIST WHERE contains(file.inlinks, this.file.link)
  AND !contains(string(file.path), "_meta/")
SORT file.name ASC
```


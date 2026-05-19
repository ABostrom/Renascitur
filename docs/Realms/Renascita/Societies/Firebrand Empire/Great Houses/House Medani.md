---
aliases:
- Medani
type: house
status: draft
tags: []
realm: '[[Renascita]]'
parent_faction: '[[Firebrand Empire]]'
---
## Domain
*Detection*
_Responsible for internal security, inquisition, and rooting out cultists within the Firebrand Empire._

## Leadership
- **Current Head**: [[Trelib Medani]]
- **Race**: [[Leonin]]

## Headquarters
- **City**: [[Lion’s Rest]]
- **Primary Seat**: [[Tower of Inquisition]]

## Political Alignment
- **Primary Faction(s)**: Hardliners & Watchers
- **Allied Houses**: [[House Deneith|Deneith]], [[House Sivis|Sivis]]
- **Rival Houses**: [[House Tharashk|Tharashk]], [[House Phiarlan|Phiarlan]], [[House Lyrandar|Lyrandar]], [[House Orien|Orien]]

## Overview

House Medani serves a critical role within the Firebrand Empire, overseeing internal security, inquisition, and rooting out cultists. Known for their domain of detection, they are headquartered in [[Lion’s Rest]] at the [[Tower of Inquisition]].

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


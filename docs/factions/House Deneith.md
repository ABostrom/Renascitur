---
aliases:
- Deneith
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
kind: house
---
## Domain
*Sentinel*
_Responsible for internal defense, lawkeeping, and martial order within the Firebrand Empire._

## Leadership
- **Current Head**: [[Breven Deneith]]
- **Race**: [[Leonin]]

## Headquarters
- **City**: [[Lion’s Rest]]
- **Primary Seat**: [[Vigilants Watch]]

## Political Alignment
- **Primary Faction(s)**: Stability Bloc, Hardliners & Watchers
- **Allied Houses**: [[House Jorasco|Jorasco]], [[House Medani|Medani]], [[House Sivis|Sivis]]
- **Rival Houses**: [[House Phiarlan|Phiarlan]]

## Overview

House Deneith serves a critical role within the Firebrand Empire, overseeing internal defense, lawkeeping, and martial order. Known for their domain of sentinel, they are headquartered in [[Lion’s Rest]] at the [[Vigilants Watch]].

---

## Contents

<!-- AUTO-INJECTED-DYNAMIC-CONTENTS — delete this comment and everything below to opt out; safe to edit otherwise -->

### Members

```dataview
LIST FROM ""
WHERE type = "character" AND contains(file.outlinks, this.file.link)
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


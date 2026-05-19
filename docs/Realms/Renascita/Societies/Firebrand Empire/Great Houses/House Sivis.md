---
aliases:
- Sivis
type: house
status: draft
tags:
- realm/renascita
- faction/firebrand-empire
realm: '[[Renascita]]'
parent_faction: '[[Firebrand Empire]]'
---
## Domain
*Scribing*
_Responsible for communication, bureaucracy, and encoded records within the Firebrand Empire._

## Leadership
- **Current Head**: [[Lysse Lyrruman Sivis]]
- **Race**: [[Human]]

## Headquarters
- **City**: [[Lux Oescus]]
- **Primary Seat**: [[The Labyrinth]]

## Political Alignment
- **Primary Faction(s)**: Stability Bloc, Hardliners & Watchers
- **Allied Houses**: [[House Deneith|Deneith]], [[House Medani|Medani]], [[House Orien|Orien]]
- **Rival Houses**: [[House Phiarlan|Phiarlan]]

## Overview

House Sivis serves a critical role within the Firebrand Empire, overseeing communication, bureaucracy, and encoded records. Known for their domain of scribing, they are headquartered in [[Lux Oescus]] at the [[The Labyrinth]].

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


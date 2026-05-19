---
aliases:
- Jorasco
type: house
status: draft
tags: []
realm: [[Renascita]]
parent_faction: [[Firebrand Empire]]
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
*Healing*
_Responsible for medicine, healing, and battlefield care within the Firebrand Empire._

## Leadership
- **Current Head**: [[Ulara Jorasco]]
- **Race**: [[Human]]

## Headquarters
- **City**: [[Lion's Rest]]
- **Primary Seat**: [[Vedkyar Enclave]]

## Political Alignment
- **Primary Faction(s)**: Stability Bloc, Wild Front
- **Allied Houses**: [[House Deneith|Deneith]], [[House Silverhand|Silverhand]], [[House Tharashk|Tharashk]], [[House Vadalis|Vadalis]]
- **Rival Houses**: None

## Overview

House Jorasco serves a critical role within the Firebrand Empire, overseeing medicine, healing, and battlefield care. Known for their domain of healing, they are headquartered in [[Lion's Rest]] at the [[Vedkyar Enclave]].

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


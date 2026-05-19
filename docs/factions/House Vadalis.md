---
aliases:
- Vadalis
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
*Handling*
_Responsible for animal husbandry and mounted logistics within the Firebrand Empire._

## Leadership
- **Current Head**: [[Dalin Vadalis]]
- **Race**: [[Human]]

## Headquarters
- **City**: [[Old Westgate]]
- **Primary Seat**: [[Foalswood]]

## Political Alignment
- **Primary Faction(s)**: Wild Front
- **Allied Houses**: [[House Jorasco|Jorasco]], [[House Orien|Orien]], [[House Tharashk|Tharashk]]
- **Rival Houses**: None

## Overview

House Vadalis serves a critical role within the Firebrand Empire, overseeing animal husbandry and mounted logistics. Known for their domain of handling, they are headquartered in [[Old Westgate]] at the [[Foalswood]].

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


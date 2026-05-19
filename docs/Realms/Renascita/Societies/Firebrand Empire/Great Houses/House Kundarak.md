---
aliases:
- Kundarak
type: house
status: draft
tags: []
realm: '[[Renascita]]'
parent_faction: '[[Firebrand Empire]]'
nature: ''
importance: ''
alignment: ''
government: ''
size: ''
allies: []
rivals: []
---
## Domain
*Warding*
_Responsible for dwarven arcane security and magical protections within the Firebrand Empire._

## Leadership
- **Current Head**: [[Morrikan Kundarak]]
- **Race**: [[Dwarf]]

## Headquarters
- **City**: [[Lux Oescus]]
- **Primary Seat**: [[Korunda Gate]]

## Political Alignment
- **Primary Faction(s)**: Outliers & Hidden Powers
- **Allied Houses**: [[House Cannith|Cannith]], [[House Lyrandar|Lyrandar]], [[House Phiarlan|Phiarlan]]
- **Rival Houses**: None

## Overview

House Kundarak serves a critical role within the Firebrand Empire, overseeing dwarven arcane security and magical protections. Known for their domain of warding, they are headquartered in [[Lux Oescus]] at the [[Korunda Gate]].

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


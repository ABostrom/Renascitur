---
aliases:
- Orien
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
*Passage*
_Responsible for transport, travel, and logistics within the Firebrand Empire._

## Leadership
- **Current Head**: [[Kwanti Orien]]
- **Race**: [[Orc]]

## Headquarters
- **City**: [[Port Ardere]]
- **Primary Seat**: [[Journey’s Home]]

## Political Alignment
- **Primary Faction(s)**: Stability Bloc
- **Allied Houses**: [[House Cannith|Cannith]], [[House Silverhand|Silverhand]], [[House Sivis|Sivis]], [[House Tharashk|Tharashk]], [[House Vadalis|Vadalis]]
- **Rival Houses**: [[House Medani|Medani]]

## Overview

House Orien serves a critical role within the Firebrand Empire, overseeing transport, travel, and logistics. Known for their domain of passage, they are headquartered in [[Port Ardere]] at the [[Journey’s Home]].

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


---
aliases:
- Tharashk
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
*Finding*
_Responsible for hunting threats, scouting, and frontier operations within the Firebrand Empire._

## Leadership
- **Current Head**: [[Broxiz Tharashk]]
- **Race**: [[Leonin]]

## Headquarters
- **City**: [[Lion’s Rest]]
- **Primary Seat**: [[The Den]]

## Political Alignment
- **Primary Faction(s)**: Wild Front
- **Allied Houses**: [[House Cannith|Cannith]], [[House Jorasco|Jorasco]], [[House Orien|Orien]], [[House Vadalis|Vadalis]]
- **Rival Houses**: [[House Medani|Medani]], [[House Phiarlan|Phiarlan]]

## Overview

House Tharashk serves a critical role within the Firebrand Empire, overseeing hunting threats, scouting, and frontier operations. Known for their domain of finding, they are headquartered in [[Lion’s Rest]] at the [[The Den]].

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


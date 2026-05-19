---
aliases:
- Phiarlan
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
*Shadow*
_Responsible for espionage, assassination, and manipulation within the Firebrand Empire._

## Leadership
- **Current Head**: [[Elar Phiarlan]]
- **Race**: [[Leonin]]

## Headquarters
- **City**: [[Raining Bay]]
- **Primary Seat**: [[The Serpentine Citadel]]

## Political Alignment
- **Primary Faction(s)**: Outliers & Hidden Powers
- **Allied Houses**: [[House Kundarak|Kundarak]], [[House Lyrandar|Lyrandar]]
- **Rival Houses**: [[House Deneith|Deneith]], [[House Medani|Medani]], [[House Sivis|Sivis]], [[House Tharashk|Tharashk]]

## Overview

House Phiarlan serves a critical role within the Firebrand Empire, overseeing espionage, assassination, and manipulation. Known for their domain of shadow, they are headquartered in [[Raining Bay]] at the [[The Serpentine Citadel]].

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


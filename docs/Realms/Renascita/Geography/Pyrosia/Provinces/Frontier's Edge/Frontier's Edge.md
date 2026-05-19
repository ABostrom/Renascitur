---
aliases:
- Frontier's Edge
tags:
- province
- region
type: region
status: draft
continent: '[[Pyrosia]]'
realm: '[[Renascita]]'
---
## Overview
A war-torn and reclaimed expanse once ruled by [[Orc|orcs]] and aberrant creatures. Now it stands as the Empire’s final shield wall, fiercely protected by border clans and militant orders.

## Major Cities
- [[Ashgatar]]

## Notes
Seen as a punishment posting by some, a sacred duty by others. Imperators here are often hardened veterans or ascendant generals.

---

## Contents

<!-- AUTO-INJECTED-DYNAMIC-CONTENTS — delete this comment and everything below to opt out; safe to edit otherwise -->

### Settlements

```dataview
TABLE WITHOUT ID
  file.link AS "Settlement",
  size AS "Size",
  controlled_by AS "Held by"
FROM ""
WHERE type = "settlement" AND region = this.file.link
SORT file.name ASC
```

### Landmarks

```dataview
LIST FROM ""
WHERE type = "landmark" AND region = this.file.link
SORT file.name ASC
```

### Characters located here

```dataview
TABLE WITHOUT ID
  file.link AS "Name",
  race AS "Race",
  affiliation AS "Affiliation"
FROM ""
WHERE type = "character" AND location = this.file.link
SORT file.name ASC
```

### Events here

```dataview
TABLE WITHOUT ID
  file.link AS "Event",
  era AS "Era",
  year_display AS "When"
FROM ""
WHERE type = "event" AND location = this.file.link
SORT year ASC
```

### Other notes referencing this region

```dataview
LIST FROM [[]]
WHERE !contains(string(file.path), "_meta/")
SORT file.name ASC
```


---
type: continent
terrain:
- mountains
- glaciers
- evergreen forests
- frozen tundra
inhabited_by:
- '[[Uftine Human]]'
- '[[Icebound|Icebound Dwarves]]'
provinces:
- '[[Aurora Forest]]'
- '[[Calderian Mountains]]'
- '[[Frosthold Glacier]]'
- '[[Misty Shores]]'
cities:
- '[[Uftine]]'
- '[[Runehart]]'
mountains:
- '[[Calderian Peaks]]'
- '[[Thornback Ridge]]'
- '[[Wyrmspine Mountains]]'
rivers:
- '[[Tharic Runoff]]'
- '[[Icevein River]]'
- '[[Shadelake Tributary]]'
status: draft
tags: []
realm: '[[Renascita]]'
---
**Arcturia** is a frigid, rugged continent shaped by ice, stone, and ancestral memory. Its frozen forests and jagged ridgelines conceal the remnants of [[Solaran]] influence and the enduring legacy of the [[Grundthain]].

The [[Icebound|Icebound Dwarves]] guard their ancient vaults beneath the [[Calderian Mountains]], while the hardy [[Uftine Human]] survive amid the frost-choked trees and glacial fjords of the [[Aurora Forest]] and


![[Frosthold Glacier]]
![[Misty Shores]]
![[Aurora Forest]]
![[Calderian Peaks]]

---

## Contents

<!-- AUTO-INJECTED-DYNAMIC-CONTENTS — delete this comment and everything below to opt out; safe to edit otherwise -->

### Regions

```dataview
LIST FROM ""
WHERE type = "region" AND continent = this.file.link
SORT file.name ASC
```

### Settlements

```dataview
TABLE WITHOUT ID
  file.link AS "Settlement",
  size AS "Size",
  controlled_by AS "Held by",
  status AS "Status"
FROM ""
WHERE type = "settlement" AND continent = this.file.link
SORT file.name ASC
```

### Mountain ranges

```dataview
LIST FROM ""
WHERE type = "range" AND continent = this.file.link
SORT file.name ASC
```

### Rivers & waterways

```dataview
LIST FROM ""
WHERE type = "waterway" AND continent = this.file.link
SORT file.name ASC
```

### Landmarks

```dataview
LIST FROM ""
WHERE type = "landmark" AND continent = this.file.link
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

### Other notes referencing this place

```dataview
LIST FROM [[]]
WHERE !contains(string(file.path), "_meta/")
SORT file.name ASC
```


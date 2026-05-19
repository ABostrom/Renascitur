---
type: continent
terrain:
- deserts
- river deltas
- canyons
- coastal cliffs
- mountains
- scrublands
- oases
inhabited_by:
- [[Ferrun]]
- [[Arcanii]]
- [[Thraysian Human]]
- [[Rahalan]]
- [[Velastri]]
provinces:
- [[Al-Ramal]]
- [[Kaldar]]
- [[Khalgar]]
- [[Shazir Coast]]
- [[Thraysia]]
- [[Vasir]]
- [[Zakhmir]]
cities:
- [[Calvereth]]
- [[Eltabarr]]
- [[Solara]]
- [[Thelassia]]
- [[Zahirah]]
mountains:
- [[Kaldar Range]]
- [[Muzari Heights]]
- [[Ravenspine Cliffs]]
- [[Sulamir Escarpment]]
rivers:
- [[Delta Iksandrun]]
- [[River Muzahir]]
- [[River Talinur]]
- [[Razan Tributary]]
- [[Sul Vahir]]
status: draft
tags: []
realm: [[Renascita]]
climate: ''
dominant_culture: ''
population_density: ''
---
**Qethusiyya** is a continent of sweeping contrasts — blistering desert plains, lush river deltas, and coastal cities forged in the aftermath of Solaran collapse. The ancient city of [[Solara]] still casts its long shadow over [[Eltabarr]] and [[Thelassia]], while the fractured empires of [[Thraysia]] and [[Vasir]] vie for dominance across windswept trade routes.

The [[Kaldar Range]] and [[Ravenspine Cliffs]] shape the continent’s arid interior, where [[Ferrun]] outposts and [[Arcanii]] sanctuaries cling to shaded ridges. Rivers such as the [[River Muzahir]] and [[Sul Vahir]] breathe life into desert-bound cities and ancient [[Solaran]] ruins alike, sustaining the enduring presence of the [[Velastri]] and the far-wandering [[Rahalan]] clans.

---

## Contents

<!-- AUTO-INJECTED-DYNAMIC-CONTENTS — delete this comment and everything below to opt out; safe to edit otherwise -->

### Regions

```dataview
LIST FROM ""
WHERE type = "region" AND contains(file.outlinks, this.file.link)
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
WHERE type = "settlement" AND contains(file.outlinks, this.file.link)
SORT file.name ASC
```

### Mountain ranges

```dataview
LIST FROM ""
WHERE type = "range" AND contains(file.outlinks, this.file.link)
SORT file.name ASC
```

### Rivers & waterways

```dataview
LIST FROM ""
WHERE type = "waterway" AND contains(file.outlinks, this.file.link)
SORT file.name ASC
```

### Landmarks

```dataview
LIST FROM ""
WHERE type = "landmark" AND contains(file.outlinks, this.file.link)
SORT file.name ASC
```

### Characters located here

```dataview
TABLE WITHOUT ID
  file.link AS "Name",
  race AS "Race",
  affiliation AS "Affiliation"
FROM ""
WHERE type = "character" AND contains(file.outlinks, this.file.link)
SORT file.name ASC
```

### Events here

```dataview
TABLE WITHOUT ID
  file.link AS "Event",
  era AS "Era",
  year_display AS "When"
FROM ""
WHERE type = "event" AND contains(file.outlinks, this.file.link)
SORT year ASC
```

### Other notes referencing this place

```dataview
LIST WHERE contains(file.inlinks, this.file.link)
  AND !contains(string(file.path), "_meta/")
SORT file.name ASC
```


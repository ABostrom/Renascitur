---
type: region
status: draft
continent: '[[Pyrosia]]'
tags: []
realm: '[[Renascita]]'
region: '[[Ashen Plains]]'
climate: volcanic
terrain:
- river
dominant_culture: ''
population_density: ''
settlements: []
---
Elturel was once a prospering city along the river Chionthar. Before the [[Psychic Schism]] it was a centre of agriculture and commerce in the region. The city was situated atop a bluff with a cliff dominating the river. It was a good defensive position and a good crossing point. 

The city was decimated after the [[Psychic Schism|schism]], as the forces of [[Ishna]] used the city to stage an all out assault into [[Infernum]].

[https://5e.tools/bestiary/hythonia-mot.html](https://5e.tools/bestiary/hythonia-mot.html) guards the portal.

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
WHERE type = "settlement" AND contains(file.outlinks, this.file.link)
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

### Other notes referencing this region

```dataview
LIST WHERE contains(file.inlinks, this.file.link)
  AND !contains(string(file.path), "_meta/")
SORT file.name ASC
```


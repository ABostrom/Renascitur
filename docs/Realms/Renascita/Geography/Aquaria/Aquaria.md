---
type: continent
status: stub
tags:
- realm/renascita
- continent/aquaria
realm: '[[Renascita]]'
---
![[Coral Reef Bay]]

![[Crystal Caverns]]

![[Leviathan's Trench]]

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
LIST WHERE contains(file.inlinks, this.file.link)
  AND !contains(string(file.path), "_meta/")
SORT file.name ASC
```


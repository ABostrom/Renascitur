---
type: faction
status: draft
tags: []
realm: '[[Renascita]]'
parent_faction: '[[Devouts of Muradin]]'
nature: mortal
importance: notable
alignment: ''
society_form: ''
government: ''
economy: ''
seat: ''
size: ''
allies: []
rivals: []
magic: []
---
The order of [[Magnus]] was formerly recognised following the death of [[Magnus]] Hammerfell in 100 AS. During his life [[Magnus]] has founded his order of Clerics to spread the teachings of the Old God [[Muradin]]. Knowing that [[Muradin]] had saved his life, he felt it his holy duty to spread his teachings to all [[Dwarf|Dwarves]] of the new world.

---

## Contents

<!-- AUTO-INJECTED-DYNAMIC-CONTENTS — delete this comment and everything below to opt out; safe to edit otherwise -->

### Sub-factions

```dataview
LIST FROM ""
WHERE type = "faction" AND parent_faction = this.file.link
SORT file.name ASC
```

### Members

```dataview
TABLE WITHOUT ID
  file.link AS "Name",
  race AS "Race",
  location AS "Location"
FROM ""
WHERE type = "character" AND affiliation = this.file.link
SORT file.name ASC
```

### Organisations within

```dataview
LIST FROM ""
WHERE type = "organisation" AND parent_faction = this.file.link
SORT file.name ASC
```

### Events involving this faction

```dataview
TABLE WITHOUT ID
  file.link AS "Event",
  era AS "Era",
  year_display AS "When"
FROM ""
WHERE type = "event" AND contains(participants, this.file.link)
SORT year ASC
```

### Other notes referencing this faction

```dataview
LIST WHERE contains(file.inlinks, this.file.link)
  AND !contains(string(file.path), "_meta/")
SORT file.name ASC
```


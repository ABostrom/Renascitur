---
type: faction
status: stub
realm: "[[Renascita]]"
tags: []
nature: mortal
importance: notable
alignment: lawful-evil
society_form: martial
government: oligarchy
economy: industrial
seat: ''
size: regional
allies: []
rivals: []
magic: []
leadership:
- "[[Kael Durnith]]"
aliases:
- Blackiron Collective
- Blackiron
era_founded: "[[Age of Stagnation]]"
---
---

## Contents

---

## Contents

<!-- AUTO-INJECTED-DYNAMIC-CONTENTS — delete this comment and everything below to opt out; safe to edit otherwise -->

### Sub-factions

```dataview
LIST FROM ""
WHERE type = "faction" AND contains(file.outlinks, this.file.link)
SORT file.name ASC
```

### Noble houses within

```dataview
TABLE WITHOUT ID
  file.link AS "House",
  current_head AS "Head",
  seat AS "Seat",
  sigil AS "Sigil"
FROM ""
WHERE type = "house" AND contains(file.outlinks, this.file.link)
SORT file.name ASC
```

### Members

```dataview
TABLE WITHOUT ID
  file.link AS "Name",
  race AS "Race",
  location AS "Location"
FROM ""
WHERE type = "character" AND contains(file.outlinks, this.file.link)
SORT file.name ASC
```

### Organisations within

```dataview
LIST FROM ""
WHERE type = "organisation" AND contains(file.outlinks, this.file.link)
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


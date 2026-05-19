---
aliases:
- The Souls of the Devourer
type: faction
status: draft
tags: []
realm: [[Renascita]]
kind: cult
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
leadership: []
---
Symbol: שקש๔

The souls of the devourer are a cult dedicated to [[Ishna]] and ensuring that the work started during the [[Psychic Schism]] is completed. The cult is secretly fronted by a working class revolution to upend the power and order of the [[Firebrand Empire]]. Disgruntled labourers and members of the [[VPVD]] are recruited to aid in the destabilisation of the empire, by strike action, sabotage, espionage and then once indoctrination has begun acts of violence.


[[Syuul, The Devourer]]

---

## Contents

<!-- AUTO-INJECTED-DYNAMIC-CONTENTS — delete this comment and everything below to opt out; safe to edit otherwise -->

### Sub-factions

```dataview
LIST FROM ""
WHERE type = "faction" AND contains(file.outlinks, this.file.link)
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


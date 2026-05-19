---
aliases:
- Lion’s Rest
tags:
- city
- location
type: settlement
status: draft
continent: '[[Pyrosia]]'
realm: '[[Renascita]]'
importance: notable
population: ''
climate: volcanic
terrain: plains
defenses: fortified
predominant_economy: military
---
## Province
- [[Ashen Plains]]

## Overseer
- [[Kheros Medani]]

## Description
The proud capital of the Firebrand Empire, seat of the Emperor and the great council. A bastion of order, military discipline, and political intrigue. Its spires overlook wide imperial avenues and the central forum of judgment. Its coliseums host military parades and public trials, while golden statues of past emperors watch from the hilltops.

## Notable Houses
- [[House Medani]]
- [[House Tharashk]]
- [[House Jorasco]]
- [[House Silverhand]]
- [[House Deneith]]

---

## Contents

<!-- AUTO-INJECTED-DYNAMIC-CONTENTS — delete this comment and everything below to opt out; safe to edit otherwise -->

### Districts and landmarks inside

```dataview
LIST FROM ""
WHERE type = "landmark" AND inside = this.file.link
SORT file.name ASC
```

### Characters here

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

### Other notes referencing this settlement

```dataview
LIST WHERE contains(file.inlinks, this.file.link)
  AND !contains(string(file.path), "_meta/")
SORT file.name ASC
```


---
aliases:
- Port Ardere
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
terrain: ''
defenses: ''
predominant_economy: ''
---
## Province
- [[Ashen Plains]]

## Overseer
- [[Brakka Orien]]

## Description
A vital logistics hub where land meets sea. Port Ardere manages the flow of goods from the Flame Coast into the Ashen heartlands, and serves as the gateway for imperial expeditions abroad. Every warehouse, dock, and granary hums with coordinated precision — a testament to the influence of House Orien.

## Notable Houses
- [[House Orien]]

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


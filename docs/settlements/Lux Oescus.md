---
aliases:
- Lux Oescus
tags:
- city
- location
type: settlement
status: draft
continent: "[[Pyrosia]]"
realm: "[[Renascita]]"
importance: notable
population: ''
climate: volcanic
terrain: plains
defenses: fortified
predominant_economy: ''
size: ''
controlled_by: "[[Firebrand Empire]]"
populated_by: []
era_founded: ''
leadership:
- "[[Rymelle Sivis]]"
region: "[[Ashen Plains]]"
---
## Province
- [[Ashen Plains]]

## Overseer
- [[Rymelle Sivis]]

## Description
The Empire’s arcane and administrative stronghold. Home to the Labyrinth and a thousand bureaucratic towers. Beneath its golden domes lies a network of spell wards and administrative codes older than the Empire itself. The city's air thrums with the hum of enchantment, and at dusk, the spell-torches lining the streets ignite in perfect unison.

## Notable Houses
- [[House Sivis]]
- [[House Kundarak]]

---

## Contents

<!-- AUTO-INJECTED-DYNAMIC-CONTENTS — delete this comment and everything below to opt out; safe to edit otherwise -->

### Districts and landmarks inside

```dataview
LIST FROM ""
WHERE type = "landmark" AND contains(file.outlinks, this.file.link)
SORT file.name ASC
```

### Characters here

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

### Other notes referencing this settlement

```dataview
LIST WHERE contains(file.inlinks, this.file.link)
  AND !contains(string(file.path), "_meta/")
SORT file.name ASC
```


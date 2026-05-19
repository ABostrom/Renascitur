---
aliases:
- Old Westgate
tags:
- city
- location
type: settlement
status: draft
continent: '[[Pyrosia]]'
realm: '[[Renascita]]'
importance: major
population: ''
climate: volcanic
terrain: mountains
defenses: ''
predominant_economy: ''
size: ''
controlled_by: ''
populated_by: []
era_founded: ''
---
## Province
- [[Ember Peaks]]

## Overseer
- [[Tressa Vadalis]]

## Description
An ancient dwarven trading city restructured by humans. It retains its rugged charm and intricate stonework, now humming with rail lines and beast-handling yards. Animal pens line the terraced hills, and its railway junction is often full of chirping beasts and stomping supply trains.

## Notable Houses
- [[House Vadalis]]

---

## Contents

<!-- AUTO-INJECTED-DYNAMIC-CONTENTS — delete this comment and everything below to opt out; safe to edit otherwise -->

### Districts and landmarks inside

```dataview
LIST FROM ""
WHERE type = "landmark" AND string(inside) = string(this.file.link)
SORT file.name ASC
```

### Characters here

```dataview
TABLE WITHOUT ID
  file.link AS "Name",
  race AS "Race",
  affiliation AS "Affiliation"
FROM ""
WHERE type = "character" AND string(location) = string(this.file.link)
SORT file.name ASC
```

### Events here

```dataview
TABLE WITHOUT ID
  file.link AS "Event",
  era AS "Era",
  year_display AS "When"
FROM ""
WHERE type = "event" AND string(location) = string(this.file.link)
SORT year ASC
```

### Other notes referencing this settlement

```dataview
LIST WHERE contains(file.inlinks, this.file.link)
  AND !contains(string(file.path), "_meta/")
SORT file.name ASC
```


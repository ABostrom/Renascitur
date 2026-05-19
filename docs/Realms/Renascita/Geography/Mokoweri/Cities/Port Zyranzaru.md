---
type: settlement
status: draft
continent: '[[Mokoweri]]'
tags: []
---
Port Zyranzaru is the largest and most important city in [[Mokoweri]]. It is located on the coast, with easy access to the sea and other nearby islands. The city is a bustling hub of activity, with traders, merchants, and sailors from all over the world coming to do business.

The architecture of Port Zyranzaru is a unique blend of ancient ruins and organic growth. Some buildings are made from the sturdy stone walls of ancient ruins, while others are grown from giant mangrove trees. The city is a riot of colour, with murals and carvings decorating every surface.

The people of Port Zyranzaru are a diverse and cosmopolitan group, with traders and travellers from all over the world passing through. However, they retain a distinct [[Mokoweri]] flavour, with a focus on community and cooperation.

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
LIST FROM [[]]
WHERE !contains(string(file.path), "_meta/")
SORT file.name ASC
```


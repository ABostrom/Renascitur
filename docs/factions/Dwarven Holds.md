---
type: faction
status: stub
tags: []
realm: "[[Renascita]]"
nature: mortal
importance: major
alignment: lawful-neutral
society_form: feudal
government: tribal-council
economy: mining
seat: ''
size: continental
allies:
- "[[Firebrand Empire]]"
rivals: []
magic:
- "[[Rune Magic]]"
- "[[Forge Magic]]"
leadership: []
aliases:
- Dwarven Holds
- The Dwarven Holds
era_founded: "[[Age of Forging]]"
---
# Dwarven Holds

*The four united holds of the Grundthain dwarves — Tidebound, Icebound, Stormbound, and Flamebound — bound by ancestral alliance and the great subterranean railway that links their cities.*

---
## Connections

<!-- AUTO-CONNECTIONS — safe to edit; will not be re-injected -->

- **Sub-factions**: [[The Tidebound of Draumhavn]], [[The Icebound of Uftine]], [[The Stormbound of Thundrakar]], [[The Flamebound of Magnus' Rest]]
- **Race**: [[Dwarf]] (a lineage of the [[Grundthain]])
- **Allied with**: [[Firebrand Empire]] via the Deepline railway
- **Patron deity**: [[Muradin]] (in his original [[Grundthain]] form)
- **Concept**: [[Hexweave]] — the cosmic structure their forges helped bind
- **Magic disciplines**: [[Rune Magic]], [[Forge Magic]]

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


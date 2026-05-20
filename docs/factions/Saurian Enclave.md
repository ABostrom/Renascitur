---
type: faction
status: stub
tags: []
realm: [[Renascita]]
nature: bioengineered
importance: major
alignment: neutral-good
society_form: theocratic
government: theocracy
economy: agrarian
seat: [[Aeloria]]
size: regional
allies: []
rivals: []
magic:
- [[Primal]]
- [[Divine]]
leadership: []
aliases:
- Saurian Enclave
- The Saurian Enclave
---
# Saurian Enclave

*The Saurian society of Mokoweri, guided by the Elder council and the ancient covenant with the Solaran creators. Keepers of the Archive of the Ancients and stewards of the Aeloria tree-city.*

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


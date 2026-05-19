---
type: faction
status: draft
realm: '[[Renascita]]'
tags: []
nature: mortal
importance: notable
alignment: neutral
society_form: magocratic
government: magocratic-council
economy: magical
seat: '[[Eltabarr]]'
size: regional
allies: []
rivals: []
magic:
- '[[Arcane]]'
- '[[Arcanometry]]'
- '[[Glyph Magic]]'
---
### The Majlis of Arcane Sovereignty

At the helm of Eltabarr's governance are three grand sorcerers, each hailing from the city's dominant races: the Elves, Tieflings, and Humans. [[Aelar Amakiir]], the Verdant Sage, brings the wisdom of the Elves and their deep connection to nature. [[Zariel Mephista]]r, known as the Infernal Diplomat, embodies the resilience and ambition of the Tieflings. [[Farid al-Hakim]], the Arcane Architect, represents the ingenuity and adaptability of Humans. Together, they guide Eltabarr through the currents of time, ensuring its prosperity and safeguarding its mystical secrets.

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


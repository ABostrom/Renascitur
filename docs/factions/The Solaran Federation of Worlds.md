---
type: faction
status: stub
tags: []
realm: '[[Renascita]]'
nature: celestial
importance: legendary
alignment: lawful-good
society_form: imperial
government: magocratic-council
economy: magical
seat: '[[Solara]]'
size: cosmic
era_founded: '[[Age of the Endless Sun]]'
era_dissolved: '[[Age of the Endless Sun]]'
allies: []
rivals: []
magic:
- '[[Arcanometry]]'
- '[[Astral Weaving]]'
leadership: []
---
# The Solaran Federation of Worlds

*The lost interstellar civilization of the Solarans, whose Endless Sun lit the heavens until its fall. Their works, like the Saurians and the World Trees, outlived them.*

---

## Contents

<!-- AUTO-INJECTED-DYNAMIC-CONTENTS — delete this comment and everything below to opt out; safe to edit otherwise -->

### Sub-factions

```dataview
LIST FROM ""
WHERE type = "faction" AND string(parent_faction) = string(this.file.link)
SORT file.name ASC
```

### Members

```dataview
TABLE WITHOUT ID
  file.link AS "Name",
  race AS "Race",
  location AS "Location"
FROM ""
WHERE type = "character" AND string(affiliation) = string(this.file.link)
SORT file.name ASC
```

### Organisations within

```dataview
LIST FROM ""
WHERE type = "organisation" AND string(parent_faction) = string(this.file.link)
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


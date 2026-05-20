---
type: faction
status: draft
realm: [[Renascita]]
tags: []
nature: mortal
importance: notable
alignment: neutral-good
society_form: tribal
government: tribal-council
economy: agrarian
seat: ''
size: regional
allies:
- [[Saurian Enclave]]
rivals: []
magic:
- [[Primal]]
leadership: []
aliases:
- Mokoweri People
- Mokoweri
era_founded: [[Age of the Endless Sun]]
---
The [[docs/Races/Solaran/Mokoweri|Mokoweri]] people are an ancient civilization with a rich and complex history. According to legend, their ancestors were among the first to inhabit the islands that now make up their homeland. They lived in harmony with the native [[Saurian]], developing a symbiotic relationship that would endure for centuries.

As time went on, the [[docs/Races/Solaran/Mokoweri|Mokoweri]] people grew and flourished, creating their own unique culture and society. They developed a deep connection with the natural world, learning to harness the power of the jungle to meet their needs. They also became skilled navigators, building seaworthy vessels that allowed them to explore the surrounding seas and trade with other civilizations.

Today, the [[Mokoweri]] people are known for their strong connection to the natural world and their emphasis on community and cooperation. They live in tight-knit villages and towns, with each person contributing to the collective wellbeing of the group.

The [[Mokoweri]] are skilled artisans and craftspeople, creating beautiful works of art and practical tools from the materials found in the jungle. They are also expert farmers and fishermen, providing ample food for their people and for trade with outsiders.

In terms of religion, the [[Mokoweri]] worship a pantheon of nature deities, including gods and goddesses associated with the sun, the sea, the sky, and the earth. They believe that all living things are connected and that the health of the natural world is essential to their own survival.

![[docs/Races/Solaran/Mokoweri|Mokoweri]]

![[Saurian]]

---
## Connections

<!-- AUTO-CONNECTIONS — safe to edit; will not be re-injected -->

- **Race**: [[Mokoweri Human]]
- **Continent**: [[Mokoweri]]
- **Allied with**: [[Saurian Enclave]] via ancestral covenant
- **Notable group**: [[Tyrannosaurs of Mokoweri]]
- **Magic**: [[Primal]]
- **Society**: tribal, spiritual, agrarian

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


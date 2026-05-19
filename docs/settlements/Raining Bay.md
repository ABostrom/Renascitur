---
aliases:
- The Raining Bay
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
terrain: coast
defenses: ''
predominant_economy: ''
size: ''
controlled_by: ''
populated_by: []
era_founded: ''
---
![[Pasted image 20250420165543.png]]
## Province
- [[Flame Coast]]

## Overseer
- [[Caelus Lyrandar]]

## Description
A storm-wracked harbor where the skies churn with arcane force. Lyrandar's skyships dock here between voyages to the elemental edge. Fog, salt, and secrets drift with the tide. From the misty docks, arcane stormglass towers rise, home to the elite navigators and stormcallers of House Lyrandar.

## Notable Houses
- [[House Phiarlan]]
- [[House Lyrandar]]

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


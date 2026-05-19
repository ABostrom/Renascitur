---
type: faction
status: draft
realm: '[[Renascita]]'
tags: []
nature: mortal
importance: notable
alignment: lawful-evil
society_form: imperial
government: monarchy
economy: ''
seat: ''
size: regional
allies: []
rivals: []
magic:
- '[[Glyph Magic]]'
leadership: []
---
**Type**:: Sovereign Protectorate  
**Capital**:: [[Calvereth]]  
**Ruler**:: [[Vaelira Lyrandar|Vaelira]], *The Lady of Velkhar*  
**Location**:: Southeast of the [[Kaldar Range]], [[Qethusiyya]]  
**Founded**:: ~250 years ago, in the aftermath of the [[Psychic Schism|Schism]]

---

## Overview

The Velkhar Dominion is a mist-veiled nation ruled by a caste of oath-bound vampires, offering stability, protection, and order in exchange for loyalty and blood. Though feudal and rigid, the Dominion is not cruel — its hierarchy is clear, its laws are honored, and its undead nobility are guardians as much as rulers.

At its heart lies [[Calvereth]], a quiet and disciplined city built in a valley. The living dwell alongside the dead in a mutual pact of survival, shielded from [[Entropy|aberrant corruption]] by arcane mists and ancient [[Glyph Magic]].

The Dominion is ruled by [[Vaelira Lyrandar|Vaelira]], *The Lady of Velkhar* — a former scion of [[House Lyrandar]] who cast aside her name to become something other: immortal, veiled, and just. She is spoken of with reverence and caution, a figure of myth and law whose presence anchors the nation’s long vigil.

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


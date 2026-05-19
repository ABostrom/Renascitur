---
type: settlement
status: draft
continent: '[[Qethusiyya]]'
tags: []
realm: '[[Renascita]]'
importance: notable
population: ''
climate: arid
terrain: underground
defenses: ''
predominant_economy: mercantile
size: ''
controlled_by: ''
populated_by: []
era_founded: ''
---
Zahirah is the thriving heart of commerce in the [[Vasir]], nestled among fertile deltas and intersecting glyphroads. Known for its sprawling bazaar, floating canal markets, and colorful canvas awnings enchanted with protective runes, it is a melting pot of culture, trade, and low-tier enchantment.

The city is governed loosely by a council of merchant guilds, with magical regulation enforced only lightly. While not openly defiant, Zahirah is viewed with suspicion by the Magocracy in [[Eltabarr]] for its tolerance of glyph innovation and rumour of Brimmed Cap artifacts passing through its underground markets.

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


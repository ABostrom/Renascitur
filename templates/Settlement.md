---
type: settlement
status: draft
tags: []
size: village
continent: ''
region: ''
era_founded: ''
controlled_by: ''
populated_by: []
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
importance: ''
population: ''
climate: ''
terrain: ''
defenses: ''
predominant_economy: ''
---
# {{title}}

## Overview

## Inhabitants

## Notable locations

## History

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


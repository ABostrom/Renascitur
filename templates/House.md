---
type: house
status: draft
tags: []
realm: ''
era_founded: ''
era_extinct: ''
founder: ''
seat: ''
current_head: ''
members: []
sigil: ''
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
nature: ''
importance: ''
alignment: ''
government: ''
size: ''
allies: []
rivals: []
---
# {{title}}

## Lineage

## Significant events

## Current status

---

## Contents

<!-- AUTO-INJECTED-DYNAMIC-CONTENTS — delete this comment and everything below to opt out; safe to edit otherwise -->

### Members

```dataview
LIST FROM ""
WHERE type = "character" AND string(affiliation) = string(this.file.link)
SORT file.name ASC
```

### Events involving this house

```dataview
TABLE WITHOUT ID
  file.link AS "Event",
  era AS "Era",
  year_display AS "When"
FROM ""
WHERE type = "event" AND contains(participants, this.file.link)
SORT year ASC
```

### Other notes referencing this house

```dataview
LIST WHERE contains(file.inlinks, this.file.link)
  AND !contains(string(file.path), "_meta/")
SORT file.name ASC
```


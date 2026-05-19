---
type: era
status: draft
tags: []
code: ''
aliases: []
preceded_by: ''
followed_by: ''
defining_events: []
defining_chronicles: []
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
importance: ''
---
# {{title}}

## Overview

## Themes

## Key events

## Key chronicles

---

## Contents

<!-- AUTO-INJECTED-DYNAMIC-CONTENTS — delete this comment and everything below to opt out; safe to edit otherwise -->

### Events in this era

```dataview
TABLE WITHOUT ID
  file.link AS "Event",
  year_display AS "When",
  location AS "Where",
  status AS "Status"
FROM ""
WHERE type = "event" AND string(era) = string(this.file.link)
SORT year ASC
```

### Chronicles

```dataview
LIST FROM ""
WHERE type = "chronicle" AND string(era_of_composition) = string(this.file.link)
SORT file.name ASC
```

### Myths from this era

```dataview
LIST FROM ""
WHERE type = "myth" AND string(era) = string(this.file.link)
SORT file.name ASC
```

### Characters who lived in this era

```dataview
LIST FROM ""
WHERE type = "character" AND string(era) = string(this.file.link)
SORT file.name ASC
```

### Settlements founded in this era

```dataview
LIST FROM ""
WHERE type = "settlement" AND string(era_founded) = string(this.file.link)
SORT file.name ASC
```

### Other notes referencing this era

```dataview
LIST WHERE contains(file.inlinks, this.file.link)
  AND !contains(string(file.path), "_meta/")
SORT file.name ASC
```


---
type: culture
status: draft
tags: []
races: []
homeland: ''
era_bloom: ''
era_decline: ''
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
nature: ''
importance: ''
society_form: ''
government: ''
magic: []
---
# {{title}}

## Overview

## Values and beliefs

## Practices

## History

---

## Contents

<!-- AUTO-INJECTED-DYNAMIC-CONTENTS — delete this comment and everything below to opt out; safe to edit otherwise -->

### Characters of this culture

```dataview
TABLE WITHOUT ID
  file.link AS "Name",
  race AS "Race",
  affiliation AS "Affiliation"
FROM ""
WHERE type = "character" AND string(culture) = string(this.file.link)
SORT file.name ASC
```

### Traditions

```dataview
LIST FROM ""
WHERE type = "tradition" AND string(culture) = string(this.file.link)
SORT file.name ASC
```

### Languages spoken

```dataview
LIST FROM ""
WHERE type = "language" AND contains(spoken_by, this.file.link)
SORT file.name ASC
```

### Other notes referencing this culture

```dataview
LIST WHERE contains(file.inlinks, this.file.link)
  AND !contains(string(file.path), "_meta/")
SORT file.name ASC
```


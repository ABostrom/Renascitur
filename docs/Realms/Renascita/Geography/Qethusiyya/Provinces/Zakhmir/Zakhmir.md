---
type: region
status: draft
continent: '[[Qethusiyya]]'
tags: []
---
# Zakhmir
**Original Root:** Zakhm-e Jān

Zakhmir is a fractured and crater-ridden land to the south, scarred by arcane collapse. It is said [[Weave|the Weave]] itself split open here during the Fall, leaving behind [[soul]]-deep wounds. Glyphs twist in the air, never quite stable.

---

## Contents

<!-- AUTO-INJECTED-DYNAMIC-CONTENTS — delete this comment and everything below to opt out; safe to edit otherwise -->

### Settlements

```dataview
TABLE WITHOUT ID
  file.link AS "Settlement",
  size AS "Size",
  controlled_by AS "Held by"
FROM ""
WHERE type = "settlement" AND region = this.file.link
SORT file.name ASC
```

### Landmarks

```dataview
LIST FROM ""
WHERE type = "landmark" AND region = this.file.link
SORT file.name ASC
```

### Characters located here

```dataview
TABLE WITHOUT ID
  file.link AS "Name",
  race AS "Race",
  affiliation AS "Affiliation"
FROM ""
WHERE type = "character" AND location = this.file.link
SORT file.name ASC
```

### Events here

```dataview
TABLE WITHOUT ID
  file.link AS "Event",
  era AS "Era",
  year_display AS "When"
FROM ""
WHERE type = "event" AND location = this.file.link
SORT year ASC
```

### Other notes referencing this region

```dataview
LIST FROM [[]]
WHERE !contains(string(file.path), "_meta/")
SORT file.name ASC
```


---
type: index
status: canon
tags:
- meta
---
# Campaign Reference

Quick-lookup dashboard for live sessions.

## Recently edited

```dataview
LIST FROM "" WHERE file.mtime SORT file.mtime DESC LIMIT 15
```

## Major factions

```dataview
LIST FROM "" WHERE type = "faction" SORT file.name ASC
```

## All canonical characters

```dataview
TABLE WITHOUT ID
  file.link AS "Name",
  race AS "Race",
  affiliation AS "Faction"
FROM ""
WHERE type = "character" AND status = "canon"
SORT affiliation ASC, file.name ASC
```

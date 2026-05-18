---
type: essay
status: canon
topic: vault conventions
---

# Renascitur Vault Conventions

*Living reference for the typed-vault schema. Last updated 2026-05-18.*

## Note types (23)

Every reference note declares its `type:` in frontmatter. Long-form prose without a categorical home uses `type: essay`. The full vocabulary, grouped:

**Geography (6):** `continent`, `region`, `settlement`, `landmark`, `waterway`, `range`

**People & groups (6):** `character`, `race`, `culture`, `faction`, `house`, `organisation`

**Time & history (4):** `era`, `event`, `myth`, `chronicle`

**Things (4):** `artifact`, `item`, `resource`, `technology`

**Concepts (4):** `deity`, `cosmic-force`, `tradition`, `language`

**Meta (2):** `essay`, `prophecy`

## Universal frontmatter

Every typed note:
- `type:` — one of the 23 above
- `status:` — `stub` | `draft` | `canon` | `archived`
- `tags:` — free-form list
- `created:` — auto-set by Templater
- `updated:` — auto-set by Templater

## The four Ages

| Age              | Code | Folder                              | Display |
|------------------|------|-------------------------------------|---------|
| First Age        | `ES` | `History/Age of the Endless Sun/`   | `ES 412` |
| Second Age       | `AF` | `History/Age of Forging/`           | `AF 412` |
| Third Age        | `AS` | `History/Age of Stagnation/`        | `AS 412` |
| Fourth Age       | `AN` | `History/Age of Night/`             | `AN 412` |

Event and chronicle filenames use a 4-digit zero-padded year prefix: `AF0412 Hexweave Binding.md`. Year `0000` is reserved for "undated within the era." Aliases preserve old names so existing `[[wikilinks]]` still resolve.

## Authoring rules

- `status: stub` files have *only* frontmatter and the title. They are valid; they live in `_meta/Stub Backlog.md`.
- Long-form prose (`type: essay`, `type: chronicle`) has no rigid template; only the frontmatter is fixed.
- Frontmatter wikilinks are always quoted: `era: "[[Age of Forging]]"`.
- Cross-references (`participants:`, `chronicled-in:`, etc.) are link lists.

See also: `notes/refactor-design.md` for the design rationale; `notes/working-model.md` for what the vault looked like before the refactor.

---
type: region
status: draft
continent: "[[Qethusiyya]]"
tags: []
realm: "[[Renascita]]"
region: "[[Al-Ramal]]"
climate: arid
terrain:
- forest
dominant_culture: ''
population_density: ''
settlements: []
---
_Appearance:_ Nestled amid the arid expanse of Renascitur, the Eversoul Grove presents a striking contrast to the surrounding desolation. It is an oasis of vibrant life and tranquility, offering a haven of resplendent greenery amidst the harsh wilderness. Tall, ancient trees with verdant foliage form a protective canopy over the grove, their leaves shimmering with an ethereal radiance that bathes the entire area in a soft, gentle glow. This luminescence, akin to dappled sunlight, emanates from the heart of the grove.

_Entrance to Solara:_ The Eversoul Grove is one of the last known places in Renascitur that holds the elusive key to accessing the storied city of Solara, a place of great significance to the [[Solaran]] civilization. It serves as a physical gateway to the ancient city, allowing those of [[Solaran]] ancestry to pass through to the hallowed grounds of Solara.

_Ancestral Connection:_ As guardians of their heritage, the ancient [[Solaran|Solarans]] imbued this entrance with the power to recognize and resonate with their descendants. To unlock the gateway, one must possess [[Solaran]] bloodline or lineage. The grove itself is attuned to the unique spiritual essence of [[Solaran]] ancestry, making it unresponsive to those whose blood lacks this connection.

_The Grove Warden:_ Standing as both sentinel and arbiter, the Grove Warden is a towering, sentient living construct intricately entwined with the flora of the grove. Its body is composed of interwoven vines, branches, and mystical runes that grant it both sentience and purpose. The Grove Warden's gaze, eternally watchful, gazes upon those who approach the gateway.

_Testing Purity:_ For those not of [[Solaran]] descent, the Grove Warden serves as a guardian of [[Solaran]] heritage and history. It stands as the final arbiter, tasked with evaluating the purity of the petitioner's intentions and worthiness to enter Solara. The Warden subjects outsiders to a spiritual test, delving into their hearts and motives to determine whether they seek Solara's secrets for good or ill.

The Eversoul Grove, with its radiant luminescence and the solemn presence of the Grove Warden, remains a place of profound significance, where the past meets the

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
WHERE type = "settlement" AND contains(file.outlinks, this.file.link)
SORT file.name ASC
```

### Landmarks

```dataview
LIST FROM ""
WHERE type = "landmark" AND contains(file.outlinks, this.file.link)
SORT file.name ASC
```

### Characters located here

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

### Other notes referencing this region

```dataview
LIST WHERE contains(file.inlinks, this.file.link)
  AND !contains(string(file.path), "_meta/")
SORT file.name ASC
```


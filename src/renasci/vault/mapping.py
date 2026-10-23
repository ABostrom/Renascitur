"""What each note becomes (S2 spec §3.3): a pin source, a place, reference, a claim seed, or nothing.

Status gates come first: a `status: draft` note is `draft` (loaded, reported, makes nothing); a
`canon: proposed` note is `proposed` until Aaron promotes it. Everything else is canon, and its type
decides its role.
"""

from __future__ import annotations

ROLES = {
    **dict.fromkeys(("character", "house", "organisation", "event", "era"), "pin_source"),
    **dict.fromkeys(("settlement", "region", "continent", "landmark", "waterway", "range"), "place"),
    **dict.fromkeys(("race", "culture", "language", "deity", "faction", "artifact", "item", "resource", "technology",
                     "cosmic-force", "tradition"), "reference"),
    **dict.fromkeys(("chronicle", "myth"), "claim_seed"),  # a prophecy is a myth with kind: prophecy
    **dict.fromkeys(("essay", "index"), "ignored"),
}


def role(note) -> str:
    """pin_source | place | reference | claim_seed | ignored | draft | proposed."""
    if note.status in ("draft", "proposed"):
        return note.status
    return ROLES[note.type]

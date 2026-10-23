"""`vault.toml`: what the bridge needs to know about one vault (S2 spec §3.2), kept as data.

```toml
ignore = ["Images/**"]            # paths (globs) the walk skips
[type_aliases]
city = "settlement"               # a type name the vault uses -> one of the 22 (never one of the 22 itself)
[[types]]                         # folder rules, in order, first match wins
match = "History/**"
when = "aat-event-start-date"     # optional: the note must have this frontmatter field
type = "event"
```

Globs match note keys (paths without `.md`). Only `*` is special: within a segment it is any run of
characters; a whole `**` segment is any number of segments (none included), except at the end, where it
needs at least one (`History/**` is what's *inside* History). Everything else is literal, brackets too
(`[Draft]` is a folder name, not a character class).
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from renasci.vault.loader_types import TYPES


@lru_cache(maxsize=4096)
def _segment(pattern: str) -> re.Pattern:
    return re.compile("".join("[^/]*" if part == "*" else re.escape(part) for part in re.split(r"(\*)", pattern)))


def glob_match(pattern: str, path: str) -> bool:
    """`pattern` against a note key, segment by segment."""
    pat, parts = pattern.strip("/").split("/"), path.strip("/").split("/")

    def go(i: int, j: int) -> bool:
        if i == len(pat):
            return j == len(parts)
        if pat[i] == "**":
            if i == len(pat) - 1:
                return j < len(parts)
            return any(go(i + 1, k) for k in range(j, len(parts) + 1))
        return j < len(parts) and _segment(pat[i]).fullmatch(parts[j]) is not None and go(i + 1, j + 1)

    return go(0, 0)


@dataclass(frozen=True)
class Rule:
    match: str
    type: str
    when: str | None = None


def _strings(value, what: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ValueError(f"vault.toml: {what} is a list of strings, got {value!r}")
    return list(value)


@dataclass
class Config:
    ignore: list = field(default_factory=list)
    type_aliases: dict = field(default_factory=dict)
    rules: list = field(default_factory=list)
    digest_text: str = ""  # the file's normalised text, for the vault digest ("" when there is none)

    @classmethod
    def load(cls, root) -> Config:
        path = Path(root) / "vault.toml"
        if not path.is_file():
            return cls()
        text = path.read_bytes().decode("utf-8").removeprefix(chr(0xFEFF)).replace("\r\n", "\n")
        raw = tomllib.loads(text)
        unknown = set(raw) - {"ignore", "type_aliases", "types"}
        if unknown:
            raise ValueError(f"vault.toml: unknown settings {sorted(unknown)}")
        ignore = _strings(raw.get("ignore", []), "ignore")
        aliases = raw.get("type_aliases", {})
        if not isinstance(aliases, dict):
            raise ValueError("vault.toml: [type_aliases] is a table of name = type")
        for name, to in aliases.items():
            if name in TYPES:
                raise ValueError(f"vault.toml: type alias {name!r} would redefine one of the 22 types")
            if not isinstance(to, str) or to not in TYPES:
                raise ValueError(f"vault.toml: type alias {name!r} -> {to!r}, which is not one of the 22 types")
        rules = []
        for r in raw.get("types", []):
            if not isinstance(r, dict) or set(r) - {"match", "type", "when"} or not {"match", "type"} <= set(r):
                raise ValueError(f"vault.toml: a [[types]] rule is {{match, type, when?}}, got {r}")
            if not isinstance(r["match"], str):
                raise ValueError(f"vault.toml: a rule's match is a string, got {r['match']!r}")
            if not isinstance(r.get("when", ""), str):
                raise ValueError(f"vault.toml: a rule's when is a field name, got {r['when']!r}")
            if r["type"] not in TYPES:
                raise ValueError(f"vault.toml: rule {r['match']!r} gives type {r['type']!r}, not one of the 22")
            rules.append(Rule(r["match"], r["type"], r.get("when")))
        return cls(ignore, dict(aliases), rules, text)

    def ignored(self, key: str) -> bool:
        return any(glob_match(p, key) for p in self.ignore)

    def folder_type(self, key: str, frontmatter: dict) -> str | None:
        for r in self.rules:
            if glob_match(r.match, key) and (r.when is None or r.when in frontmatter):
                return r.type
        return None

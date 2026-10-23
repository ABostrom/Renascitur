"""Frontmatter: the YAML subset the vault's notes are written in (S2 spec §2.2).

Between a leading `---` and the next `---`:

- `key: value` scalars: plain, "double" (with `\\"`, `\\\\`, `\\n` escapes) or 'single' (with `''`)
  quoted, integers, true/false, empty (null). A key is everything before the first `: `, verbatim
  (`birth date: 4A 1` is fine);
- a value that is exactly one wikilink, quoted or not (`seat: [[Lion's Rest]]`), is a link scalar;
- flow lists `[a, "b, c"]`; block lists (`key:` then `- item`, indented or at column 0; blank and
  comment lines inside are fine);
- one level of block map (`key:` then indented `sub: value`);
- flow maps as block-list items (`- {office: "[[House X]]", from: 4A 1}`);
- `# comments` (a whole line, or after a value and a space).

Anything else (`|` blocks, anchors, unclosed brackets, deeper nesting) is a finding for that field, and
the rest still reads. A file that opens with `---` but has no key at all before the next `---` is a
horizontal rule, not frontmatter. No YAML dependency: the subset is small on purpose.
"""

from __future__ import annotations

import re

KEY = re.compile(r"^([^\s:#\-\[{][^:]*?)\s*:(?:\s+(.*?)|\s*)$")
LINK_ONLY = re.compile(r"^!?\[\[[^\[\]]+\]\]$")
INT = re.compile(r"^-?\d+$")


class Unsupported(ValueError):
    pass


def _quoted_end(t: str, i: int) -> int:
    """The index just past the quoted string starting at t[i] (escapes and '' honoured)."""
    q = t[i]
    j = i + 1
    while j < len(t):
        if q == '"' and t[j] == "\\":
            j += 2
            continue
        if t[j] == q:
            if q == "'" and t[j + 1:j + 2] == "'":
                j += 2
                continue
            return j + 1
        j += 1
    raise Unsupported("an unclosed quote")


def _unquote(t: str) -> str:
    body = t[1:-1]
    if t[0] == "'":
        return body.replace("''", "'")
    out, i = [], 0
    while i < len(body):
        if body[i] == "\\" and i + 1 < len(body):
            out.append({"n": "\n", "t": "\t"}.get(body[i + 1], body[i + 1]))
            i += 2
        else:
            out.append(body[i])
            i += 1
    return "".join(out)


def _split(text: str, opener: str, closer: str) -> list[str]:
    """Split a flow collection's inside on top-level commas (quoted strings and [[links]] kept whole). A
    quote opens a string only at an item's start or a map value's start (`Magnus' Rest` is plain text)."""
    out, cur, depth, i = [], "", 0, 0
    while i < len(text):
        c = text[i]
        if c in "\"'" and (not cur.strip() or cur.rstrip().endswith(":")):
            j = _quoted_end(text, i)
            cur += text[i:j]
            i = j
            continue
        if text.startswith("[[", i):
            end = text.find("]]", i)
            if end == -1:
                raise Unsupported("an unclosed [[link")
            cur += text[i:end + 2]
            i = end + 2
            continue
        if c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
        elif c == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
            i += 1
            continue
        cur += c
        i += 1
    if depth:
        raise Unsupported(f"an unclosed {opener}{closer}")
    if cur.strip():
        out.append(cur.strip())
    return out


def _uncomment(t: str) -> str:
    """The value without a trailing `# comment` (outside quotes and links)."""
    if t.startswith("#"):
        return ""
    i, in_link = 0, False
    while i < len(t):
        if t.startswith("[[", i):
            in_link = True
        elif t.startswith("]]", i):
            in_link = False
        elif t[i] in "\"'" and (i == 0 or t[i - 1] in " [{,:"):
            try:
                i = _quoted_end(t, i)
                continue
            except Unsupported:
                return t
        elif t[i] == "#" and not in_link and i > 0 and t[i - 1] in " \t":
            return t[:i].rstrip()
        i += 1
    return t


def scalar(text: str):
    """One value: a link scalar, a flow list or map, a quoted string, an int, a bool, null or plain text."""
    t = _uncomment(text.strip())
    if t == "" or t in ("~", "null"):
        return None
    if LINK_ONLY.match(t):
        return t
    if t[0] in "\"'":
        if _quoted_end(t, 0) != len(t):
            raise Unsupported("text after a quoted string")
        return _unquote(t)
    if t.startswith("["):
        if not t.endswith("]"):
            raise Unsupported("an unclosed [")
        return [scalar(x) for x in _split(t[1:-1], "[", "]")]
    if t.startswith("{"):
        if not t.endswith("}"):
            raise Unsupported("an unclosed {")
        out = {}
        for part in _split(t[1:-1], "{", "}"):
            k, sep, v = part.partition(":")
            if not sep or not k.strip():
                raise Unsupported(f"a flow map entry without a key: {part!r}")
            out[k.strip()] = scalar(v)
        return out
    if t[0] in "|>&*!":
        raise Unsupported(f"'{t[0]}' (block scalars, anchors and tags aren't in the subset)")
    if INT.match(t):
        return int(t)
    if t in ("true", "false"):
        return t == "true"
    return t


def _belongs(line: str) -> bool:
    """A line inside a key's block: indented, or a list item at column 0."""
    return bool(line.strip()) and (line[0].isspace() or line.startswith("- ") or line.strip() == "-")


def _skippable(line: str) -> bool:
    return not line.strip() or line.strip().startswith("#")


def parse(text: str) -> tuple[dict, list[dict], dict, int]:
    """(frontmatter, findings, line of each key (1-based, in the file), the line the body starts at (0-based))."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, [], {}, 0
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return {}, [{"field": None, "line": 1, "message": "frontmatter never closes (no second ---)"}], {}, 0
    content = [lines[i] for i in range(1, end) if not _skippable(lines[i])]
    if content and not any(KEY.match(x) for x in content):
        return {}, [], {}, 0  # a horizontal rule around prose, not frontmatter (comments alone are frontmatter)
    fm: dict = {}
    findings: list[dict] = []
    line_of: dict = {}
    i = 1
    while i < end:
        raw = lines[i]
        if _skippable(raw):
            i += 1
            continue
        m = KEY.match(raw)
        if not m:
            findings.append({"field": None, "line": i + 1, "message": f"not a key: {raw.strip()!r}"})
            i += 1
            continue
        key, value = m.group(1), m.group(2)
        line_of[key] = i + 1
        i += 1
        block = []  # the key's lines; blank and comment lines inside it are skipped
        while i < end:
            if _belongs(lines[i]) and not lines[i].strip().startswith("#"):
                block.append(lines[i])
                i += 1
            elif _skippable(lines[i]):
                j = i
                while j < end and _skippable(lines[j]):
                    j += 1
                if j < end and _belongs(lines[j]) and block:
                    i = j
                else:
                    break
            else:
                break
        try:
            if value is not None and _uncomment(value.strip()):
                if block:
                    raise Unsupported("a value and an indented block")
                fm[key] = scalar(value)
            elif not block:
                fm[key] = None
            elif all(b.strip().startswith("-") for b in block):
                fm[key] = [scalar(b.strip()[1:]) for b in block]
            else:
                sub = {}
                for b in block:
                    sm = KEY.match(b.strip())
                    if not sm or not b[0].isspace():
                        raise Unsupported(f"deeper than one level: {b.strip()!r}")
                    sub[sm.group(1)] = scalar(sm.group(2) or "")
                fm[key] = sub
        except Unsupported as err:
            findings.append({"field": key, "line": line_of[key], "message": str(err)})
    return fm, findings, line_of, end + 1

"""A small JSON Schema checker for the story layer's documents (S12 spec §1): the subset `type`, `required`,
`enum`, `items`, `properties`, `additionalProperties: false`, and nothing else (no `jsonschema` dependency).
`validate(doc, schema)` returns findings; `PACK` is the pack schema from `schemas/pack.json`."""

from __future__ import annotations

import json
from pathlib import Path

PACK = json.loads((Path(__file__).resolve().parents[3] / "schemas" / "pack.json").read_text(encoding="utf-8"))
TYPES = {"string": str, "integer": int, "number": (int, float), "boolean": bool, "array": list, "object": dict,
         "null": type(None)}
KEYWORDS = {"about", "type", "required", "enum", "items", "properties", "additionalProperties"}


def _is(value, kind: str) -> bool:
    if kind in ("integer", "number") and isinstance(value, bool):
        return False  # (true isn't 1 here)
    return isinstance(value, TYPES[kind])


def validate(doc, schema: dict, path: str = "$") -> list[dict]:
    """Every way `doc` breaks `schema`: [{path, message}]."""
    unknown = set(schema) - KEYWORDS
    if unknown:
        raise ValueError(f"the schema at {path} uses keywords this checker doesn't know: {sorted(unknown)}")
    if "enum" in schema and doc not in schema["enum"]:
        return [{"path": path, "message": f"{doc!r} isn't one of {schema['enum']}"}]
    kinds = schema.get("type")
    if kinds is not None:
        kinds = [kinds] if isinstance(kinds, str) else kinds
        if not any(_is(doc, k) for k in kinds):
            return [{"path": path, "message": f"expected {' or '.join(kinds)}, got {type(doc).__name__}"}]
    out = []
    if isinstance(doc, dict):
        for k in schema.get("required", []):
            if k not in doc:
                out.append({"path": f"{path}.{k}", "message": "missing"})
        props = schema.get("properties", {})
        for k, v in doc.items():
            if k in props:
                out += validate(v, props[k], f"{path}.{k}")
            elif schema.get("additionalProperties") is False:
                out.append({"path": f"{path}.{k}", "message": "not allowed here"})
    if isinstance(doc, list) and "items" in schema:
        for i, v in enumerate(doc):
            out += validate(v, schema["items"], f"{path}[{i}]")
    return out

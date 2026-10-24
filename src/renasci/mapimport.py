"""Importing an Inkarnate map (S5 spec §4, #82): the private layers the editor starts from.

`import_map(image, out, water=[(x, y), ...], marker=(x, y))` reads the image once and writes, into `out`
(a world's `maps/<world>/private/`, git-ignored: the map is private):

- `base.png`: the image reduced to `base_width` (about 4096 px), for the editor to draw on;
- `mask.png`: land (white) and water (black) at `mask_width`. Water is whatever is near one of the
  `water` sample colours, so a painted frame isn't taken for sea; it's cleaned of specks by a small
  open/close. The grid (#80) takes each cell's land or water from it;
- `markers.json`: settlement markers. These are blobs of the `marker` sample's colour, about its size,
  and square (a round blob is a different icon). Each has its position as **fractions of the map's
  width and height**, so a different resolution of the same map gives the same numbers (they become
  cells once the grid knows the map's scale), its `size` (its width, as a fraction of the map's) and a
  `confidence` (its squareness). Which place each one is, the editor asks. The marker point must land in
  an icon's fill: a miss, a speck or an outline is refused, rather than finding nothing or everything;
- `import.json`: what was asked for and what was found.

Sample points are in the original image's pixels, as an image viewer shows them. Needs Pillow (the `map`
extra); the engine never imports this module.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

WATER_TOL = 40.0  # (RGB distance to a sample colour that still counts as it)
MARKER_TOL = 40.0
SQUARE_FILL = 0.88  # (a square fills its box; a circle fills about 0.785 of it)


def _open(path):
    """The image, decoded once at full size (PNG can't be decoded in strips: one zlib stream with per-row
    filters). Over Pillow's decompression-bomb limit, as the map is, so the limit is lifted for this call."""
    from PIL import Image

    limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = None
    try:
        img = Image.open(path)
        img.load()
    finally:
        Image.MAX_IMAGE_PIXELS = limit
    return img


def _size(path) -> tuple[int, int]:
    """The image's size without decoding it (so bad sample points fail before the long decode)."""
    from PIL import Image

    limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = None
    try:
        with Image.open(path) as img:
            return img.size
    finally:
        Image.MAX_IMAGE_PIXELS = limit


def _resized(img, width: int):
    """`img` reduced to `width` across (box filter), as RGB. Reduced first, converted after: converting
    the full map would copy all of it."""
    from PIL import Image

    w, h = img.size
    width = min(width, w)
    small = img.resize((width, max(1, round(h * width / w))), Image.Resampling.BOX) if width != w else img
    return small if small.mode == "RGB" else small.convert("RGB")


def _sample(arr: np.ndarray, x: float, y: float) -> np.ndarray:
    """The median colour of a small patch at a point given as fractions of the image."""
    h, w = arr.shape[:2]
    cx, cy = min(w - 1, int(x * w)), min(h - 1, int(y * h))
    patch = arr[max(0, cy - 1):cy + 2, max(0, cx - 1):cx + 2].reshape(-1, 3)
    return np.median(patch, axis=0)


def _near(arr: np.ndarray, colours, tol: float, rows: int = 512) -> np.ndarray:
    """Pixels within `tol` (RGB distance) of any colour, a block of rows at a time (integer squares: the
    marker-width image is tens of megapixels)."""
    out = np.zeros(arr.shape[:2], dtype=bool)
    cs = [np.asarray(c, dtype=np.int32) for c in colours]
    t2 = int(tol * tol)
    for y in range(0, arr.shape[0], rows):
        block = arr[y:y + rows].astype(np.int32)
        for c in cs:
            out[y:y + rows] |= ((block - c) ** 2).sum(axis=2) <= t2
    return out


def _shift_all(mask: np.ndarray, r: int, op) -> np.ndarray:
    """Erosion (op=np.logical_and) or dilation (np.logical_or) by a (2r+1) square, edges padded neutrally."""
    pad = np.pad(mask, r, constant_values=op is np.logical_and)
    out = pad[r:r + mask.shape[0], r:r + mask.shape[1]].copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            out = op(out, pad[r + dy:r + dy + mask.shape[0], r + dx:r + dx + mask.shape[1]])
    return out


def clean(mask: np.ndarray, r: int = 1) -> np.ndarray:
    """Open then close: specks of one in the other removed, outlines kept."""
    opened = _shift_all(_shift_all(mask, r, np.logical_and), r, np.logical_or)
    return _shift_all(_shift_all(opened, r, np.logical_or), r, np.logical_and)


def components(mask: np.ndarray) -> list[dict]:
    """Connected blobs (4-connected) by runs per row joined with union-find: each with its box, area and
    centroid (in pixels)."""
    parent: list[int] = []

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    runs: list[tuple[int, int, int, int]] = []  # (row, start, end, label)
    above: list[tuple[int, int, int]] = []
    for y in range(mask.shape[0]):
        row = mask[y]
        if not row.any():
            above = []
            continue
        edges = np.flatnonzero(np.diff(np.concatenate(([0], row.view(np.int8), [0]))))
        here = []
        for s, e in zip(edges[::2], edges[1::2]):
            label = len(parent)
            parent.append(label)
            for (ps, pe, pl) in above:
                if ps < e and s < pe:  # (overlapping runs touch)
                    a, b = find(pl), find(label)
                    if a != b:
                        parent[max(a, b)] = min(a, b)
            here.append((s, e, label))
            runs.append((y, s, e, label))
        above = here
    blobs: dict[int, dict] = {}
    for y, s, e, label in runs:
        b = blobs.setdefault(find(label), {"x0": s, "x1": e, "y0": y, "y1": y + 1, "area": 0, "sx": 0.0, "sy": 0.0})
        n = e - s
        b["x0"], b["x1"], b["y0"], b["y1"] = min(b["x0"], s), max(b["x1"], e), min(b["y0"], y), max(b["y1"], y + 1)
        b["area"] += n
        b["sx"] += n * (s + e - 1) / 2
        b["sy"] += n * y
    out = []
    for b in blobs.values():
        out.append({"box": (int(b["x0"]), int(b["y0"]), int(b["x1"]), int(b["y1"])), "area": int(b["area"]),
                    "cx": b["sx"] / b["area"], "cy": b["sy"] / b["area"]})
    return sorted(out, key=lambda b: (b["cy"], b["cx"]))


def _squareness(b: dict) -> float:
    x0, y0, x1, y1 = b["box"]
    w, h = x1 - x0, y1 - y0
    return (b["area"] / (w * h)) * (min(w, h) / max(w, h))


def _model(blobs: list[dict], mx: float, my: float, reach: float = 4.0) -> dict:
    """The blob the marker sample point is on (or within `reach` px of): the marker every other is like.
    Refused when the point misses, or lands on something too small or not square to be a marker."""
    def gap(b):
        x0, y0, x1, y1 = b["box"]
        return max(x0 - mx, 0, mx - (x1 - 1)) ** 2 + max(y0 - my, 0, my - (y1 - 1)) ** 2

    near = [b for b in blobs if gap(b) <= reach * reach]
    if not near:
        raise ValueError("the marker point isn't on a marker: pick a pixel inside one settlement icon's fill")
    model = min(near, key=lambda b: (gap(b), (b["cx"] - mx) ** 2 + (b["cy"] - my) ** 2))
    if model["area"] < 16:
        raise ValueError(f"the marker point is on a speck ({model['area']} px at this width), not an icon: "
                         "pick a pixel inside one settlement icon's fill, or raise --marker-width")
    if _squareness(model) < SQUARE_FILL:
        raise ValueError(f"the marker point's blob isn't square (squareness {_squareness(model):.2f}): "
                         "pick a pixel inside a settlement icon's fill, not its outline or label")
    return model


def import_map(image, out, water, marker, base_width: int = 4096, mask_width: int = 1024,
               marker_width: int = 8192, water_tol: float = WATER_TOL, marker_tol: float = MARKER_TOL,
               force: bool = False) -> dict:
    """Write the private layers (see the module doc); returns what `import.json` says.

    Peak memory is the decoded image (about 4 bytes a pixel: some 800 MB for the 198-megapixel map) plus
    the marker-width copy and its masks."""
    W, H = _size(image)
    for x, y in [*water, marker]:
        if not (0 <= x < W and 0 <= y < H):
            raise ValueError(f"sample point ({x}, {y}) is outside the {W}x{H} image")
    out = Path(out)
    if (out / "markers.json").exists() and not force:
        raise ValueError(f"{out} already has an import: pass --force to replace it")
    full = _open(image)
    fine_img = _resized(full, marker_width)  # (every smaller layer comes from this one: the full map is let go)
    del full
    out.mkdir(parents=True, exist_ok=True)
    _resized(fine_img, base_width).save(out / "base.png")
    fine = np.asarray(fine_img)
    fh, fw = fine.shape[:2]
    sea = [_sample(fine, x / W, y / H) for x, y in water]  # (sampled fine: a shore point isn't mixed with land)
    small = np.asarray(_resized(fine_img, mask_width))
    land = ~clean(_near(small, sea, water_tol))
    from PIL import Image

    Image.fromarray((land * 255).astype(np.uint8)).save(out / "mask.png")

    colour = _sample(fine, marker[0] / W, marker[1] / H)
    blobs = components(_near(fine, [colour], marker_tol))
    model = _model(blobs, marker[0] / W * fw, marker[1] / H * fh)
    found = []
    for b in blobs:
        if not 0.5 * model["area"] <= b["area"] <= 2 * model["area"]:
            continue
        sq = _squareness(b)
        if sq < SQUARE_FILL:
            continue
        found.append({"x": round(b["cx"] / fw, 5), "y": round(b["cy"] / fh, 5),
                      "size": round(((b["box"][2] - b["box"][0]) / fw), 5), "confidence": round(min(1.0, sq), 3)})
    found.sort(key=lambda m: (m["y"], m["x"]))
    for i, m in enumerate(found, 1):
        m["id"] = f"m{i}"
    (out / "markers.json").write_text(json.dumps({"markers": found}, indent=1), encoding="utf-8")
    report = {"source": {"name": Path(image).name, "size": [W, H]}, "water": [list(p) for p in water],
              "marker": list(marker), "water_colours": [[int(v) for v in c] for c in sea],
              "marker_colour": [int(v) for v in colour], "land": round(float(land.mean()), 4), "markers": len(found),
              "widths": {"base": base_width, "mask": mask_width, "markers": marker_width}}
    (out / "import.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    return report

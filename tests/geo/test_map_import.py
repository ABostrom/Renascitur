"""Importing an Inkarnate map (S5 spec §4, #82), on synthetic images drawn here: a framed sea, an island,
four square settlement markers on it and a round blob that isn't one."""

import json

import pytest

PIL = pytest.importorskip("PIL")
from PIL import Image, ImageDraw  # noqa: E402

from renasci import mapimport  # noqa: E402

SEA, LAND, FRAME, MARK = (40, 90, 160), (110, 150, 80), (30, 25, 20), (200, 30, 30)
SQUARES = [(0.40, 0.40), (0.55, 0.45), (0.45, 0.60), (0.60, 0.58)]  # (as fractions of the width and height)


def draw(path, width=2000, height=1500):
    """The test map at any resolution (the same picture, scaled)."""
    img = Image.new("RGB", (width, height), SEA)
    d = ImageDraw.Draw(img)
    f = width / 2000
    d.rectangle([0, 0, width - 1, height - 1], outline=FRAME, width=int(30 * f))  # (a frame: corners aren't sea)
    d.ellipse([0.25 * width, 0.25 * height, 0.75 * width, 0.75 * height], fill=LAND)
    for x, y in SQUARES:
        s = 12 * f
        d.rectangle([x * width - s, y * height - s, x * width + s, y * height + s], fill=MARK)
    d.ellipse([0.5 * width - 14 * f, 0.33 * height - 14 * f, 0.5 * width + 14 * f, 0.33 * height + 14 * f], fill=MARK)
    img.save(path)
    return path


def run(tmp_path, width=2000, height=1500, **kw):
    src = draw(tmp_path / f"map{width}.png", width, height)
    out = tmp_path / f"out{width}"
    f = width / 2000
    return mapimport.import_map(src, out, water=[(int(100 * f), int(700 * f))], marker=(int(0.4 * width), int(0.4 * height)),
                                base_width=400, mask_width=200, marker_width=1000, **kw), out


def test_it_writes_the_private_layers(tmp_path):
    report, out = run(tmp_path)
    assert {p.name for p in out.iterdir()} == {"base.png", "mask.png", "markers.json", "import.json"}
    assert Image.open(out / "base.png").size == (400, 300)
    assert report["markers"] == 4 and report["source"]["size"] == [2000, 1500]


def test_the_island_is_land_and_the_frame_is_not_taken_for_sea(tmp_path):
    _, out = run(tmp_path)
    mask = Image.open(out / "mask.png").convert("L")
    w, h = mask.size
    assert mask.getpixel((w // 2, h // 2)) == 255  # (land: the island)
    assert mask.getpixel((int(0.1 * w), h // 2)) == 0  # (water: the sea)
    assert mask.getpixel((0, 0)) == 255  # (the frame isn't sea-coloured: not water)


def test_four_square_markers_are_found_where_they_are_and_the_round_blob_is_not(tmp_path):
    _, out = run(tmp_path)
    found = json.loads((out / "markers.json").read_text(encoding="utf-8"))["markers"]
    assert len(found) == 4
    for (x, y) in SQUARES:
        assert any(abs(m["x"] - x) < 0.01 and abs(m["y"] - y) < 0.01 for m in found), (x, y)
    assert all(0 < m["confidence"] <= 1 for m in found) and [m["id"] for m in found] == ["m1", "m2", "m3", "m4"]


def test_positions_are_the_same_at_another_resolution(tmp_path):
    _, a = run(tmp_path, 2000, 1500)
    _, b = run(tmp_path, 4000, 3000)
    ma = json.loads((a / "markers.json").read_text(encoding="utf-8"))["markers"]
    mb = json.loads((b / "markers.json").read_text(encoding="utf-8"))["markers"]
    assert [(round(m["x"], 2), round(m["y"], 2)) for m in ma] == [(round(m["x"], 2), round(m["y"], 2)) for m in mb]


def test_an_image_over_pillows_bomb_limit_still_imports(tmp_path, monkeypatch):
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1000)  # (the real map is over the default limit)
    report, _ = run(tmp_path)
    assert report["markers"] == 4


def test_a_sample_outside_the_image_is_refused(tmp_path):
    src = draw(tmp_path / "m.png")
    with pytest.raises(ValueError, match="outside"):
        mapimport.import_map(src, tmp_path / "o", water=[(5000, 10)], marker=(800, 600))


def test_the_cli_imports_into_the_worlds_private_folder(tmp_path):
    from renasci.cli import main

    src = draw(tmp_path / "m.png")
    assert main(["map", "import", str(src), "--world", "testland", "--maps", str(tmp_path / "maps"),
                 "--water", "100,700", "--marker", "800,600", "--base-width", "400", "--marker-width", "1000"]) == 0
    assert (tmp_path / "maps" / "testland" / "private" / "markers.json").is_file()


@pytest.mark.parametrize("marker, why", [((100, 700), "pick a pixel"),  # (the sea: one huge blob)
                                         ((int(0.5 * 2000) - 13, int(0.33 * 1500)), "square")])  # (the round blob)
def test_a_marker_point_that_misses_an_icon_is_refused(tmp_path, marker, why):
    src = draw(tmp_path / "m.png")
    with pytest.raises(ValueError, match=why):
        mapimport.import_map(src, tmp_path / "o", water=[(100, 700)], marker=marker, marker_width=1000)


def test_an_import_is_not_replaced_without_force(tmp_path):
    report, out = run(tmp_path)
    src = tmp_path / "map2000.png"
    with pytest.raises(ValueError, match="force"):
        mapimport.import_map(src, out, water=[(100, 700)], marker=(800, 600), marker_width=1000)
    assert mapimport.import_map(src, out, water=[(100, 700)], marker=(800, 600), marker_width=1000, force=True)["markers"] == 4


def test_the_cli_refuses_to_write_inside_the_repo_where_git_would_not_ignore_it(tmp_path):
    from renasci.cli import REPO, main

    src = draw(tmp_path / "m.png")
    assert main(["map", "import", str(src), "--world", "testland", "--maps", str(REPO / "observatory" / "maps"),
                 "--water", "100,700", "--marker", "800,600"]) != 0
    assert not (REPO / "observatory" / "maps").exists()

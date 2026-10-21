"""Inline poc/out/poc_data.json into the Observatory template -> poc/out/observatory.html."""
import json
from pathlib import Path

here = Path(__file__).parent
data = json.loads((here / "out" / "poc_data.json").read_text())
for run in data["runs"].values():
    for p in run["people"].values():
        # trim noise the viewer does not need: repeated identical drive snapshots
        hist, last = [], None
        for h in p["history"]:
            if h[1] == "drives" and h[2] == last:
                continue
            if h[1] == "drives":
                last = h[2]
            hist.append(h)
        p["history"] = hist
blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
html = (here / "observatory_template.html").read_text(encoding="utf-8").replace("/*DATA*/", blob)
out = here / "out" / "observatory.html"
out.write_text(html, encoding="utf-8")
print(f"wrote {out} ({out.stat().st_size // 1024} KB)")

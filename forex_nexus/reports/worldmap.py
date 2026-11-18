"""Weltkarte für die Website: Natural-Earth-Länder (world-atlas 110m, ISC-Lizenz, Daten gemeinfrei)
-> SVG-Pfade in der flächentreuen Equal-Earth-Projektion."""

from __future__ import annotations

import json
import math
from pathlib import Path

A1, A2, A3, A4 = 1.340264, -0.081106, 0.000893, 0.003796
M = math.sqrt(3) / 2
WIDTH = 1000.0

# Volkswirtschaften der Plattform (ISO-3166 numerisch) und Marker-Koordinaten (Länge, Breite)
ECONOMIES = {
    "US": {"iso": ["840"], "lonlat": (-98, 39), "label": "USD"},
    "EA": {"iso": ["040", "056", "191", "196", "233", "246", "250", "276", "300", "372", "380", "428", "440",
                   "442", "470", "528", "620", "703", "705", "724"], "lonlat": (8, 49), "label": "EUR"},
    "JP": {"iso": ["392"], "lonlat": (138, 36), "label": "JPY"},
    "GB": {"iso": ["826"], "lonlat": (-2, 53.5), "label": "GBP"},
    "CH": {"iso": ["756"], "lonlat": (8.2, 46.8), "label": "CHF"},
    "CA": {"iso": ["124"], "lonlat": (-106, 57), "label": "CAD"},
    "AU": {"iso": ["036"], "lonlat": (134, -25), "label": "AUD"},
    "NZ": {"iso": ["554"], "lonlat": (172, -41.5), "label": "NZD"},
    "CN": {"iso": ["156"], "lonlat": (104, 35), "label": "China"},
}


def project(lon: float, lat: float) -> tuple[float, float]:
    lam, phi = math.radians(lon), math.radians(lat)
    theta = math.asin(M * math.sin(phi))
    t2 = theta * theta
    t6 = t2 ** 3
    x = 2 * math.sqrt(3) * lam * math.cos(theta) / (3 * (9 * A4 * t6 * t2 + 7 * A3 * t6 + 3 * A2 * t2 + A1))
    y = theta * (A4 * t6 * t2 + A3 * t6 + A2 * t2 + A1)
    return x, y


X_MAX = project(180, 0)[0]
Y_MAX = project(0, 90)[1]
SCALE = WIDTH / (2 * X_MAX)
HEIGHT = 2 * Y_MAX * SCALE


def to_svg(lon, lat):
    x, y = project(lon, lat)
    return round((x + X_MAX) * SCALE, 1), round((Y_MAX - y) * SCALE, 1)


def build(topojson_path: Path) -> dict:
    topo = json.loads(topojson_path.read_text())
    sx, sy = topo["transform"]["scale"]
    tx, ty = topo["transform"]["translate"]
    arcs = []
    for arc in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x += dx
            y += dy
            pts.append((x * sx + tx, y * sy + ty))
        arcs.append(pts)

    def ring(indices):
        pts = []
        for i in indices:
            a = arcs[i] if i >= 0 else arcs[~i][::-1]
            pts.extend(a if not pts else a[1:])
        return pts

    countries = {}
    for g in topo["objects"]["countries"]["geometries"]:
        cid = g.get("id")
        if cid == "010" or g["type"] not in ("Polygon", "MultiPolygon"):
            continue                                  # Antarktis weglassen
        polys = [g["arcs"]] if g["type"] == "Polygon" else g["arcs"]
        d = []
        for poly in polys:
            for r in poly:
                pts = [to_svg(lon, lat) for lon, lat in ring(r)]
                if len(pts) < 3:
                    continue
                d.append("M" + "L".join(f"{x:g},{y:g}" for x, y in pts) + "Z")
        countries[cid or g["properties"].get("name")] = "".join(d)
    economies = {k: {"label": v["label"], "iso": v["iso"], "xy": to_svg(*v["lonlat"])} for k, v in ECONOMIES.items()}
    return {"width": WIDTH, "height": round(HEIGHT, 1), "countries": countries, "economies": economies,
            "attribution": "Kartendaten: Natural Earth über world-atlas (ISC-Lizenz)"}


if __name__ == "__main__":
    import sys
    out = build(Path(sys.argv[1]))
    Path(sys.argv[2]).write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(f"{len(out['countries'])} Länder, {Path(sys.argv[2]).stat().st_size // 1024} KB")

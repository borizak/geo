import os, time, math
import numpy as np
import requests
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify, render_template
from sgp4.api import Satrec, jday

app = Flask(__name__)
CESIUM_TOKEN = os.environ.get("CESIUM_TOKEN", "")
TLE_URL = "https://celestrak.org/NORAD/elements/gps-ops.txt"
_cache = {"tles": None, "at": 0}

DURATION_H = 12    # hours of trajectory to show
STEP_MIN   = 2     # sample interval in minutes


def fetch_tles():
    now = time.time()
    if _cache["tles"] and now - _cache["at"] < 3600:
        return _cache["tles"]
    resp = requests.get(TLE_URL, timeout=15)
    resp.raise_for_status()
    lines = [l.strip() for l in resp.text.splitlines() if l.strip()]
    tles = []
    for i in range(0, len(lines) - 2, 3):
        tles.append((lines[i], lines[i+1], lines[i+2]))
    _cache["tles"] = tles
    _cache["at"]   = now
    return tles


def gmst(jd, fr):
    T = (jd + fr - 2451545.0) / 36525.0
    sec = (67310.54841
           + (876600 * 3600 + 8640184.812866) * T
           + 0.093104 * T**2
           - 6.2e-6   * T**3)
    return math.radians((sec % 86400.0) / 240.0)


def teme_to_geodetic(r_km, jd, fr):
    x, y, z = r_km
    g  = gmst(jd, fr)
    cg, sg = math.cos(g), math.sin(g)
    xe = cg * x + sg * y
    ye = -sg * x + cg * y
    ze = z

    # Bowring iterative geodetic (WGS-84)
    a, b = 6378.137, 6356.7523142
    e2   = 1 - (b/a)**2
    lon  = math.atan2(ye, xe)
    p    = math.sqrt(xe**2 + ye**2)
    lat  = math.atan2(ze, p * (1 - e2))
    for _ in range(5):
        N   = a / math.sqrt(1 - e2 * math.sin(lat)**2)
        lat = math.atan2(ze + e2 * N * math.sin(lat), p)
    N   = a / math.sqrt(1 - e2 * math.sin(lat)**2)
    alt = p / math.cos(lat) - N if abs(math.cos(lat)) > 1e-10 else abs(ze) / math.sin(lat) - N * (1 - e2)

    return math.degrees(lat), math.degrees(lon), alt * 1000  # alt in metres


def build_czml(tles):
    t0 = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    t1 = t0 + timedelta(hours=DURATION_H)
    iso0 = t0.isoformat().replace("+00:00", "Z")
    iso1 = t1.isoformat().replace("+00:00", "Z")
    interval = f"{iso0}/{iso1}"

    doc = [{"id": "document", "name": "GPS", "version": "1.0",
            "clock": {"currentTime": iso0, "multiplier": 60,
                      "interval": interval}}]

    steps = int(DURATION_H * 60 / STEP_MIN) + 1

    for name, l1, l2 in tles:
        sat = Satrec.twoline2rv(l1, l2)
        cartesian = []  # epoch-seconds + x,y,z in metres (ECEF)
        ok = True
        for i in range(steps):
            dt  = t0 + timedelta(minutes=i * STEP_MIN)
            jd, fr = jday(dt.year, dt.month, dt.day,
                          dt.hour, dt.minute, dt.second + dt.microsecond / 1e6)
            e, r, _ = sat.sgp4(jd, fr)
            if e != 0:
                ok = False
                break
            lat, lon, alt = teme_to_geodetic(r, jd, fr)
            # CZML cartographicDegrees: [seconds, lon, lat, alt]
            cartesian.append(i * STEP_MIN * 60)
            cartesian.append(lon)
            cartesian.append(lat)
            cartesian.append(alt)

        if not ok:
            continue

        doc.append({
            "id":   name,
            "name": name,
            "availability": interval,
            "position": {
                "interpolationAlgorithm": "LAGRANGE",
                "interpolationDegree": 5,
                "referenceFrame": "FIXED",
                "epoch": iso0,
                "cartographicDegrees": cartesian,
            },
            "point": {
                "color": {"rgba": [0, 220, 255, 255]},
                "pixelSize": 6,
                "outlineColor": {"rgba": [255, 255, 255, 80]},
                "outlineWidth": 1,
            },
            "path": {
                "show": True,
                "leadTime":  STEP_MIN * 60 * 30,
                "trailTime": STEP_MIN * 60 * 30,
                "width": 1,
                "material": {"solidColor": {"color": {"rgba": [0, 180, 255, 120]}}},
            },
        })

    return doc


@app.route("/")
def index():
    return render_template("index.html", cesium_token=CESIUM_TOKEN)


@app.route("/api/czml")
def czml():
    return jsonify(build_czml(fetch_tles()))


if __name__ == "__main__":
    app.run(debug=True, port=5000)

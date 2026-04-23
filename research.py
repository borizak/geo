import matplotlib
matplotlib.use('TkAgg')

import numpy as np
import matplotlib.pyplot as plt
import mplcursors

# ---------------------------
# Constants
G = 6.67430e-11
M = 5.972e24
c = 299792458
R_earth = 6371e3
v_gps = 3874
r_gps = R_earth + 20200e3

# ---------------------------
# Satellites and points
np.random.seed(42)
satellites = []
for _ in range(10):
    phi = np.random.uniform(0, 2*np.pi)
    theta = np.radians(55)
    x = r_gps * np.cos(phi) * np.cos(theta)
    y = r_gps * np.sin(phi) * np.cos(theta)
    z = r_gps * np.sin(theta)
    satellites.append([x, y, z])
satellites = np.array(satellites)

points = [
    (0,0), (30,30), (45,90), (-30,60), (60,-60),
    (-45,-45), (15,-90), (75,45), (-60,120), (0,180)
]

# ---------------------------
# Helper functions
def time_dilation(observer, sat):
    r_sat = np.linalg.norm(sat)
    r_obs = np.linalg.norm(observer)
    d = np.linalg.norm(sat - observer)
    grav = G * M * (1/r_obs - 1/r_sat) / c**2
    vel = - (v_gps**2) / (2 * c**2)
    return grav + vel, d

def latlon_to_ecef(lat_deg, lon_deg):
    lat = np.radians(lat_deg)
    lon = np.radians(lon_deg)
    x = R_earth * np.cos(lat) * np.cos(lon)
    y = R_earth * np.cos(lat) * np.sin(lon)
    z = R_earth * np.sin(lat)
    return np.array([x, y, z])

# ---------------------------
# Prepare figure with 2 subplots
fig, axes = plt.subplots(1,2, figsize=(16,7))
lines = []
markers = []

for ax_idx, ax in enumerate(axes):
    is_daily_gain = (ax_idx == 1)  # second graph converts to time gain per day
    for sat_idx, sat in enumerate(satellites):
        p0 = latlon_to_ecef(*points[0])
        pN = latlon_to_ecef(*points[-1])
        d0 = np.linalg.norm(sat - p0)
        dN = np.linalg.norm(sat - pN)
        dist_range = np.linspace(min(d0,dN), max(d0,dN), 100)
        distances = []
        dilations = []
        for d in dist_range:
            alpha = (d - min(d0,dN)) / (max(d0,dN)-min(d0,dN))
            observer = p0*(1-alpha) + pN*alpha
            dilation, _ = time_dilation(observer, sat)
            if is_daily_gain:
                dilation = dilation * 86400  # seconds/day
            distances.append(d/1e3)
            dilations.append(dilation)
        line, = ax.plot(distances, dilations, label=f"Sat {sat_idx}")
        lines.append(line)

    markers = []
    for pt_idx, (lat, lon) in enumerate(points):
        observer = latlon_to_ecef(lat, lon)
        dil_sat = []
        dists = []
        for sat_idx, sat in enumerate(satellites):
            dilation, d = time_dilation(observer, sat)
            if is_daily_gain:
                dilation = dilation * 86400
            dil_sat.append(dilation)
            dists.append(d/1e3)
            m, = ax.plot(d/1e3, dilation, 'o', label=f"P{pt_idx} S{sat_idx}")
            markers.append(m)

        # Δ lines between all satellite pairs
        for i in range(len(satellites)):
            for j in range(i+1, len(satellites)):
                ax.plot([dists[i], dists[j]], [dil_sat[i], dil_sat[j]], '--', color='red', alpha=0.5)
    
    ax.set_xlabel("Distance to satellite (km)")
    ax.set_ylabel("Time dilation" + (" (s/day)" if is_daily_gain else " (relative)"))
    ax.set_title("Time dilation (s/day)" if is_daily_gain else "Time dilation (relative)")
    ax.grid(True)

axes[0].legend(fontsize=6, ncol=2)
axes[1].legend(fontsize=6, ncol=2)

# Interactive tooltips on first subplot only
cursor = mplcursors.cursor(lines + markers, hover=True)
@cursor.connect("add")
def on_add(sel):
    x, y = sel.target
    sel.annotation.set_text(f"Distance: {x:.1f} km\nDilation: {y:.3e}" if axes[0] else f"{y:.3e} s/day")

plt.tight_layout()
plt.show()

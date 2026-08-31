import json
import math
import os
from pyproj import Transformer
import matplotlib.pyplot as plt
import numpy as np

# --------------------------------------------------
# 1. Configuration & Input / Output Paths
# --------------------------------------------------
INPUT_FILE = "outputs/contours.json"
OUTPUT_FILE = "outputs/projected_contours.json"

# Ensure output directory exists
os.makedirs("outputs", exist_ok=True)

# --------------------------------------------------
# 2. Load Parsed Contours
# --------------------------------------------------
with open(INPUT_FILE, "r") as f:
    contours = json.load(f)

print(f"Loaded {len(contours):,} contours from {INPUT_FILE}")

# --------------------------------------------------
# 3. Determine Geographic Centroid & UTM Zone
# --------------------------------------------------
all_points = []
for contour in contours:
    for lon, lat in contour["coordinates"]:
        all_points.append((lon, lat))

if not all_points:
    raise ValueError(f"No coordinates found in {INPUT_FILE}")

mean_lon = sum(lon for lon, lat in all_points) / len(all_points)
mean_lat = sum(lat for lon, lat in all_points) / len(all_points)

# Automatic UTM Zone calculation
utm_zone = math.floor((mean_lon + 180) / 6) + 1
hemisphere = "north" if mean_lat >= 0 else "south"
epsg = (32600 if hemisphere == "north" else 32700) + utm_zone

print(f"Center Longitude: {mean_lon:.6f}°")
print(f"Center Latitude : {mean_lat:.6f}°")
print(f"Detected UTM Zone: {utm_zone} ({hemisphere.capitalize()}) -> EPSG:{epsg}")

# --------------------------------------------------
# 4. Transform Coordinates (WGS84 -> UTM Meters)
# --------------------------------------------------
transformer = Transformer.from_crs(
    "EPSG:4326",       # Source: WGS84 degrees
    f"EPSG:{epsg}",    # Target: Metric UTM
    always_xy=True
)

projected_contours = []

for contour in contours:
    projected_coordinates = []
    for lon, lat in contour["coordinates"]:
        x, y = transformer.transform(lon, lat)
        projected_coordinates.append([x, y])

    projected_contours.append({
        "id": contour["id"],
        "elevation": contour["elevation"],
        "coordinates": projected_coordinates
    })

# --------------------------------------------------
# 5. Save Projected Dataset
# --------------------------------------------------
output_data = {
    "coordinate_system": {
        "source": "EPSG:4326",
        "target": f"EPSG:{epsg}",
        "projection": "UTM",
        "utm_zone": utm_zone,
        "hemisphere": hemisphere,
        "units": "meters"
    },
    "contours": projected_contours
}

with open(OUTPUT_FILE, "w") as f:
    json.dump(output_data, f, indent=2)

print(f"Successfully projected {len(projected_contours):,} contours.")
print(f"Saved to: {OUTPUT_FILE}")

# --------------------------------------------------
# 6. Preview & Visualization
# --------------------------------------------------
first_contour = projected_contours[0]
print(f"\nFirst Contour (ID: {first_contour['id']}, Elevation: {first_contour['elevation']} m):")
print(f"  First Projected Coordinate (X, Y in meters): {first_contour['coordinates'][0]}")

# Optional: Plot projected metric contour lines
plt.figure(figsize=(9, 6))
for c in projected_contours[::5]:
    pts = np.array(c["coordinates"])
    plt.plot(pts[:, 0], pts[:, 1], color="navy", linewidth=0.6, alpha=0.7)

plt.title(f"Step 2: Projected Metric Contours (EPSG:{epsg}, Units: Meters)", fontsize=12)
plt.xlabel("UTM Easting (meters)")
plt.ylabel("UTM Northing (meters)")
plt.grid(True, linestyle="--", alpha=0.5)
plt.show()

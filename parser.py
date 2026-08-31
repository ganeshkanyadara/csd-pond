import xml.etree.ElementTree as ET
import json
import matplotlib.pyplot as plt
import numpy as np

# --------------------------------------------------
# 1. Configuration & XML Namespace
# --------------------------------------------------
INPUT_KML = "contours_1m.kml"
OUTPUT_JSON = "outputs/contours.json"

NAMESPACE = {
    "kml": "http://www.opengis.net/kml/2.2"
}

# --------------------------------------------------
# 2. Parse KML Tree & Extract Placemarks
# --------------------------------------------------
print(f"Reading {INPUT_KML}...")
tree = ET.parse(INPUT_KML)
root = tree.getroot()

placemarks = root.findall(".//kml:Placemark", NAMESPACE)
contours = []

for placemark in placemarks:
    # Extract Contour ID (ensures only real contour lines are parsed)
    id_element = placemark.find(".//kml:SimpleData[@name='ID']", NAMESPACE)
    if id_element is None or id_element.text is None:
        continue

    contour_id = int(id_element.text)

    # Extract Elevation
    name = placemark.find("kml:name", NAMESPACE)
    elevation = float(name.text) if (name is not None and name.text) else 0.0

    # Extract Coordinates from LineString
    coordinates_element = placemark.find(".//kml:coordinates", NAMESPACE)
    if coordinates_element is None or not coordinates_element.text:
        continue

    coordinates_text = coordinates_element.text.strip()
    points = []

    for point in coordinates_text.split():
        parts = point.split(",")
        if len(parts) >= 2:
            lon, lat = float(parts[0]), float(parts[1])
            points.append([lon, lat])

    # Store structured contour object
    contours.append({
        "id": contour_id,
        "elevation": elevation,
        "coordinates": points
    })

# --------------------------------------------------
# 3. Save Structured Intermediate Output
# --------------------------------------------------
with open(OUTPUT_JSON, "w") as f:
    json.dump(contours, f, indent=2)

print(f"Total contours parsed: {len(contours):,}")
print(f"Saved parsed data to: {OUTPUT_JSON}")

# --------------------------------------------------
# 4. Preview / Verification in Notebook
# --------------------------------------------------
for c in contours[:3]:
    print(f"\nContour ID: {c['id']} | Elevation: {c['elevation']} m | Points: {len(c['coordinates'])}")
    print(f"  First Point (Lon, Lat): {c['coordinates'][0]}")

# Optional: Plot parsed contour lines
plt.figure(figsize=(9, 6))
for c in contours[::5]:  # Plot every 5th contour for quick rendering
    pts = np.array(c["coordinates"])
    plt.plot(pts[:, 0], pts[:, 1], color="teal", linewidth=0.7, alpha=0.8)

plt.title(f"Step 1: Parsed Contours ({len(contours):,} Lines)", fontsize=12)
plt.xlabel("Longitude (°E)")
plt.ylabel("Latitude (°N)")
plt.grid(True, linestyle="--", alpha=0.5)
plt.show()

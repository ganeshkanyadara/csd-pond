import json
import os
import numpy as np
from scipy.interpolate import griddata
import matplotlib.pyplot as plt

# --------------------------------------------------
# 1. Configuration & Input / Output Paths
# --------------------------------------------------
INPUT_FILE = "outputs/projected_contours.json"
OUTPUT_FILE = "outputs/dem.npz"
RESOLUTION = 1 # 1.0 meter grid spacing

os.makedirs("outputs", exist_ok=True)

# --------------------------------------------------
# 2. Load Projected Contours & Extract Point Cloud
# --------------------------------------------------
print(f"Loading projected contours from {INPUT_FILE}...")
with open(INPUT_FILE, "r") as f:
    data = json.load(f)

contours = data["contours"]

x_coords = []
y_coords = []
z_elevations = []

for contour in contours:
    elevation = contour["elevation"]
    for x, y in contour["coordinates"]:
        x_coords.append(x)
        y_coords.append(y)
        z_elevations.append(elevation)

x_coords = np.array(x_coords, dtype=np.float64)
y_coords = np.array(y_coords, dtype=np.float64)
z_elevations = np.array(z_elevations, dtype=np.float64)

print(f"Total contour sample points: {len(x_coords):,}")
print(f"Elevation range in contours: {z_elevations.min():.1f} m to {z_elevations.max():.1f} m")

# --------------------------------------------------
# 3. Create Regular 2D Metric Grid
# --------------------------------------------------
min_x, max_x = x_coords.min(), x_coords.max()
min_y, max_y = y_coords.min(), y_coords.max()

grid_x_1d = np.arange(min_x, max_x + RESOLUTION, RESOLUTION)
grid_y_1d = np.arange(min_y, max_y + RESOLUTION, RESOLUTION)

grid_x, grid_y = np.meshgrid(grid_x_1d, grid_y_1d)
print(f"Grid dimensions: {grid_x.shape[0]:,} rows x {grid_x.shape[1]:,} cols ({grid_x.size:,} total cells)")

# --------------------------------------------------
# 4. 2D Surface Interpolation (TIN / Delaunay)
# --------------------------------------------------
print("Interpolating continuous 2D surface (Linear TIN)...")
points = np.column_stack((x_coords, y_coords))
dem = griddata(points, z_elevations, (grid_x, grid_y), method="linear")

# Fill boundary extrapolation gaps (convex hull edges) with nearest neighbor
nan_mask = np.isnan(dem)
if np.any(nan_mask):
    print(f"Filling {np.count_nonzero(nan_mask):,} boundary cells with nearest-neighbor values...")
    dem_nearest = griddata(points, z_elevations, (grid_x[nan_mask], grid_y[nan_mask]), method="nearest")
    dem[nan_mask] = dem_nearest

print(f"DEM interpolation complete.")
print(f"DEM Elevation Stats: Min = {dem.min():.2f} m | Max = {dem.max():.2f} m | Mean = {dem.mean():.2f} m")

# --------------------------------------------------
# 5. Save Compressed DEM Array
# --------------------------------------------------
np.savez_compressed(
    OUTPUT_FILE,
    dem=dem,
    grid_x=grid_x,
    grid_y=grid_y,
    resolution=RESOLUTION
)

print(f"Saved DEM to: {OUTPUT_FILE} ({os.path.getsize(OUTPUT_FILE) / 1024 / 1024:.2f} MB)")

# --------------------------------------------------
# 6. Preview & Visualization
# --------------------------------------------------
plt.figure(figsize=(10, 7))
im = plt.imshow(
    dem,
    origin="lower",
    extent=[min_x, max_x, min_y, max_y],
    cmap="terrain"
)
cbar = plt.colorbar(im, label="Elevation (meters)")
plt.title(f"Step 3: 2D Digital Elevation Model (DEM) Grid\nShape: {dem.shape} | Resolution: {RESOLUTION} m", fontsize=12)
plt.xlabel("UTM Easting (meters)")
plt.ylabel("UTM Northing (meters)")
plt.grid(True, linestyle="--", alpha=0.3)
plt.show()

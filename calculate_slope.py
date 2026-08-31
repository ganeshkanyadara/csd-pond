import os
import numpy as np
import matplotlib.pyplot as plt

# --------------------------------------------------
# 1. Configuration & Input / Output Paths
# --------------------------------------------------
INPUT_FILE = "outputs/dem.npz"
OUTPUT_FILE = "outputs/terrain_analysis.npz"

if not os.path.exists(INPUT_FILE):
    raise FileNotFoundError(f"Cannot find {INPUT_FILE}. Please run Step 3 (build_dem.py) first.")

# --------------------------------------------------
# 2. Load DEM Grid
# --------------------------------------------------
print(f"Loading DEM from {INPUT_FILE}...")
data = np.load(INPUT_FILE)
dem = data["dem"]
grid_x = data["grid_x"]
grid_y = data["grid_y"]
resolution = float(data["resolution"])

rows, cols = dem.shape
print(f"Grid Dimensions: {rows:,} rows x {cols:,} cols ({dem.size:,} cells at {resolution}m resolution)")

# --------------------------------------------------
# 3. Horn's 8-Neighbor Weighted Algorithm (Vectorized)
# --------------------------------------------------
print("Calculating terrain slope using Horn's 8-neighbor weighted algorithm (ArcGIS/GDAL standard)...")

# Pad boundaries to handle grid borders seamlessly
padded_dem = np.pad(dem, pad_width=1, mode='edge')

# Extract 3x3 moving window neighbors across the entire matrix simultaneously
# Grid oriented with origin='lower' (row 0 = South, row N = North, col 0 = West, col M = East)
a = padded_dem[:-2, :-2]   # South-West
b = padded_dem[:-2, 1:-1]  # South
c = padded_dem[:-2, 2:]    # South-East
d = padded_dem[1:-1, :-2]  # West
f = padded_dem[1:-1, 2:]   # East
g = padded_dem[2:, :-2]    # North-West
h = padded_dem[2:, 1:-1]   # North
i = padded_dem[2:, 2:]     # North-East

# Compute 8-neighbor weighted gradients (dx and dy)
dz_dx = ((c + 2.0 * f + i) - (a + 2.0 * d + g)) / (8.0 * resolution)
dz_dy = ((g + 2.0 * h + i) - (a + 2.0 * b + c)) / (8.0 * resolution)

# --------------------------------------------------
# 4. Compute Topographic Slope (Degrees & Percent) & Aspect
# --------------------------------------------------
slope_magnitude = np.sqrt(dz_dx**2 + dz_dy**2)
slope_radians = np.arctan(slope_magnitude)
slope_degrees = np.degrees(slope_radians)
slope_percent = np.tan(slope_radians) * 100.0

# Topographic Aspect (Direction slope faces: 0° - 360° from North)
aspect_radians = np.arctan2(dz_dy, -dz_dx)
aspect_degrees = np.degrees(aspect_radians)
aspect_degrees = (90.0 - aspect_degrees) % 360.0  # Convert mathematical angle to compass bearing

print("\n--- Horn's Algorithm Terrain Statistics ---")
print(f"Slope (Degrees) : Min = {slope_degrees.min():.2f}° | Max = {slope_degrees.max():.2f}° | Mean = {slope_degrees.mean():.2f}°")
print(f"Slope (Percent) : Min = {slope_percent.min():.2f}% | Max = {slope_percent.max():.2f}% | Mean = {slope_percent.mean():.2f}%")

# Agricultural Pond Construction Feasibility
flat_cells = np.count_nonzero(slope_degrees <= 3.0)
gentle_cells = np.count_nonzero((slope_degrees > 3.0) & (slope_degrees <= 8.0))
steep_cells = np.count_nonzero(slope_degrees > 8.0)

print(f"\nTerrain Classification (Horn's Model):")
print(f"  • Flat (0° - 3°)    : {flat_cells:,} cells ({flat_cells / dem.size * 100:.1f}%) -> Optimal for Pond Basins")
print(f"  • Gentle (3° - 8°)  : {gentle_cells:,} cells ({gentle_cells / dem.size * 100:.1f}%) -> Ideal Catchment Slopes")
print(f"  • Steep (> 8°)      : {steep_cells:,} cells ({steep_cells / dem.size * 100:.1f}%) -> High Runoff / Unsuitable for Pond Basin")

# --------------------------------------------------
# 5. Save Terrain Analysis Output
# --------------------------------------------------
np.savez_compressed(
    OUTPUT_FILE,
    dem=dem,
    slope_degrees=slope_degrees,
    slope_percent=slope_percent,
    aspect_degrees=aspect_degrees,
    gradient_x=dz_dx,
    gradient_y=dz_dy,
    grid_x=grid_x,
    grid_y=grid_y,
    resolution=resolution,
    method="Horn_8_Neighbor"
)

print(f"\nSaved terrain analysis to: {OUTPUT_FILE} ({os.path.getsize(OUTPUT_FILE) / 1024 / 1024:.2f} MB)")

# --------------------------------------------------
# 6. Preview & Visualization
# --------------------------------------------------
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))

min_x, max_x = grid_x.min(), grid_x.max()
min_y, max_y = grid_y.min(), grid_y.max()
extent = [min_x, max_x, min_y, max_y]

# 1. Slope Map
im1 = ax1.imshow(slope_degrees, origin="lower", extent=extent, cmap="YlOrRd", vmin=0, vmax=15)
cbar1 = plt.colorbar(im1, ax=ax1, fraction=0.046, pad=0.04)
cbar1.set_label("Slope (degrees)")
ax1.set_title(f"Horn's 8-Neighbor Slope Map (Mean: {slope_degrees.mean():.2f}°)", fontweight="bold")
ax1.set_xlabel("UTM Easting (meters)")
ax1.set_ylabel("UTM Northing (meters)")
ax1.grid(True, linestyle="--", alpha=0.3)

# 2. Aspect Map (Compass Orientation)
im2 = ax2.imshow(aspect_degrees, origin="lower", extent=extent, cmap="twilight", vmin=0, vmax=360)
cbar2 = plt.colorbar(im2, ax=ax2, fraction=0.046, pad=0.04)
cbar2.set_label("Aspect (Compass Bearing 0-360°)")
ax2.set_title("Topographic Aspect (Slope Direction)", fontweight="bold")
ax2.set_xlabel("UTM Easting (meters)")
ax2.set_ylabel("UTM Northing (meters)")
ax2.grid(True, linestyle="--", alpha=0.3)

plt.tight_layout()
plt.show()

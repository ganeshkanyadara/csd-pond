import os
import numpy as np
import matplotlib.pyplot as plt

# --------------------------------------------------
# 1. Configuration & Input / Output Paths
# --------------------------------------------------
INPUT_FILE = "outputs/terrain_analysis.npz"
OUTPUT_FILE = "outputs/flow_direction.npz"

if not os.path.exists(INPUT_FILE):
    raise FileNotFoundError(f"Cannot find {INPUT_FILE}. Please run calculate_slope.py first.")

# --------------------------------------------------
# 2. Load Elevation Grid
# --------------------------------------------------
print(f"Loading terrain data from {INPUT_FILE}...")
data = np.load(INPUT_FILE)
dem = data["dem"]
resolution = float(data["resolution"])
grid_x = data["grid_x"]
grid_y = data["grid_y"]
rows, cols = dem.shape

print(f"DEM Dimensions: {rows:,} rows x {cols:,} cols ({dem.size:,} total cells)")

# --------------------------------------------------
# 3. Define 8 Direction Vectors & Physical Distances
# --------------------------------------------------
# 8 Offsets: [NW, N, NE, W, E, SW, S, SE]
DIRECTIONS = [
    (-1, -1), (-1,  0), (-1,  1),  # Row - 1 (North in matrix index)
    ( 0, -1),           ( 0,  1),  # Row 0
    ( 1, -1), ( 1,  0), ( 1,  1)   # Row + 1 (South in matrix index)
]

DISTANCES = [
    resolution * np.sqrt(2), resolution, resolution * np.sqrt(2),
    resolution,                          resolution,
    resolution * np.sqrt(2), resolution, resolution * np.sqrt(2)
]

DIRECTION_NAMES = ["NW (0)", "N (1)", "NE (2)", "W (3)", "E (4)", "SW (5)", "S (6)", "SE (7)"]

# --------------------------------------------------
# 4. Vectorized D8 Steepest Downhill Direction Algorithm
# --------------------------------------------------
print("Calculating D8 flow direction across 8.5 million cells...")

flow_direction = np.full((rows, cols), -1, dtype=np.int8)
max_slope = np.zeros((rows, cols), dtype=np.float64)

for dir_idx, ((dr, dc), dist) in enumerate(zip(DIRECTIONS, DISTANCES)):
    # Shift DEM matrix to align neighbor cell values
    nbr = np.full_like(dem, np.nan)
    
    r_src_start = max(0, dr)
    r_src_end = rows + min(0, dr)
    r_dst_start = max(0, -dr)
    r_dst_end = rows + min(0, -dr)
    
    c_src_start = max(0, dc)
    c_src_end = cols + min(0, dc)
    c_dst_start = max(0, -dc)
    c_dst_end = cols + min(0, -dc)
    
    nbr[r_dst_start:r_dst_end, c_dst_start:c_dst_end] = dem[r_src_start:r_src_end, c_src_start:c_src_end]
    
    # Calculate downhill slope gradient (Drop / Distance)
    slope = (dem - nbr) / dist
    
    # Identify cells where this neighbor provides a steeper downhill descent
    steeper = slope > max_slope
    max_slope[steeper] = slope[steeper]
    flow_direction[steeper] = dir_idx

# --------------------------------------------------
# 5. Summary Statistics
# --------------------------------------------------
print("\n--- D8 Flow Direction Summary ---")
for idx, name in enumerate(DIRECTION_NAMES):
    count = np.count_nonzero(flow_direction == idx)
    print(f"  • Direction {name:6s}: {count:9,} cells ({count / dem.size * 100:5.2f}%)")

sinks = np.count_nonzero(flow_direction == -1)
print(f"  • Sinks / Outlets (-1) : {sinks:9,} cells ({sinks / dem.size * 100:5.2f}%)")

# --------------------------------------------------
# 6. Save Flow Direction Output
# --------------------------------------------------
np.savez_compressed(
    OUTPUT_FILE,
    dem=dem,
    flow_direction=flow_direction,
    resolution=resolution,
    grid_x=grid_x,
    grid_y=grid_y
)

print(f"\nSaved flow direction grid to: {OUTPUT_FILE} ({os.path.getsize(OUTPUT_FILE) / 1024 / 1024:.2f} MB)")

# --------------------------------------------------
# 7. Preview & Visualization
# --------------------------------------------------
plt.figure(figsize=(10, 7))
min_x, max_x = grid_x.min(), grid_x.max()
min_y, max_y = grid_y.min(), grid_y.max()

im = plt.imshow(
    flow_direction,
    origin="lower",
    extent=[min_x, max_x, min_y, max_y],
    cmap="tab10"
)
cbar = plt.colorbar(im, label="D8 Direction Code")
cbar.set_ticks(range(-1, 8))
cbar.set_ticklabels(["Sink (-1)", "NW (0)", "N (1)", "NE (2)", "W (3)", "E (4)", "SW (5)", "S (6)", "SE (7)"])

plt.title("Step 5: D8 Flow Direction Map", fontsize=12, fontweight="bold")
plt.xlabel("UTM Easting (meters)")
plt.ylabel("UTM Northing (meters)")
plt.grid(True, linestyle="--", alpha=0.3)
plt.show()

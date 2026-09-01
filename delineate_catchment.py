import os
import json
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LightSource

# --------------------------------------------------
# 1. Configuration & Input / Output Paths
# --------------------------------------------------
FLOW_FILE = "outputs/flow_direction.npz"
POND_FILE = "outputs/top_5_pond_candidates.json"
OUTPUT_PRIMARY = "outputs/catchment.npz"
OUTPUT_ALL = "outputs/top_5_catchments.npz"
OUTPUT_IMAGE = "outputs/catchment_basins_visualization.png"

if not os.path.exists(FLOW_FILE):
    raise FileNotFoundError(f"Cannot find {FLOW_FILE}. Please run calculate_flow_direction.py first.")
if not os.path.exists(POND_FILE):
    raise FileNotFoundError(f"Cannot find {POND_FILE}. Please run find_and_visualize_5_ponds.py first.")

# --------------------------------------------------
# 2. Load Flow Direction and Top Ponds
# --------------------------------------------------
print(f"Loading hydrological data...")
data = np.load(FLOW_FILE)
dem = data["dem"]
flow_direction = data["flow_direction"]
resolution = float(data["resolution"])
grid_x = data["grid_x"]
grid_y = data["grid_y"]
rows, cols = dem.shape

with open(POND_FILE, "r") as f:
    top_ponds = json.load(f)["top_5_ponds"]

# 8 Direction Offsets: NW, N, NE, W, E, SW, S, SE
DIRECTIONS = [
    (-1, -1), (-1,  0), (-1,  1),
    ( 0, -1),           ( 0,  1),
    ( 1, -1), ( 1,  0), ( 1,  1)
]

# --------------------------------------------------
# 3. Build Reverse Flow Adjacency Graph
# --------------------------------------------------
print("Building reverse upstream flow graph...")
upstream = {}

for r in range(rows):
    for c in range(cols):
        d = flow_direction[r, c]
        if d != -1:
            dr, dc = DIRECTIONS[d]
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                if (nr, nc) not in upstream:
                    upstream[(nr, nc)] = []
                upstream[(nr, nc)].append((r, c))

# --------------------------------------------------
# 4. Function: Delineate Catchment from Pour Point
# --------------------------------------------------
def trace_catchment(pour_r, pour_c):
    """Recursively traces all upstream cells draining to (pour_r, pour_c)."""
    mask = np.zeros((rows, cols), dtype=bool)
    stack = [(pour_r, pour_c)]
    
    while stack:
        curr_r, curr_c = stack.pop()
        if mask[curr_r, curr_c]:
            continue
        mask[curr_r, curr_c] = True
        
        # Add all cells that flow directly into current cell
        for up_r, up_c in upstream.get((curr_r, curr_c), []):
            stack.append((up_r, up_c))
            
    return mask

# --------------------------------------------------
# 5. Delineate Catchments for All 5 Ponds
# --------------------------------------------------
print("\nDelineating catchments for top 5 ponds...")
catchment_masks = []

for p in top_ponds:
    # Find nearest row, col in grid
    dist_sq = (grid_x - p["x_m"])**2 + (grid_y - p["y_m"])**2
    p_r, p_c = np.unravel_index(np.argmin(dist_sq), dist_sq.shape)
    
    c_mask = trace_catchment(p_r, p_c)
    c_area_m2 = np.count_nonzero(c_mask) * (resolution ** 2)
    c_area_ha = c_area_m2 / 10000.0
    
    catchment_masks.append(c_mask)
    
    elev_vals = dem[c_mask]
    print(f"[POND #{p['rank']}] Pour Point: Lat {p['latitude']}, Lon {p['longitude']}")
    print(f"  • Catchment Area : {c_area_m2:,.1f} m² ({c_area_ha:.4f} hectares / {np.count_nonzero(c_mask):,} cells)")
    print(f"  • Elevation Range: {elev_vals.min():.1f}m to {elev_vals.max():.1f}m (Mean: {elev_vals.mean():.1f}m)")

# --------------------------------------------------
# 6. Save Catchment Arrays
# --------------------------------------------------
# Save primary Rank #1 catchment
np.savez_compressed(
    OUTPUT_PRIMARY,
    catchment_mask=catchment_masks[0],
    dem=dem,
    resolution=resolution,
    grid_x=grid_x,
    grid_y=grid_y,
    pond_info=top_ponds[0]
)

# Save all 5 catchments
np.savez_compressed(
    OUTPUT_ALL,
    catchment_masks=np.array(catchment_masks),
    dem=dem,
    resolution=resolution,
    grid_x=grid_x,
    grid_y=grid_y
)

print(f"\nSaved Rank #1 catchment to: {OUTPUT_PRIMARY}")
print(f"Saved all 5 catchments to  : {OUTPUT_ALL}")

# --------------------------------------------------
# 7. Visualization of Delineated Catchment Basins
# --------------------------------------------------
min_x, max_x = grid_x.min(), grid_x.max()
min_y, max_y = grid_y.min(), grid_y.max()
extent = [min_x, max_x, min_y, max_y]

ls = LightSource(azdeg=315, altdeg=45)
hillshade = ls.hillshade(dem, vert_exag=2.0, dx=resolution, dy=resolution)

plt.figure(figsize=(15, 11), facecolor="#0f141d")
ax = plt.gca()
ax.set_facecolor="#0f141d"

# Hillshade base
ax.imshow(hillshade, origin="lower", extent=extent, cmap="bone", alpha=0.55)

# Distinct Colors for Each Catchment Basin
basin_colors = ["#ff4757", "#ffa502", "#2ed573", "#1e90ff", "#a55eea"]

# Overlay each catchment basin mask
for idx, (mask, p) in enumerate(zip(catchment_masks, top_ponds)):
    col = basin_colors[idx]
    masked_basin = np.ma.masked_where(~mask, mask)
    ax.imshow(masked_basin, origin="lower", extent=extent, cmap=plt.cm.colors.ListedColormap([col]), alpha=0.65, interpolation="nearest")
    
    # Plot Pour Point (Pond Site)
    ax.scatter(p["x_m"], p["y_m"], color="white", s=180, edgecolors=col, linewidth=2.5, zorder=6)
    ax.scatter(p["x_m"], p["y_m"], color=col, s=80, zorder=7)
    
    area_ha = (np.count_nonzero(mask) * resolution**2) / 10000.0
    ax.annotate(
        f"Basin #{p['rank']}\n{area_ha:.2f} ha",
        xy=(p["x_m"], p["y_m"]),
        xytext=(p["x_m"] + 30, p["y_m"] + 30),
        fontsize=9,
        fontweight="bold",
        color="white",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="#1e272e", edgecolor=col, alpha=0.9, linewidth=1.5),
        arrowprops=dict(arrowstyle="->", color=col, lw=1.5),
        zorder=8
    )

plt.title("Delineated Rainwater Catchment Basins for Top 5 Ponds", fontsize=15, fontweight="bold", color="white", pad=15)
plt.xlabel("UTM Easting (meters)", color="#d2dae2", fontsize=11)
plt.ylabel("UTM Northing (meters)", color="#d2dae2", fontsize=11)
ax.tick_params(colors="#d2dae2")
ax.grid(True, linestyle=":", color="#34495e", alpha=0.5)

plt.tight_layout()
plt.savefig(OUTPUT_IMAGE, dpi=300, bbox_inches="tight", facecolor="#0f141d")
print(f"Saved catchment visualization map to: {OUTPUT_IMAGE}")
plt.show()

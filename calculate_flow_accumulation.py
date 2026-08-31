import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm

# --------------------------------------------------
# 1. Configuration & Input / Output Paths
# --------------------------------------------------
INPUT_FILE = "outputs/flow_direction.npz"
OUTPUT_FILE = "outputs/flow_accumulation.npz"

if not os.path.exists(INPUT_FILE):
    raise FileNotFoundError(f"Cannot find {INPUT_FILE}. Please run calculate_flow_direction.py first.")

# --------------------------------------------------
# 2. Load Flow Direction & Elevation Grid
# --------------------------------------------------
print(f"Loading flow direction from {INPUT_FILE}...")
data = np.load(INPUT_FILE)
dem = data["dem"]
flow_direction = data["flow_direction"]
resolution = float(data["resolution"])
grid_x = data["grid_x"]
grid_y = data["grid_y"]
rows, cols = dem.shape

print(f"Grid Size: {rows:,} rows x {cols:,} cols ({dem.size:,} cells at {resolution}m resolution)")

# 8 Direction Offsets: NW, N, NE, W, E, SW, S, SE
DIRECTIONS = [
    (-1, -1), (-1,  0), (-1,  1),
    ( 0, -1),           ( 0,  1),
    ( 1, -1), ( 1,  0), ( 1,  1)
]

# --------------------------------------------------
# 3. Compute In-Degrees (Incoming Flow Count per Cell)
# --------------------------------------------------
print("Building hydrological drainage network graph...")
incoming_count = np.zeros((rows, cols), dtype=np.int32)

for r in range(rows):
    for c in range(cols):
        d = flow_direction[r, c]
        if d != -1:
            dr, dc = DIRECTIONS[d]
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                incoming_count[nr, nc] += 1

# --------------------------------------------------
# 4. Topological Queue Routing (O(N) Fast Accumulation)
# --------------------------------------------------
print("Routing flow accumulation across all 8.5 million cells...")
flow_accumulation = np.ones((rows, cols), dtype=np.float64)

# Initialize queue with all headwater ridge cells (cells that receive 0 upstream flow)
queue = [(r, c) for r in range(rows) for c in range(cols) if incoming_count[r, c] == 0]
print(f"Found {len(queue):,} headwater ridge cells to begin routing.")

processed = 0
while queue:
    r, c = queue.pop()
    processed += 1
    
    d = flow_direction[r, c]
    if d != -1:
        dr, dc = DIRECTIONS[d]
        nr, nc = r + dr, c + dc
        if 0 <= nr < rows and 0 <= nc < cols:
            # Pass this cell's accumulated runoff to downstream neighbor
            flow_accumulation[nr, nc] += flow_accumulation[r, c]
            incoming_count[nr, nc] -= 1
            
            # When all upstream feeders for (nr, nc) are processed, add it to queue
            if incoming_count[nr, nc] == 0:
                queue.append((nr, nc))

print(f"Routing complete! Processed {processed:,} cells.")

# --------------------------------------------------
# 5. Summary Statistics
# --------------------------------------------------
max_flow = flow_accumulation.max()
mean_flow = flow_accumulation.mean()

print("\n--- Flow Accumulation Statistics ---")
print(f"Minimum Accumulation : {flow_accumulation.min():.1f} cells (1.0 m² - Ridge peaks)")
print(f"Maximum Accumulation : {max_flow:,.1f} cells ({max_flow * resolution**2:,.1f} m² / {max_flow * resolution**2 / 10000:.2f} hectares)")
print(f"Mean Accumulation    : {mean_flow:.2f} cells")

stream_cells = np.count_nonzero(flow_accumulation >= 1000)
print(f"Cells with >= 1,000m² flow (Stream Network): {stream_cells:,} cells ({stream_cells / dem.size * 100:.2f}%)")

# --------------------------------------------------
# 6. Save Flow Accumulation Output
# --------------------------------------------------
np.savez_compressed(
    OUTPUT_FILE,
    dem=dem,
    flow_direction=flow_direction,
    flow_accumulation=flow_accumulation,
    resolution=resolution,
    grid_x=grid_x,
    grid_y=grid_y
)

print(f"\nSaved flow accumulation grid to: {OUTPUT_FILE} ({os.path.getsize(OUTPUT_FILE) / 1024 / 1024:.2f} MB)")

# --------------------------------------------------
# 7. Preview & Visualization (Logarithmic Scale)
# --------------------------------------------------
plt.figure(figsize=(11, 8))
min_x, max_x = grid_x.min(), grid_x.max()
min_y, max_y = grid_y.min(), grid_y.max()

# Using LogNorm so both small gullies and main streams are brightly visible
im = plt.imshow(
    flow_accumulation,
    origin="lower",
    extent=[min_x, max_x, min_y, max_y],
    cmap="viridis",
    norm=LogNorm(vmin=1.0, vmax=max_flow)
)
cbar = plt.colorbar(im, label="Upstream Accumulated Cells (m² of Catchment)")
plt.title(f"Step 6: Flow Accumulation Drainage Network (Max: {max_flow:,.0f} m²)", fontsize=12, fontweight="bold")
plt.xlabel("UTM Easting (meters)")
plt.ylabel("UTM Northing (meters)")
plt.grid(True, linestyle="--", alpha=0.3)
plt.show()

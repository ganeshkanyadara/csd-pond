import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches

fig, ax = plt.subplots(figsize=(13, 8), dpi=300)
ax.set_xlim(0, 100)
ax.set_ylim(0, 100)
ax.axis('off')

# Color palette
c_layer_bg = "#f8fafc"
c_layer_border = "#94a3b8"
c_box_bg = "#ffffff"
c_client = "#0284c7"
c_api = "#4f46e5"
c_core = "#0d9488"
c_data = "#b45309"
c_text_dark = "#0f172a"
c_text_muted = "#475569"

def draw_layer(y, height, title, color):
    rect = patches.FancyBboxPatch((3, y), 94, height, boxstyle="round,pad=1,rounding_size=2.5",
                                 facecolor=c_layer_bg, edgecolor=c_layer_border, linewidth=1.2)
    ax.add_patch(rect)
    # Title badge
    ax.text(5.5, y + height - 2.2, title.upper(), fontsize=10.5, fontweight='bold', color=color,
            family='sans-serif', va='center')

def draw_box(x, y, w, h, title, subtitle, color, border_color=None):
    if border_color is None:
        border_color = color
    box = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.6,rounding_size=1.5",
                                facecolor=c_box_bg, edgecolor=border_color, linewidth=1.5)
    ax.add_patch(box)
    ax.text(x + w/2, y + h*0.62, title, fontsize=9.5, fontweight='bold', color=c_text_dark,
            ha='center', va='center', family='sans-serif')
    ax.text(x + w/2, y + h*0.28, subtitle, fontsize=7.5, color=c_text_muted,
            ha='center', va='center', family='sans-serif')

def draw_arrow(x1, y1, x2, y2, label=""):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="->,head_width=0.35,head_length=0.45",
                                color="#64748b", lw=1.5))
    if label:
        ax.text((x1 + x2)/2, (y1 + y2)/2, label, fontsize=7.5, fontweight='bold',
                color="#0369a1", ha='center', va='center',
                bbox=dict(boxstyle="round,pad=0.2", facecolor="#ffffff", edgecolor="#cbd5e1", lw=0.8))

# Main Title
ax.text(50, 98, "AI-based Village Pond Planning System — End-to-End Architectural Design",
        fontsize=13, fontweight='bold', color=c_text_dark, ha='center', family='sans-serif')

# Layer 1: Client & Presentation Layer (y: 77 to 95)
draw_layer(77, 18.5, "1. Interactive Presentation Layer (Web GIS & Map UI)", c_client)
draw_box(6, 79, 27, 11, "Leaflet.js Map Engine", "Esri Satellite / OSM Base Layers", c_client)
draw_box(36.5, 79, 27, 11, "Land Area Selection Tool", "Interactive Canvas BBox Drawing", c_client)
draw_box(67, 79, 27, 11, "Hydrology HUD & Results", "Real-time Capacity & Runoff Gauges", c_client)

# Downward Arrow 1
draw_arrow(50, 77, 50, 71, "HTTP / REST (GeoJSON, KML Multipart, BBox Query)")

# Layer 2: API & Gateway Layer (y: 54 to 71)
draw_layer(54, 17, "2. Application & API Gateway Layer (FastAPI / ASGI on Port 3000)", c_api)
draw_box(6, 56, 20.5, 10, "FastAPI Application", "Port 3000 / Uvicorn ASGI", c_api)
draw_box(29, 56, 20.5, 10, "Route /analyzeContour", "KML/KMZ Multipart Ingestion", c_api)
draw_box(52, 56, 20.5, 10, "Route /api/analyzeSample", "Low-Latency In-Memory Analysis", c_api)
draw_box(75, 56, 19, 10, "Pydantic Schemas", "Strict Validation & Type Safety", c_api)

# Downward Arrow 2
draw_arrow(50, 54, 50, 48, "Memory-Efficient Pipeline Dispatch (Resolution >= 5.0m)")

# Layer 3: Geospatial Processing Engine (y: 16 to 48)
draw_layer(16, 32, "3. Geospatial Terrain & Hydrological Core Engine", c_core)
# Row 1 of Core (y: 33 to 42)
draw_box(6, 33.5, 20.5, 9, "KML/KMZ Parser", "XML Placemark & Z Extractor", c_core)
draw_box(29, 33.5, 20.5, 9, "UTM Projection", "Auto EPSG:32644 (PyProj)", c_core)
draw_box(52, 33.5, 20.5, 9, "DEM Interpolation", "SciPy GridData 2D Mesh", c_core)
draw_box(75, 33.5, 19, 9, "Horn's Slope & Aspect", "8-Neighbor Gradient Filtering", c_core)

# Internal pipeline arrows
draw_arrow(26.5, 38, 29, 38)
draw_arrow(49.5, 38, 52, 38)
draw_arrow(72.5, 38, 75, 38)

# Row 2 of Core (y: 18 to 27)
draw_box(6, 18.5, 20.5, 9, "D8 Flow Accumulation", "Downhill Routing & Sink Fill", c_core)
draw_box(29, 18.5, 20.5, 9, "AHP Site Selection", "Flow 60% + Slope 30% + NMS", c_core)
draw_box(52, 18.5, 20.5, 9, "Catchment Tracing", "Zero-Memory Backtracking Stack", c_core)
draw_box(75, 18.5, 19, 9, "Hydrology & GeoJSON", "Runoff Yield & RFC 7946 Vector", c_core)

# Internal pipeline arrows row 2
draw_arrow(26.5, 23, 29, 23)
draw_arrow(49.5, 23, 52, 23)
draw_arrow(72.5, 23, 75, 23)

# Downward Arrow 3
draw_arrow(50, 16, 50, 12, "Garbage Collection & OOM Protection")

# Layer 4: Infrastructure & Constraints Layer (y: 1 to 14)
draw_layer(1, 14, "4. Infrastructure, Resource Governance & Data Storage", c_data)
draw_box(6, 2.5, 27, 8, "512 MB cgroup Memory Limit", "Strict Allocation Cap / gc.collect()", c_data)
draw_box(36.5, 2.5, 27, 8, "Docker NAT Port Forwarding", "Container Port 3000 -> Host 3213", c_data)
draw_box(67, 2.5, 27, 8, "RFC 7946 GeoJSON Output", "Multi-layer FeatureCollection", c_data)

plt.tight_layout()
plt.savefig("architecture-diagram.png", dpi=300, bbox_inches='tight')
print("Successfully generated updated architecture-diagram.png")

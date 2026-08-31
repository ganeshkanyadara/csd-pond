import os
import json
import numpy as np
from shapely.geometry import box
from shapely.ops import unary_union
from pyproj import Transformer

# --------------------------------------------------
# 1. Configuration & Input / Output Paths
# --------------------------------------------------
CATCH_FILE = "outputs/catchment.npz"
PROJ_FILE = "outputs/projected_contours.json"
OUTPUT_GEOJSON = "outputs/catchment.geojson"

if not os.path.exists(CATCH_FILE):
    raise FileNotFoundError(f"Cannot find {CATCH_FILE}. Please run delineate_catchment.py first.")

print("Loading catchment raster data...")
data = np.load(CATCH_FILE, allow_pickle=True)
catchment_mask = data["catchment_mask"]
grid_x = data["grid_x"]
grid_y = data["grid_y"]
resolution = float(data["resolution"])
pond = data["pond_info"].item() if hasattr(data["pond_info"], "item") else data["pond_info"]

with open(PROJ_FILE, "r") as f:
    proj_meta = json.load(f)["coordinate_system"]

epsg = proj_meta["target"]
print(f"Reprojecting from {epsg} back to universal WGS84 (EPSG:4326)...")
transformer = Transformer.from_crs(epsg, "EPSG:4326", always_xy=True)

# --------------------------------------------------
# 2. Vectorize Raster Mask to Smooth Polygons
# --------------------------------------------------
print("Vectorizing raster catchment cells into polygon boundary...")
c_rows, c_cols = np.where(catchment_mask)
half = resolution / 2.0
cell_boxes = [
    box(grid_x[r, c] - half, grid_y[r, c] - half, grid_x[r, c] + half, grid_y[r, c] + half)
    for r, c in zip(c_rows, c_cols)
]
poly_utm = unary_union(cell_boxes).buffer(0)

# Function to transform polygon coordinates to WGS84 (Lon, Lat)
def to_wgs84(geom):
    if geom.geom_type == "Polygon":
        ext = [list(transformer.transform(x, y)) for x, y in geom.exterior.coords]
        holes = [[list(transformer.transform(x, y)) for x, y in h.coords] for h in geom.interiors]
        return {"type": "Polygon", "coordinates": [ext, *holes]}
    elif geom.geom_type == "MultiPolygon":
        return {"type": "MultiPolygon", "coordinates": [to_wgs84(g)["coordinates"] for g in geom.geoms]}

poly_wgs84 = to_wgs84(poly_utm)

# --------------------------------------------------
# 3. Create Standard GeoJSON Document
# --------------------------------------------------
area_m2 = float(poly_utm.area)
area_ha = area_m2 / 10000.0
area_acres = area_m2 * 0.000247105

geojson_doc = {
    "type": "FeatureCollection",
    "name": "Farm_Pond_Catchment_Delineation",
    "crs": {
        "type": "name",
        "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}
    },
    "features": [
        # Feature 1: Catchment Basin Polygon
        {
            "type": "Feature",
            "properties": {
                "feature_type": "catchment_basin",
                "area_m2": round(area_m2, 2),
                "area_hectares": round(area_ha, 4),
                "area_acres": round(area_acres, 2),
                "description": "Rainwater catchment watershed contributing runoff to the pond"
            },
            "geometry": poly_wgs84
        },
        # Feature 2: Pond Outlet Point
        {
            "type": "Feature",
            "properties": {
                "feature_type": "farm_pond_site",
                "latitude": pond["latitude"],
                "longitude": pond["longitude"],
                "elevation_m": pond["elevation_m"],
                "slope_deg": pond["slope_deg"],
                "google_maps_url": pond["google_maps_url"]
            },
            "geometry": {
                "type": "Point",
                "coordinates": [pond["longitude"], pond["latitude"]]
            }
        }
    ]
}

# --------------------------------------------------
# 4. Save GeoJSON File
# --------------------------------------------------
with open(OUTPUT_GEOJSON, "w") as f:
    json.dump(geojson_doc, f, indent=2)

print("\n=========================================================================")
print(" GEOJSON EXPORT COMPLETE")
print("=========================================================================")
print(f"File Saved      : {OUTPUT_GEOJSON}")
print(f"Catchment Area  : {area_m2:,.1f} m² ({area_ha:.4f} hectares / {area_acres:.2f} acres)")
print(f"Pond Location   : Lat {pond['latitude']}, Lon {pond['longitude']}")
print(f"Google Maps Link: {pond['google_maps_url']}")
print("=========================================================================")

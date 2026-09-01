import io
import json
import logging
import math
import os
import time
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Tuple, Optional

import numpy as np
from pyproj import Transformer
from scipy.interpolate import griddata
from shapely.geometry import box
from shapely.ops import unary_union

logger = logging.getLogger("csd-pond")

# --------------------------------------------------
# 1. KML / KMZ Parsing (from parser.py)
# --------------------------------------------------
NAMESPACE = {
    "kml": "http://www.opengis.net/kml/2.2"
}

def parse_kml_or_kmz(file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
    """
    Parses a KML or KMZ byte stream and extracts all contour lines with elevations.
    Handles KMZ zip archives, KML XML namespaces, and varied attribute schemas.
    """
    kml_content = file_bytes

    # Handle KMZ compressed zip archive
    if filename.lower().endswith(".kmz") or (len(file_bytes) > 4 and file_bytes[:4] == b"PK\x03\x04"):
        with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as z:
            kml_files = [f for f in z.namelist() if f.lower().endswith(".kml")]
            if not kml_files:
                raise ValueError("KMZ archive does not contain any .kml file.")
            # Prefer doc.kml if present, else first .kml
            target_kml = "doc.kml" if "doc.kml" in kml_files else kml_files[0]
            kml_content = z.read(target_kml)

    # Parse XML Tree
    root = ET.fromstring(kml_content)

    # Try namespace search first, fallback to wildcard tag search
    placemarks = root.findall(".//kml:Placemark", NAMESPACE)
    if not placemarks:
        placemarks = root.findall(".//{*}Placemark")

    contours = []
    auto_id = 0

    for placemark in placemarks:
        # Extract Contour ID (from SimpleData or fallback)
        id_element = placemark.find(".//kml:SimpleData[@name='ID']", NAMESPACE)
        if id_element is None:
            id_element = placemark.find(".//{*}SimpleData[@name='ID']")
        
        contour_id = int(id_element.text) if (id_element is not None and id_element.text is not None and id_element.text.isdigit()) else auto_id
        auto_id += 1

        # Extract Elevation
        elevation: Optional[float] = None
        name = placemark.find("kml:name", NAMESPACE)
        if name is None:
            name = placemark.find("{*}name")
        
        if name is not None and name.text:
            try:
                elevation = float(name.text.strip())
            except ValueError:
                # Try extracting numbers from string e.g. "277 m"
                import re
                m = re.search(r"[-+]?\d*\.?\d+", name.text)
                if m:
                    elevation = float(m.group(0))

        # Check ExtendedData for elevation attributes if not found in name
        if elevation is None:
            for attr_name in ["ELEVATION", "Elevation", "ELEV", "elev", "Z", "z", "CONTOUR", "Contour"]:
                sd = placemark.find(f".//kml:SimpleData[@name='{attr_name}']", NAMESPACE)
                if sd is None:
                    sd = placemark.find(f".//{{*}}SimpleData[@name='{attr_name}']")
                if sd is not None and sd.text:
                    try:
                        elevation = float(sd.text.strip())
                        break
                    except ValueError:
                        pass

        # Extract Coordinates from LineString or Geometry
        coordinates_element = placemark.find(".//kml:coordinates", NAMESPACE)
        if coordinates_element is None:
            coordinates_element = placemark.find(".//{*}coordinates")
        
        if coordinates_element is None or not coordinates_element.text:
            continue

        coordinates_text = coordinates_element.text.strip()
        points = []

        for point in coordinates_text.split():
            parts = point.split(",")
            if len(parts) >= 2:
                lon, lat = float(parts[0]), float(parts[1])
                if elevation is None and len(parts) >= 3:
                    try:
                        elevation = float(parts[2])
                    except ValueError:
                        pass
                points.append([lon, lat])

        if points:
            contours.append({
                "id": contour_id,
                "elevation": elevation if elevation is not None else 0.0,
                "coordinates": points
            })

    if not contours:
        raise ValueError("No valid contour lines found in the uploaded KML/KMZ file.")

    return contours


# --------------------------------------------------
# 2. Coordinate System & UTM Projection (from projection.py)
# --------------------------------------------------
def project_contours(contours: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Transformer, Transformer]:
    """
    Computes centroid, automatically detects UTM zone, and projects coordinates to metric UTM (meters).
    """
    all_points = []
    for contour in contours:
        for lon, lat in contour["coordinates"]:
            all_points.append((lon, lat))

    if not all_points:
        raise ValueError("No coordinates found in contours.")

    mean_lon = sum(lon for lon, lat in all_points) / len(all_points)
    mean_lat = sum(lat for lon, lat in all_points) / len(all_points)

    min_lon = min(lon for lon, lat in all_points)
    max_lon = max(lon for lon, lat in all_points)
    min_lat = min(lat for lon, lat in all_points)
    max_lat = max(lat for lon, lat in all_points)

    # Automatic UTM Zone calculation (from projection.py)
    utm_zone = math.floor((mean_lon + 180) / 6) + 1
    hemisphere = "north" if mean_lat >= 0 else "south"
    epsg = (32600 if hemisphere == "north" else 32700) + utm_zone

    transformer = Transformer.from_crs(
        "EPSG:4326",       # Source: WGS84 degrees
        f"EPSG:{epsg}",    # Target: Metric UTM
        always_xy=True
    )
    
    transformer_inv = Transformer.from_crs(
        f"EPSG:{epsg}",
        "EPSG:4326",
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

    coord_meta = {
        "source": "EPSG:4326",
        "target": f"EPSG:{epsg}",
        "projection": "UTM",
        "utm_zone": utm_zone,
        "hemisphere": hemisphere,
        "units": "meters",
        "center_lon": round(mean_lon, 6),
        "center_lat": round(mean_lat, 6),
        "bbox_wgs84": {
            "min_lon": round(min_lon, 6),
            "min_lat": round(min_lat, 6),
            "max_lon": round(max_lon, 6),
            "max_lat": round(max_lat, 6)
        }
    }

    return projected_contours, coord_meta, transformer, transformer_inv


from scipy.interpolate import LinearNDInterpolator
from scipy.spatial import cKDTree

def build_dem(projected_contours: List[Dict[str, Any]], resolution: float = 1.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    """
    Interpolates continuous 2D Digital Elevation Model (DEM) from projected metric contour point cloud.
    Uses memory-efficient single-pass Linear Delaunay interpolation with fast cKDTree boundary fill.
    """
    x_coords = []
    y_coords = []
    z_elevations = []

    for contour in projected_contours:
        elevation = contour["elevation"]
        for x, y in contour["coordinates"]:
            x_coords.append(x)
            y_coords.append(y)
            z_elevations.append(elevation)

    x_coords = np.array(x_coords, dtype=np.float64)
    y_coords = np.array(y_coords, dtype=np.float64)
    z_elevations = np.array(z_elevations, dtype=np.float64)

    min_x, max_x = x_coords.min(), x_coords.max()
    min_y, max_y = y_coords.min(), y_coords.max()

    grid_x_1d = np.arange(min_x, max_x + resolution, resolution)
    grid_y_1d = np.arange(min_y, max_y + resolution, resolution)

    grid_x, grid_y = np.meshgrid(grid_x_1d, grid_y_1d)

    points = np.column_stack((x_coords, y_coords))
    
    # Fast single-pass Linear Delaunay interpolation
    lin_interp = LinearNDInterpolator(points, z_elevations)
    dem = lin_interp(grid_x, grid_y)

    # Fill boundary extrapolation gaps (convex hull edges) with fast cKDTree nearest-neighbor
    nan_mask = np.isnan(dem)
    if np.any(nan_mask):
        tree = cKDTree(points)
        nan_pts = np.column_stack((grid_x[nan_mask], grid_y[nan_mask]))
        _, idxs = tree.query(nan_pts, k=1, workers=-1)
        dem[nan_mask] = z_elevations[idxs]

    return dem, grid_x, grid_y, resolution


# --------------------------------------------------
# 4. Horn's 8-Neighbor Slope & Aspect (from calculate_slope.py)
# --------------------------------------------------
def calculate_slope(dem: np.ndarray, resolution: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Calculates topographic slope and aspect using Horn's 8-neighbor weighted algorithm.
    """
    padded_dem = np.pad(dem, pad_width=1, mode='edge')

    # 3x3 moving window neighbors
    a = padded_dem[:-2, :-2]   # South-West
    b = padded_dem[:-2, 1:-1]  # South
    c = padded_dem[:-2, 2:]    # South-East
    d = padded_dem[1:-1, :-2]  # West
    f = padded_dem[1:-1, 2:]   # East
    g = padded_dem[2:, :-2]    # North-West
    h = padded_dem[2:, 1:-1]   # North
    i = padded_dem[2:, 2:]     # North-East

    # Horn's 8-neighbor weighted gradients
    dz_dx = ((c + 2.0 * f + i) - (a + 2.0 * d + g)) / (8.0 * resolution)
    dz_dy = ((g + 2.0 * h + i) - (a + 2.0 * b + c)) / (8.0 * resolution)

    slope_magnitude = np.sqrt(dz_dx**2 + dz_dy**2)
    slope_radians = np.arctan(slope_magnitude)
    slope_degrees = np.degrees(slope_radians)
    slope_percent = np.tan(slope_radians) * 100.0

    aspect_radians = np.arctan2(dz_dy, -dz_dx)
    aspect_degrees = (90.0 - np.degrees(aspect_radians)) % 360.0

    return slope_degrees, slope_percent, aspect_degrees


# --------------------------------------------------
# 5. D8 Steepest Downhill Flow Direction (from calculate_flow_direction.py)
# --------------------------------------------------
DIRECTIONS = [
    (-1, -1), (-1,  0), (-1,  1),  # Row - 1 (North in matrix index)
    ( 0, -1),           ( 0,  1),  # Row 0
    ( 1, -1), ( 1,  0), ( 1,  1)   # Row + 1 (South in matrix index)
]

def calculate_flow_direction(dem: np.ndarray, resolution: float) -> np.ndarray:
    """
    Vectorized D8 Steepest Downhill Direction Algorithm.
    """
    rows, cols = dem.shape
    distances = [
        resolution * np.sqrt(2), resolution, resolution * np.sqrt(2),
        resolution,                          resolution,
        resolution * np.sqrt(2), resolution, resolution * np.sqrt(2)
    ]

    flow_direction = np.full((rows, cols), -1, dtype=np.int8)
    max_slope = np.zeros((rows, cols), dtype=np.float64)

    for dir_idx, ((dr, dc), dist) in enumerate(zip(DIRECTIONS, distances)):
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

        slope = (dem - nbr) / dist
        steeper = slope > max_slope
        max_slope[steeper] = slope[steeper]
        flow_direction[steeper] = dir_idx

    return flow_direction


# --------------------------------------------------
# 6. Topological Queue Flow Accumulation & Downstream Graph
# --------------------------------------------------
def calculate_flow_accumulation(dem: np.ndarray, flow_direction: np.ndarray, resolution: float) -> Tuple[np.ndarray, np.ndarray]:
    """
    Computes upstream accumulated flow runoff using O(N) topological queue routing.
    Also returns the 1D downstream adjacency array for fast catchment tracing.
    """
    rows, cols = dem.shape
    n_cells = rows * cols

    downstream = np.full(n_cells, -1, dtype=np.int32)
    flat_fd = flow_direction.ravel()
    flat_r, flat_c = np.unravel_index(np.arange(n_cells), (rows, cols))

    for d_idx, (dr, dc) in enumerate(DIRECTIONS):
        mask = (flat_fd == d_idx)
        nr = flat_r[mask] + dr
        nc = flat_c[mask] + dc
        valid = (nr >= 0) & (nr < rows) & (nc >= 0) & (nc < cols)
        target_1d = nr[valid] * cols + nc[valid]
        src_1d = np.where(mask)[0][valid]
        downstream[src_1d] = target_1d

    in_degree = np.zeros(n_cells, dtype=np.int32)
    valid_ds = downstream[downstream >= 0]
    np.add.at(in_degree, valid_ds, 1)

    flow_acc_flat = np.ones(n_cells, dtype=np.float64)

    # Batch-vectorized topological sort: processes all in_degree==0 cells in parallel
    ready = np.where(in_degree == 0)[0]

    while len(ready) > 0:
        targets = downstream[ready]
        valid_mask = targets >= 0

        valid_sources = ready[valid_mask]
        valid_targets = targets[valid_mask]

        np.add.at(flow_acc_flat, valid_targets, flow_acc_flat[valid_sources])
        np.add.at(in_degree, valid_targets, -1)
        in_degree[ready] = -1

        ready = np.where(in_degree == 0)[0]

    return flow_acc_flat.reshape((rows, cols)), downstream


# --------------------------------------------------
# 7. Multi-Criteria Pond Candidate Selection (from viz.ipynb)
# --------------------------------------------------
def find_top_ponds(
    dem: np.ndarray,
    slope_deg: np.ndarray,
    flow_acc: np.ndarray,
    grid_x: np.ndarray,
    grid_y: np.ndarray,
    transformer_inv: Transformer,
    top_n: int = 5,
    min_separation_meters: float = 150.0,
    max_slope_degrees: float = 8.0,
    min_flow_cells: float = 1000.0,
    resolution: float = 1.0
) -> List[Dict[str, Any]]:
    """
    Multi-criteria suitability scoring (AHP) and Spatial Non-Maximum Suppression (NMS)
    for identifying optimal pond candidates.
    """
    rows, cols = dem.shape
    border = max(1, int(50 / resolution))

    valid_mask = np.zeros((rows, cols), dtype=bool)
    if rows > 2 * border and cols > 2 * border:
        valid_mask[border:-border, border:-border] = True
    else:
        valid_mask[:, :] = True

    valid_mask &= (slope_deg <= max_slope_degrees)
    valid_mask &= (flow_acc >= min_flow_cells)

    cand_r, cand_c = np.where(valid_mask)
    if len(cand_r) == 0:
        # Fallback if strict criteria yield 0 cells: relax min_flow
        valid_mask = (slope_deg <= max_slope_degrees)
        cand_r, cand_c = np.where(valid_mask)
        if len(cand_r) == 0:
            cand_r, cand_c = np.where(np.ones_like(dem, dtype=bool))

    c_flow = flow_acc[cand_r, cand_c]
    c_slope = slope_deg[cand_r, cand_c]
    c_elev = dem[cand_r, cand_c]

    def normalize(arr: np.ndarray) -> np.ndarray:
        return (arr - arr.min()) / (arr.max() - arr.min()) if arr.max() > arr.min() else np.zeros_like(arr)

    norm_flow = normalize(c_flow)
    norm_slope = normalize(c_slope)
    norm_elev = normalize(c_elev)

    # AHP Score: 60% Flow + 30% Flat Slope + 10% Low Elevation (from viz.ipynb)
    scores = (0.60 * norm_flow) + (0.30 * (1.0 - norm_slope)) + (0.10 * (1.0 - norm_elev))

    sorted_indices = np.argsort(scores)[::-1]
    selected_ponds = []

    for idx in sorted_indices:
        r, c = cand_r[idx], cand_c[idx]
        x, y = float(grid_x[r, c]), float(grid_y[r, c])

        too_close = False
        for prev in selected_ponds:
            dist = np.sqrt((x - prev["x_m"])**2 + (y - prev["y_m"])**2)
            if dist < min_separation_meters:
                too_close = True
                break

        if not too_close:
            lon, lat = transformer_inv.transform(x, y)
            pond_info = {
                "rank": len(selected_ponds) + 1,
                "latitude": round(float(lat), 6),
                "longitude": round(float(lon), 6),
                "x_m": round(x, 1),
                "y_m": round(y, 1),
                "row": int(r),
                "col": int(c),
                "elevation_m": round(float(dem[r, c]), 2),
                "slope_deg": round(float(slope_deg[r, c]), 2),
                "flow_accumulation_m2": round(float(flow_acc[r, c] * (resolution ** 2)), 1),
                "suitability_score": round(float(scores[idx]), 4),
                "google_maps_url": f"https://www.google.com/maps?q={lat:.6f},{lon:.6f}"
            }
            selected_ponds.append(pond_info)

            if len(selected_ponds) == top_n:
                break

    return selected_ponds


# --------------------------------------------------
# 8. Catchment Delineation & GeoJSON (from delineate_catchment.py & catchment_to_geojson.py)
# --------------------------------------------------
def delineate_catchments_and_geojson(
    dem: np.ndarray,
    downstream: np.ndarray,
    slope_deg: np.ndarray,
    selected_ponds: List[Dict[str, Any]],
    grid_x: np.ndarray,
    grid_y: np.ndarray,
    resolution: float,
    transformer_inv: Transformer
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]:
    """
    Traces upstream catchment from pour point using fast CSR reverse flow graph,
    calculates watershed metrics, and converts the basin boundary into a standard WGS84 GeoJSON.
    """
    rows, cols = dem.shape
    n_cells = rows * cols

    # Fast CSR reverse upstream graph (replaces slow Python dictionary lookups)
    valid_src = np.where(downstream >= 0)[0]
    valid_dst = downstream[valid_src]
    order = np.argsort(valid_dst)
    sorted_dst = valid_dst[order]
    sorted_src = valid_src[order]

    starts = np.searchsorted(sorted_dst, np.arange(n_cells), side='left')
    ends = np.searchsorted(sorted_dst, np.arange(n_cells), side='right')

    def trace_catchment_fast(pour_1d: int) -> np.ndarray:
        visited = np.zeros(n_cells, dtype=bool)
        stack = [pour_1d]
        while stack:
            curr = stack.pop()
            if visited[curr]:
                continue
            visited[curr] = True
            s, e = starts[curr], ends[curr]
            if s < e:
                stack.extend(sorted_src[s:e].tolist())
        return visited.reshape((rows, cols))

    all_catchment_summaries = []
    primary_geojson: Optional[Dict[str, Any]] = None
    primary_catchment_info: Optional[Dict[str, Any]] = None

    for pond in selected_ponds:
        pour_1d = pond["row"] * cols + pond["col"]
        mask = trace_catchment_fast(pour_1d)

        cell_count = int(np.count_nonzero(mask))
        area_m2 = cell_count * (resolution ** 2)
        area_ha = area_m2 / 10000.0
        area_acres = area_m2 * 0.000247105

        elev_vals = dem[mask]
        slope_vals = slope_deg[mask]

        catchment_summary = {
            "pond_rank": pond["rank"],
            "pond_location": {
                "latitude": pond["latitude"],
                "longitude": pond["longitude"],
                "elevation_m": pond["elevation_m"]
            },
            "catchment_area_m2": round(area_m2, 2),
            "catchment_area_hectares": round(area_ha, 4),
            "catchment_area_acres": round(area_acres, 2),
            "catchment_cell_count": cell_count,
            "elevation_min_m": round(float(elev_vals.min()), 2),
            "elevation_max_m": round(float(elev_vals.max()), 2),
            "elevation_mean_m": round(float(elev_vals.mean()), 2),
            "slope_mean_deg": round(float(slope_vals.mean()), 2)
        }
        all_catchment_summaries.append(catchment_summary)

        # For the Rank 1 pond, vectorize to GeoJSON (with fast row-span optimization)
        if pond["rank"] == 1:
            primary_catchment_info = catchment_summary
            c_rows, c_cols = np.where(mask)
            half = resolution / 2.0

            # Merge contiguous horizontal spans in each row into single boxes
            boxes = []
            for r in np.unique(c_rows):
                row_cols = c_cols[c_rows == r]
                diffs = np.diff(row_cols)
                split_pts = np.where(diffs > 1)[0] + 1
                runs = np.split(row_cols, split_pts)
                y_min = grid_y[r, 0] - half
                y_max = grid_y[r, 0] + half
                for run in runs:
                    if len(run) > 0:
                        boxes.append(box(grid_x[0, run[0]] - half, y_min, grid_x[0, run[-1]] + half, y_max))

            poly_utm = unary_union(boxes).buffer(0)

            def to_wgs84(geom):
                if geom.geom_type == "Polygon":
                    ext = [list(transformer_inv.transform(x, y)) for x, y in geom.exterior.coords]
                    holes = [[list(transformer_inv.transform(x, y)) for x, y in h.coords] for h in geom.interiors]
                    return {"type": "Polygon", "coordinates": [ext, *holes]}
                elif geom.geom_type == "MultiPolygon":
                    polys = []
                    for g in geom.geoms:
                        converted = to_wgs84(g)
                        if converted:
                            polys.append(converted["coordinates"])
                    return {"type": "MultiPolygon", "coordinates": polys}
                return None

            poly_wgs84 = to_wgs84(poly_utm)

            primary_geojson = {
                "type": "FeatureCollection",
                "name": "Farm_Pond_Catchment_Delineation",
                "crs": {
                    "type": "name",
                    "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}
                },
                "features": [
                    {
                        "type": "Feature",
                        "properties": {
                            "feature_type": "catchment_basin",
                            "pond_rank": pond["rank"],
                            "area_m2": round(area_m2, 2),
                            "area_hectares": round(area_ha, 4),
                            "area_acres": round(area_acres, 2),
                            "description": "Rainwater catchment watershed contributing runoff to the pond"
                        },
                        "geometry": poly_wgs84
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "feature_type": "farm_pond_site",
                            "pond_rank": pond["rank"],
                            "latitude": pond["latitude"],
                            "longitude": pond["longitude"],
                            "elevation_m": pond["elevation_m"],
                            "slope_deg": pond["slope_deg"],
                            "suitability_score": pond["suitability_score"],
                            "google_maps_url": pond["google_maps_url"]
                        },
                        "geometry": {
                            "type": "Point",
                            "coordinates": [pond["longitude"], pond["latitude"]]
                        }
                    }
                ]
            }

    return primary_catchment_info, all_catchment_summaries, primary_geojson


# --------------------------------------------------
# 9. Master Pipeline Runner
# --------------------------------------------------
def run_contour_analysis_pipeline(
    file_bytes: bytes,
    filename: str,
    top_n: int = 5,
    resolution: float = 1.0,
    min_separation_meters: float = 150.0,
    max_slope_degrees: float = 8.0
) -> Dict[str, Any]:
    """
    Executes full end-to-end terrain and catchment analysis pipeline on uploaded KML/KMZ file.
    """
    # 1. Parse KML / KMZ
    t0 = time.time()
    contours = parse_kml_or_kmz(file_bytes, filename)
    total_points = sum(len(c["coordinates"]) for c in contours)
    logger.info(f"[1/8] Parsed {len(contours)} contours ({total_points:,} points) in {time.time()-t0:.2f}s")

    # 2. Projection to UTM
    t0 = time.time()
    projected_contours, coord_meta, transformer, transformer_inv = project_contours(contours)
    logger.info(f"[2/8] UTM projection complete in {time.time()-t0:.2f}s")

    # 3. 2D Surface Interpolation / DEM
    t0 = time.time()
    dem, grid_x, grid_y, resolution = build_dem(projected_contours, resolution=resolution)
    logger.info(f"[3/8] DEM interpolated ({dem.shape[0]}x{dem.shape[1]} = {dem.size:,} cells) in {time.time()-t0:.2f}s")

    # 4. Horn's Slope and Aspect
    t0 = time.time()
    slope_deg, slope_percent, aspect_deg = calculate_slope(dem, resolution)
    logger.info(f"[4/8] Slope & aspect computed in {time.time()-t0:.2f}s")

    # 5. D8 Flow Direction
    t0 = time.time()
    flow_dir = calculate_flow_direction(dem, resolution)
    logger.info(f"[5/8] D8 flow direction computed in {time.time()-t0:.2f}s")

    # 6. Flow Accumulation & Downstream Graph
    t0 = time.time()
    flow_acc, downstream = calculate_flow_accumulation(dem, flow_dir, resolution)
    logger.info(f"[6/8] Flow accumulation routed in {time.time()-t0:.2f}s")

    # 7. Pond Suitability & Selection
    t0 = time.time()
    top_ponds = find_top_ponds(
        dem=dem,
        slope_deg=slope_deg,
        flow_acc=flow_acc,
        grid_x=grid_x,
        grid_y=grid_y,
        transformer_inv=transformer_inv,
        top_n=top_n,
        min_separation_meters=min_separation_meters,
        max_slope_degrees=max_slope_degrees,
        resolution=resolution
    )
    logger.info(f"[7/8] Found {len(top_ponds)} pond candidates in {time.time()-t0:.2f}s")

    if not top_ponds:
        raise ValueError("Could not find any suitable pond candidate site in the given terrain.")

    # 8. Delineate Catchment Basins & Export GeoJSON
    t0 = time.time()
    primary_catchment, all_catchments, geojson_doc = delineate_catchments_and_geojson(
        dem=dem,
        downstream=downstream,
        slope_deg=slope_deg,
        selected_ponds=top_ponds,
        grid_x=grid_x,
        grid_y=grid_y,
        resolution=resolution,
        transformer_inv=transformer_inv
    )
    logger.info(f"[8/8] Catchment delineation & GeoJSON export done in {time.time()-t0:.2f}s")

    # Terrain Classification Summary (from calculate_slope.py)
    flat_cells = int(np.count_nonzero(slope_deg <= 3.0))
    gentle_cells = int(np.count_nonzero((slope_deg > 3.0) & (slope_deg <= 8.0)))
    steep_cells = int(np.count_nonzero(slope_deg > 8.0))
    total_cells = int(dem.size)

    terrain_summary = {
        "dem_dimensions": {
            "rows": int(dem.shape[0]),
            "cols": int(dem.shape[1]),
            "total_cells": total_cells,
            "resolution_meters": resolution
        },
        "elevation_stats": {
            "min_m": round(float(dem.min()), 2),
            "max_m": round(float(dem.max()), 2),
            "mean_m": round(float(dem.mean()), 2),
            "relief_m": round(float(dem.max() - dem.min()), 2)
        },
        "slope_stats": {
            "mean_degrees": round(float(slope_deg.mean()), 2),
            "min_degrees": round(float(slope_deg.min()), 2),
            "max_degrees": round(float(slope_deg.max()), 2),
            "flat_terrain_pct": round((flat_cells / total_cells) * 100.0, 2),
            "gentle_terrain_pct": round((gentle_cells / total_cells) * 100.0, 2),
            "steep_terrain_pct": round((steep_cells / total_cells) * 100.0, 2)
        },
        "flow_accumulation_stats": {
            "max_accumulation_m2": round(float(flow_acc.max() * (resolution ** 2)), 2),
            "mean_accumulation_m2": round(float(flow_acc.mean() * (resolution ** 2)), 2)
        }
    }

    # Clean pond objects for JSON output (remove internal row/col indices)
    cleaned_top_ponds = []
    for p in top_ponds:
        p_copy = dict(p)
        p_copy.pop("row", None)
        p_copy.pop("col", None)
        cleaned_top_ponds.append(p_copy)

    selected_pond = cleaned_top_ponds[0] if cleaned_top_ponds else None

    return {
        "status": "success",
        "file_info": {
            "filename": filename,
            "file_size_bytes": len(file_bytes),
            "total_contours_parsed": len(contours),
            "total_contour_points": total_points
        },
        "coordinate_system": coord_meta,
        "terrain_summary": terrain_summary,
        "selected_pond": selected_pond,
        "pond_candidates": cleaned_top_ponds,
        "primary_catchment": primary_catchment,
        "all_catchments": all_catchments,
        "geojson": geojson_doc
    }

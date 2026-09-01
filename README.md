# Terrain Analysis & Farm Pond Catchment Delineation API (FastAPI Backend)

A FastAPI backend service that accepts contour maps (`KML` / `KMZ` format), computes a 2D Digital Elevation Model (DEM), analyzes terrain slopes and topographic aspect, calculates D8 hydrological drainage and flow accumulation, identifies optimal farm pond locations via multi-criteria suitability scoring (AHP + NMS), and delineates rainwater catchment watershed basins.

---

## 🚀 Key Features & Endpoints

- **`POST /analyzeContour`**: Primary endpoint for terrain analysis and catchment delineation.
- **`POST /findCatchment`**: Alias endpoint for `/analyzeContour`.
- **`GET /health`**: API health check.
- **`GET /docs`**: Interactive Swagger UI API documentation.
- **`GET /redoc`**: ReDoc API documentation.

### Parameter Name
- **`contour_map`** *(Required)*: Upload a `.kml` or `.kmz` contour map file as multipart form-data.

### Optional Parameters (Query / Form)
- `top_n` *(int, default: 5)*: Number of top pond candidates to identify.
- `resolution` *(float, default: 1.0)*: DEM metric grid spacing in meters.
- `min_separation_meters` *(float, default: 150.0)*: Minimum Euclidean distance between selected pond candidates.
- `max_slope_degrees` *(float, default: 8.0)*: Maximum allowable slope for pond placement.

---

## 📦 Installation

Install the required dependencies using pip:

```bash
pip install -r requirements.txt
```

---

## 🛠️ How to Run the Server

Activate the virtual environment and start the Uvicorn server:

```bash
# Using the project's virtual environment
/home/ganesh/Documents/csd/dummy/csd/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Server will be running at: `http://localhost:8000`  
Swagger UI docs available at: `http://localhost:8000/docs`

---

## 🧪 Testing with cURL / Postman

### 1. cURL Request
```bash
curl -X POST "http://localhost:8000/analyzeContour" \
  -F "contour_map=@contours_1m.kml"
```

Or calling the alias endpoint `/findCatchment`:
```bash
curl -X POST "http://localhost:8000/findCatchment" \
  -F "contour_map=@contours_1m.kml"
```

### 2. Postman Setup
1. **Method**: `POST`
2. **URL**: `http://localhost:8000/analyzeContour` (or `http://localhost:8000/findCatchment`)
3. **Body**: Select `form-data`
   - Key: `contour_map` (Change type dropdown from *Text* to *File*)
   - Value: Select your `contours_1m.kml` or `.kmz` file
4. Click **Send**.

### 3. Python Client Example
```python
import httpx

url = "http://localhost:8000/analyzeContour"
with open("contours_1m.kml", "rb") as f:
    files = {"contour_map": ("contours_1m.kml", f, "application/vnd.google-earth.kml+xml")}
    response = httpx.post(url, files=files, timeout=120.0)
    print(response.json())
```

---

## 📊 Output Response Structure (JSON)

```json
{
  "status": "success",
  "file_info": {
    "filename": "contours_1m.kml",
    "file_size_bytes": 6710528,
    "total_contours_parsed": 2711,
    "total_contour_points": 160473
  },
  "coordinate_system": {
    "source": "EPSG:4326",
    "target": "EPSG:32644",
    "projection": "UTM",
    "utm_zone": 44,
    "hemisphere": "north",
    "units": "meters",
    "center_lon": 81.29663,
    "center_lat": 21.25188,
    "bbox_wgs84": {
      "min_lon": 81.281404,
      "min_lat": 21.239822,
      "max_lon": 81.312647,
      "max_lat": 21.263581
    }
  },
  "terrain_summary": {
    "dem_dimensions": {
      "rows": 2627,
      "cols": 3243,
      "total_cells": 8519361,
      "resolution_meters": 1.0
    },
    "elevation_stats": {
      "min_m": 30.0,
      "max_m": 298.0,
      "mean_m": 283.62,
      "relief_m": 268.0
    },
    "slope_stats": {
      "mean_degrees": 3.6,
      "min_degrees": 0.0,
      "max_degrees": 89.61,
      "flat_terrain_pct": 49.61,
      "gentle_terrain_pct": 43.61,
      "steep_terrain_pct": 6.78
    },
    "flow_accumulation_stats": {
      "max_accumulation_m2": 8450.0,
      "mean_accumulation_m2": 23.76
    }
  },
  "selected_pond": {
    "rank": 1,
    "latitude": 21.251917,
    "longitude": 81.296668,
    "x_m": 530780.5,
    "y_m": 2350057.3,
    "elevation_m": 270.0,
    "slope_deg": 2.69,
    "flow_accumulation_m2": 8276.0,
    "suitability_score": 0.8738,
    "google_maps_url": "https://www.google.com/maps?q=21.251917,81.296668"
  },
  "pond_candidates": [
    {
      "rank": 1,
      "latitude": 21.251917,
      "longitude": 81.296668,
      "x_m": 530780.5,
      "y_m": 2350057.3,
      "elevation_m": 270.0,
      "slope_deg": 2.69,
      "flow_accumulation_m2": 8276.0,
      "suitability_score": 0.8738,
      "google_maps_url": "https://www.google.com/maps?q=21.251917,81.296668"
    }
  ],
  "primary_catchment": {
    "pond_rank": 1,
    "pond_location": {
      "latitude": 21.251917,
      "longitude": 81.296668,
      "elevation_m": 270.0
    },
    "catchment_area_m2": 8276.0,
    "catchment_area_hectares": 0.8276,
    "catchment_area_acres": 2.05,
    "catchment_cell_count": 8276,
    "elevation_min_m": 270.0,
    "elevation_max_m": 287.78,
    "elevation_mean_m": 280.01,
    "slope_mean_deg": 6.11
  },
  "all_catchments": [
    { ... }
  ],
  "geojson": {
    "type": "FeatureCollection",
    "name": "Farm_Pond_Catchment_Delineation",
    "crs": {
      "type": "name",
      "properties": { "name": "urn:ogc:def:crs:OGC:1.3:CRS84" }
    },
    "features": [
      {
        "type": "Feature",
        "properties": {
          "feature_type": "catchment_basin",
          "pond_rank": 1,
          "area_m2": 8276.0,
          "area_hectares": 0.8276,
          "area_acres": 2.05,
          "description": "Rainwater catchment watershed contributing runoff to the pond"
        },
        "geometry": {
          "type": "Polygon",
          "coordinates": [ ... ]
        }
      },
      {
        "type": "Feature",
        "properties": {
          "feature_type": "farm_pond_site",
          "pond_rank": 1,
          "latitude": 21.251917,
          "longitude": 81.296668,
          "elevation_m": 270.0,
          "slope_deg": 2.69,
          "suitability_score": 0.8738,
          "google_maps_url": "https://www.google.com/maps?q=21.251917,81.296668"
        },
        "geometry": {
          "type": "Point",
          "coordinates": [ 81.296668, 21.251917 ]
        }
      }
    ]
  }
}
```

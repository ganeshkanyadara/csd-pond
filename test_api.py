import io
import os
import json
import unittest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

SAMPLE_KML_PATH = "contours_1m.kml"

def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200

def test_api_info_endpoint():
    response = client.get("/api/info")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "POST /analyzeContour" in data["endpoints"]
    assert "POST /findCatchment" in data["endpoints"]

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"

def test_missing_contour_map_field():
    response = client.post("/analyzeContour")
    # Missing required form parameter 'contour_map'
    assert response.status_code in [400, 422]

def test_invalid_file_extension():
    files = {"contour_map": ("test.txt", b"dummy content", "text/plain")}
    response = client.post("/analyzeContour", files=files)
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]

def test_analyze_contour_endpoint():
    assert os.path.exists(SAMPLE_KML_PATH), f"Cannot find {SAMPLE_KML_PATH}"
    
    with open(SAMPLE_KML_PATH, "rb") as f:
        file_bytes = f.read()

    files = {"contour_map": ("contours_1m.kml", file_bytes, "application/vnd.google-earth.kml+xml")}
    
    # Using resolution=5.0 for fast and memory-safe test execution
    response = client.post(
        "/analyzeContour?resolution=5.0&top_n=5&rainfall_mm=900.0&runoff_coeff=0.35&pond_depth_m=3.0",
        files=files
    )
    assert response.status_code == 200, f"Error: {response.text}"
    
    data = response.json()
    assert data["status"] == "success"
    
    # Validate File Info
    assert data["file_info"]["filename"] == "contours_1m.kml"
    assert data["file_info"]["total_contours_parsed"] > 0
    assert data["file_info"]["total_contour_points"] > 0
    
    # Validate Coordinate System
    coord = data["coordinate_system"]
    assert coord["source"] == "EPSG:4326"
    assert "EPSG:32644" in coord["target"]
    assert coord["utm_zone"] == 44
    assert coord["units"] == "meters"
    
    # Validate Terrain Summary
    terrain = data["terrain_summary"]
    assert terrain["elevation_stats"]["min_m"] > 0
    assert terrain["elevation_stats"]["max_m"] > terrain["elevation_stats"]["min_m"]
    assert terrain["slope_stats"]["mean_degrees"] >= 0
    
    # Validate Selected Pond
    pond = data["selected_pond"]
    assert pond["rank"] == 1
    assert "latitude" in pond and "longitude" in pond
    assert "elevation_m" in pond
    assert "slope_deg" in pond
    assert "flow_accumulation_m2" in pond
    assert "suitability_score" in pond
    assert "google_maps_url" in pond
    
    # Validate Top Ponds
    assert len(data["pond_candidates"]) >= 1
    for p in data["pond_candidates"]:
        assert p["rank"] >= 1
        assert p["slope_deg"] <= 8.0  # Max slope constraint
    
    # Validate Catchment Info & Water Yield
    catchment = data["primary_catchment"]
    assert catchment["pond_rank"] == 1
    assert catchment["catchment_area_m2"] > 0
    assert catchment["catchment_area_hectares"] > 0
    assert catchment["catchment_area_acres"] > 0
    
    assert "water_yield" in data and data["water_yield"] is not None
    wy = data["water_yield"]
    assert wy["annual_rainfall_mm"] == 900.0
    assert wy["runoff_coefficient"] == 0.35
    assert wy["gross_runoff_m3"] > 0
    assert wy["harvestable_volume_m3"] > 0
    assert abs(wy["harvestable_volume_liters"] - wy["harvestable_volume_m3"] * 1000.0) < 1.0
    assert wy["recommended_pond_capacity_m3"] > 0
    assert wy["recommended_depth_m"] == 3.0
    assert wy["recommended_top_width_m"] > 0
    assert wy["recommended_top_length_m"] > 0
    
    # Validate GeoJSON
    geojson = data["geojson"]
    assert geojson["type"] == "FeatureCollection"
    assert len(geojson["features"]) >= 2
    types = [f["properties"]["feature_type"] for f in geojson["features"]]
    assert "catchment_basin" in types
    assert "farm_pond_site" in types

def test_find_catchment_alias_endpoint():
    with open(SAMPLE_KML_PATH, "rb") as f:
        file_bytes = f.read()

    files = {"contour_map": ("contours_1m.kml", file_bytes, "application/vnd.google-earth.kml+xml")}
    
    response = client.post("/findCatchment?resolution=5.0&top_n=3", files=files)
    assert response.status_code == 200, f"Error: {response.text}"
    data = response.json()
    assert data["status"] == "success"
    assert len(data["pond_candidates"]) >= 1
    assert data["primary_catchment"]["catchment_area_m2"] > 0
    assert data["water_yield"] is not None

def test_analyze_sample_with_land_bbox():
    # Test quick-analysis endpoint with user-selected land bounding box
    bbox_params = {
        "resolution": 5.0,
        "top_n": 3,
        "rainfall_mm": 850.0,
        "bbox_min_lat": 17.50,
        "bbox_min_lon": 78.30,
        "bbox_max_lat": 17.52,
        "bbox_max_lon": 78.32
    }
    response = client.post("/api/analyzeSample", params=bbox_params)
    assert response.status_code == 200, f"Error: {response.text}"
    data = response.json()
    assert data["status"] == "success"
    assert data["selected_land_bbox"] is not None
    assert data["selected_land_bbox"]["min_lat"] == 17.50
    assert data["selected_pond"] is not None
    assert data["water_yield"]["gross_runoff_m3"] > 0

if __name__ == "__main__":
    test_root_endpoint()
    test_api_info_endpoint()
    test_health_endpoint()
    test_missing_contour_map_field()
    test_invalid_file_extension()
    test_analyze_contour_endpoint()
    test_find_catchment_alias_endpoint()
    test_analyze_sample_with_land_bbox()
    print("All tests passed successfully!")

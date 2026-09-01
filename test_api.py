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
    
    # Using resolution=2.0 for super fast test execution
    response = client.post("/analyzeContour?resolution=2.0&top_n=5", files=files)
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
    assert len(data["pond_candidates"]) == 5
    for p in data["pond_candidates"]:
        assert p["rank"] >= 1
        assert p["slope_deg"] <= 8.0  # Max slope constraint
    
    # Validate Catchment Info
    catchment = data["primary_catchment"]
    assert catchment["pond_rank"] == 1
    assert catchment["catchment_area_m2"] > 0
    assert catchment["catchment_area_hectares"] > 0
    assert catchment["catchment_area_acres"] > 0
    
    # Validate GeoJSON
    geojson = data["geojson"]
    assert geojson["type"] == "FeatureCollection"
    assert len(geojson["features"]) == 2
    assert geojson["features"][0]["properties"]["feature_type"] == "catchment_basin"
    assert geojson["features"][1]["properties"]["feature_type"] == "farm_pond_site"
    assert geojson["features"][0]["geometry"]["type"] in ["Polygon", "MultiPolygon"]
    assert geojson["features"][1]["geometry"]["type"] == "Point"

def test_find_catchment_alias_endpoint():
    with open(SAMPLE_KML_PATH, "rb") as f:
        file_bytes = f.read()

    files = {"contour_map": ("contours_1m.kml", file_bytes, "application/vnd.google-earth.kml+xml")}
    
    response = client.post("/findCatchment?resolution=2.0&top_n=3", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert len(data["pond_candidates"]) == 3
    assert data["primary_catchment"]["catchment_area_m2"] > 0

if __name__ == "__main__":
    test_root_endpoint()
    test_health_endpoint()
    test_missing_contour_map_field()
    test_invalid_file_extension()
    test_analyze_contour_endpoint()
    test_find_catchment_alias_endpoint()
    print("All tests passed successfully!")

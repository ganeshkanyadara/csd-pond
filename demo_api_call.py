"""
Demonstration script showing how to call the FastAPI Contour Analysis & Catchment Delineation API.
Can be executed with Python requests/httpx or tested using Postman/cURL.
"""

import os
import json
import time
import httpx

API_URL = "http://localhost:8000/analyzeContour"
KML_FILE = "contours_1m.kml"

def run_demo():
    print(f"================================================================")
    print(f" DEMONSTRATION: POST /analyzeContour (Variable: contour_map)")
    print(f"================================================================")
    print(f"Target URL : {API_URL}")
    print(f"Sample File: {KML_FILE}")
    print(f"Sending multipart form POST request...")

    t0 = time.time()
    with open(KML_FILE, "rb") as f:
        files = {
            "contour_map": (KML_FILE, f, "application/vnd.google-earth.kml+xml")
        }
        params = {
            "top_n": 5,
            "resolution": 1.0,
            "min_separation_meters": 150.0,
            "max_slope_degrees": 8.0
        }
        
        response = httpx.post(API_URL, files=files, params=params, timeout=120.0)

    elapsed = time.time() - t0
    print(f"Response Status Code: {response.status_code} (took {elapsed:.2f}s)")
    
    if response.status_code == 200:
        data = response.json()
        print("\n--- 1. File & Coordinate System Info ---")
        print(f"  • Filename: {data['file_info']['filename']}")
        print(f"  • Contours: {data['file_info']['total_contours_parsed']:,}")
        print(f"  • Points  : {data['file_info']['total_contour_points']:,}")
        print(f"  • Projected CRS: {data['coordinate_system']['target']} ({data['coordinate_system']['units']})")
        
        print("\n--- 2. Terrain Summary ---")
        elev = data['terrain_summary']['elevation_stats']
        slope = data['terrain_summary']['slope_stats']
        print(f"  • Elevation: Min = {elev['min_m']}m | Max = {elev['max_m']}m | Mean = {elev['mean_m']}m")
        print(f"  • Slope    : Mean = {slope['mean_degrees']}° (Flat: {slope['flat_terrain_pct']}%, Gentle: {slope['gentle_terrain_pct']}%, Steep: {slope['steep_terrain_pct']}%)")
        
        print("\n--- 3. Recommended Pond Site (Rank #1) ---")
        pond = data['selected_pond']
        print(f"  • Latitude : {pond['latitude']}")
        print(f"  • Longitude: {pond['longitude']}")
        print(f"  • UTM (X, Y): ({pond['x_m']}, {pond['y_m']})")
        print(f"  • Elevation: {pond['elevation_m']} m")
        print(f"  • Slope    : {pond['slope_deg']}°")
        print(f"  • Suitability Score: {pond['suitability_score']}")
        print(f"  • Google Maps URL  : {pond['google_maps_url']}")

        print("\n--- 4. Catchment Watershed Information ---")
        catchment = data['primary_catchment']
        print(f"  • Catchment Area: {catchment['catchment_area_m2']:,.1f} m² ({catchment['catchment_area_hectares']:.4f} hectares / {catchment['catchment_area_acres']:.2f} acres)")
        print(f"  • Basin Elevation: {catchment['elevation_min_m']}m to {catchment['elevation_max_m']}m (Mean: {catchment['elevation_mean_m']}m)")
        print(f"  • Basin Mean Slope: {catchment['slope_mean_deg']}°")

        print(f"\n--- 5. Top {len(data['pond_candidates'])} Pond Candidates ---")
        for p in data['pond_candidates']:
            print(f"  [Rank #{p['rank']}] Score: {p['suitability_score']} | Elev: {p['elevation_m']}m | Slope: {p['slope_deg']}° | Flow Acc: {p['flow_accumulation_m2']:,.0f}m² | Lat: {p['latitude']}, Lon: {p['longitude']}")

        # Ensure outputs directory exists
        os.makedirs("outputs", exist_ok=True)
        
        # Save output GeoJSON
        with open("outputs/api_response_catchment.geojson", "w") as f_out:
            json.dump(data["geojson"], f_out, indent=2)
        print(f"\nSaved catchment GeoJSON output to: outputs/api_response_catchment.geojson")
        
        # Save output JSON
        with open("outputs/api_response.json", "w") as f_out:
            json.dump(data, f_out, indent=2)
        print(f"Saved full JSON output to: outputs/api_response.json")
    else:
        print(f"Error Response: {response.text}")

if __name__ == "__main__":
    run_demo()

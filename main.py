import os
import io
import time
import logging
from typing import Optional

from fastapi import FastAPI, File, UploadFile, Query, Form, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from pipeline import run_contour_analysis_pipeline
from schemas import ContourAnalysisResponse

# Configure logging format for terminal visibility
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("csd-pond")

# Initialize FastAPI application
app = FastAPI(
    title="AI-based Village Pond Planning System API",
    description=(
        "Production backend API for analyzing contour maps (KML/KMZ), computing continuous Digital Elevation Models (DEM), "
        "calculating terrain slope and topographic aspect using Horn's algorithm, routing D8 flow direction and accumulation, "
        "identifying optimal farm pond locations via multi-criteria suitability scoring (AHP + NMS), "
        "delineating watershed catchment basins, estimating harvestable water volume, and exporting standard GeoJSON."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS Middleware for accessibility from any client / frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", tags=["General"], include_in_schema=False)
async def root():
    """
    Serves the interactive Web GIS frontend application if available,
    otherwise returns API status JSON.
    """
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {
        "service": "AI-based Village Pond Planning System API",
        "status": "online",
        "version": "1.0.0"
    }


@app.get("/api/info", tags=["General"])
async def api_info():
    """
    Returns service metadata, version, and active endpoints.
    """
    return {
        "service": "AI-based Village Pond Planning System API",
        "status": "online",
        "version": "1.0.0",
        "endpoints": {
            "GET /": "Interactive Web GIS application",
            "POST /analyzeContour": "Upload KML/KMZ contour map under 'contour_map' to analyze terrain, delineate catchment, and size farm ponds",
            "POST /findCatchment": "Alias endpoint for /analyzeContour",
            "POST /api/analyzeSample": "Quick-run analysis on preloaded village contour map with custom land area / rainfall parameters",
            "GET /api/sampleContour": "Download preloaded sample contours KML",
            "GET /health": "API Health check",
            "GET /docs": "Interactive Swagger API documentation",
            "GET /redoc": "ReDoc API documentation"
        }
    }


@app.get("/health", tags=["General"])
async def health_check():
    """
    Health check endpoint for container monitoring.
    """
    return {"status": "healthy", "timestamp": time.time()}


@app.get("/api/sampleContour", tags=["General"])
async def get_sample_contour():
    """
    Streams the preloaded village contour KML file.
    """
    sample_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "contours_1m.kml")
    if os.path.exists(sample_file):
        return FileResponse(
            sample_file,
            media_type="application/vnd.google-earth.kml+xml",
            filename="contours_1m.kml"
        )
    raise HTTPException(status_code=404, detail="Sample contours_1m.kml file not found.")


async def process_contour_analysis(
    contour_map: UploadFile,
    top_n: int,
    resolution: float,
    min_separation_meters: float,
    max_slope_degrees: float,
    rainfall_mm: float = 850.0,
    runoff_coeff: float = 0.35,
    pond_depth_m: float = 3.0,
    bbox_min_lat: Optional[float] = None,
    bbox_min_lon: Optional[float] = None,
    bbox_max_lat: Optional[float] = None,
    bbox_max_lon: Optional[float] = None
) -> ContourAnalysisResponse:
    """
    Core handler for analyzing contour maps and delineating catchment.
    """
    if not contour_map:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file uploaded. Please upload a valid KML or KMZ contour map under the variable name 'contour_map'."
        )

    filename = contour_map.filename or "contour_map.kml"
    filename_lower = filename.lower()

    if not (filename_lower.endswith(".kml") or filename_lower.endswith(".kmz") or filename_lower.endswith(".xml")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{filename}'. The API accepts only .kml or .kmz files under parameter name 'contour_map'."
        )

    try:
        file_bytes = await contour_map.read()
        if not file_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty."
            )

        file_size_mb = len(file_bytes) / (1024 * 1024)
        logger.info(f"Received '{filename}' ({file_size_mb:.2f} MB) | resolution={resolution:.1f}m | top_n={top_n}")
        t_start = time.time()

        # Run terrain & catchment analysis pipeline
        result = run_contour_analysis_pipeline(
            file_bytes=file_bytes,
            filename=filename,
            top_n=top_n,
            resolution=resolution,
            min_separation_meters=min_separation_meters,
            max_slope_degrees=max_slope_degrees,
            annual_rainfall_mm=rainfall_mm,
            runoff_coefficient=runoff_coeff,
            pond_depth_m=pond_depth_m,
            bbox_min_lat=bbox_min_lat,
            bbox_min_lon=bbox_min_lon,
            bbox_max_lat=bbox_max_lat,
            bbox_max_lon=bbox_max_lon
        )

        total_elapsed = time.time() - t_start
        logger.info(f"Pipeline completed in {total_elapsed:.2f}s for '{filename}'")

        return ContourAnalysisResponse(**result)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Terrain processing error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while analyzing the contour map: {str(e)}"
        )


@app.post(
    "/analyzeContour",
    response_model=ContourAnalysisResponse,
    summary="Analyze Contour Map & Find Catchment",
    tags=["Catchment & Pond Analysis"]
)
async def analyze_contour(
    contour_map: UploadFile = File(..., description="Uploaded KML or KMZ contour map file"),
    top_n: int = Query(5, ge=1, le=20, description="Number of top pond candidates to identify"),
    resolution: float = Query(5.0, ge=0.5, le=10.0, description="DEM grid resolution in meters (default: 5.0m)"),
    min_separation_meters: float = Query(150.0, ge=10.0, description="Minimum spatial distance between pond candidates"),
    max_slope_degrees: float = Query(8.0, ge=1.0, le=45.0, description="Maximum allowable slope for pond placement"),
    rainfall_mm: float = Query(850.0, ge=50.0, le=5000.0, description="Annual rainfall depth in mm"),
    runoff_coeff: float = Query(0.35, ge=0.05, le=1.0, description="Catchment runoff coefficient C (0.05 to 1.0)"),
    pond_depth_m: float = Query(3.0, ge=1.0, le=15.0, description="Recommended pond excavation depth in meters"),
    bbox_min_lat: Optional[float] = Query(None, description="Land area selection: min latitude"),
    bbox_min_lon: Optional[float] = Query(None, description="Land area selection: min longitude"),
    bbox_max_lat: Optional[float] = Query(None, description="Land area selection: max latitude"),
    bbox_max_lon: Optional[float] = Query(None, description="Land area selection: max longitude")
):
    """
    **Primary API Endpoint:**
    Accepts a contour map in `.kml` or `.kmz` format under variable name `contour_map`.
    
    **Pipeline Steps:**
    1. Extracts contour lines and elevations from KML/KMZ placemarks and geometries.
    2. Determines geographic centroid and transforms coordinates to metric UTM projection.
    3. Interpolates a continuous 2D Digital Elevation Model (DEM) surface.
    4. Computes topographic slope and aspect using Horn's 8-neighbor weighted algorithm.
    5. Calculates D8 downhill flow direction and accumulates upstream runoff drainage network.
    6. Identifies optimal pond locations via multi-criteria suitability scoring (AHP) and Spatial Non-Maximum Suppression (NMS).
       If land boundary parameters are provided, prioritizes/restricts candidates within the selected land parcel.
    7. Delineates the contributing rainwater catchment watershed basin from pour points.
    8. Estimates gross runoff, harvestable volume, and recommended pond dimensions.
    9. Returns comprehensive catchment metrics, top pond candidates, and standard GeoJSON FeatureCollection.
    """
    return await process_contour_analysis(
        contour_map=contour_map,
        top_n=top_n,
        resolution=resolution,
        min_separation_meters=min_separation_meters,
        max_slope_degrees=max_slope_degrees,
        rainfall_mm=rainfall_mm,
        runoff_coeff=runoff_coeff,
        pond_depth_m=pond_depth_m,
        bbox_min_lat=bbox_min_lat,
        bbox_min_lon=bbox_min_lon,
        bbox_max_lat=bbox_max_lat,
        bbox_max_lon=bbox_max_lon
    )


@app.post(
    "/findCatchment",
    response_model=ContourAnalysisResponse,
    summary="Find Catchment & Pond Sites (Alias for /analyzeContour)",
    tags=["Catchment & Pond Analysis"]
)
async def find_catchment(
    contour_map: UploadFile = File(..., description="Uploaded KML or KMZ contour map file"),
    top_n: int = Query(5, ge=1, le=20, description="Number of top pond candidates to identify"),
    resolution: float = Query(5.0, ge=0.5, le=10.0, description="DEM grid resolution in meters (default: 5.0m)"),
    min_separation_meters: float = Query(150.0, ge=10.0, description="Minimum spatial distance between pond candidates"),
    max_slope_degrees: float = Query(8.0, ge=1.0, le=45.0, description="Maximum allowable slope for pond placement"),
    rainfall_mm: float = Query(850.0, ge=50.0, le=5000.0, description="Annual rainfall depth in mm"),
    runoff_coeff: float = Query(0.35, ge=0.05, le=1.0, description="Catchment runoff coefficient C (0.05 to 1.0)"),
    pond_depth_m: float = Query(3.0, ge=1.0, le=15.0, description="Recommended pond excavation depth in meters"),
    bbox_min_lat: Optional[float] = Query(None, description="Land area selection: min latitude"),
    bbox_min_lon: Optional[float] = Query(None, description="Land area selection: min longitude"),
    bbox_max_lat: Optional[float] = Query(None, description="Land area selection: max latitude"),
    bbox_max_lon: Optional[float] = Query(None, description="Land area selection: max longitude")
):
    """
    **Alias API Endpoint:**
    Accepts a contour map in `.kml` or `.kmz` format under variable name `contour_map`.
    Identical behavior and response as `/analyzeContour`.
    """
    return await process_contour_analysis(
        contour_map=contour_map,
        top_n=top_n,
        resolution=resolution,
        min_separation_meters=min_separation_meters,
        max_slope_degrees=max_slope_degrees,
        rainfall_mm=rainfall_mm,
        runoff_coeff=runoff_coeff,
        pond_depth_m=pond_depth_m,
        bbox_min_lat=bbox_min_lat,
        bbox_min_lon=bbox_min_lon,
        bbox_max_lat=bbox_max_lat,
        bbox_max_lon=bbox_max_lon
    )


@app.post(
    "/api/analyzeSample",
    response_model=ContourAnalysisResponse,
    summary="Fast Analysis on Preloaded Village Contour Map",
    tags=["Catchment & Pond Analysis"]
)
async def analyze_sample(
    top_n: int = Query(5, ge=1, le=20, description="Number of top pond candidates to identify"),
    resolution: float = Query(5.0, ge=2.0, le=20.0, description="DEM grid resolution in meters"),
    min_separation_meters: float = Query(150.0, ge=10.0, description="Minimum spatial distance between pond candidates"),
    max_slope_degrees: float = Query(8.0, ge=1.0, le=45.0, description="Maximum allowable slope for pond placement"),
    rainfall_mm: float = Query(850.0, ge=50.0, le=5000.0, description="Annual rainfall depth in mm"),
    runoff_coeff: float = Query(0.35, ge=0.05, le=1.0, description="Runoff coefficient"),
    pond_depth_m: float = Query(3.0, ge=1.0, le=15.0, description="Target pond excavation depth in meters"),
    bbox_min_lat: Optional[float] = Query(None, description="Land boundary: min latitude"),
    bbox_min_lon: Optional[float] = Query(None, description="Land boundary: min longitude"),
    bbox_max_lat: Optional[float] = Query(None, description="Land boundary: max latitude"),
    bbox_max_lon: Optional[float] = Query(None, description="Land boundary: max longitude")
):
    """
    Optimized endpoint for the interactive frontend to execute terrain analysis and catchment delineation
    directly on the server-cached village contour map with zero network upload latency.
    """
    sample_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "contours_1m.kml")
    if not os.path.exists(sample_file):
        raise HTTPException(status_code=404, detail="Sample contours_1m.kml not found.")

    with open(sample_file, "rb") as f:
        file_bytes = f.read()

    result = run_contour_analysis_pipeline(
        file_bytes=file_bytes,
        filename="contours_1m.kml",
        top_n=top_n,
        resolution=resolution,
        min_separation_meters=min_separation_meters,
        max_slope_degrees=max_slope_degrees,
        annual_rainfall_mm=rainfall_mm,
        runoff_coefficient=runoff_coeff,
        pond_depth_m=pond_depth_m,
        bbox_min_lat=bbox_min_lat,
        bbox_min_lon=bbox_min_lon,
        bbox_max_lat=bbox_max_lat,
        bbox_max_lon=bbox_max_lon
    )
    return ContourAnalysisResponse(**result)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 3000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)

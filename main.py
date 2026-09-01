import os
import io
import time
import logging
from typing import Optional

from fastapi import FastAPI, File, UploadFile, Query, Form, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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
    title="Terrain Analysis & Farm Pond Catchment Delineation API",
    description=(
        "Backend API for analyzing contour maps (KML/KMZ), computing continuous Digital Elevation Models (DEM), "
        "calculating terrain slope and topographic aspect using Horn's algorithm, routing D8 flow direction and accumulation, "
        "identifying optimal farm pond locations via multi-criteria suitability scoring (AHP + NMS), "
        "delineating watershed catchment basins, and exporting standard GeoJSON."
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


@app.get("/", tags=["General"])
async def root():
    """
    Root endpoint returning service status and available routes.
    """
    return {
        "service": "Contour Analysis & Catchment Delineation API",
        "status": "online",
        "version": "1.0.0",
        "endpoints": {
            "POST /analyzeContour": "Upload KML/KMZ contour map under 'contour_map' to analyze terrain and delineate catchment",
            "POST /findCatchment": "Alias endpoint for /analyzeContour",
            "GET /health": "API Health check",
            "GET /docs": "Interactive Swagger API documentation",
            "GET /redoc": "ReDoc API documentation"
        }
    }


@app.get("/health", tags=["General"])
async def health_check():
    """
    Health check endpoint.
    """
    return {"status": "healthy", "timestamp": time.time()}


async def process_contour_analysis(
    contour_map: UploadFile,
    top_n: int,
    resolution: float,
    min_separation_meters: float,
    max_slope_degrees: float
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
            max_slope_degrees=max_slope_degrees
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
    resolution: float = Query(1.0, ge=0.5, le=10.0, description="DEM grid resolution in meters (default: 1.0m)"),
    min_separation_meters: float = Query(150.0, ge=10.0, description="Minimum spatial distance between pond candidates"),
    max_slope_degrees: float = Query(8.0, ge=1.0, le=45.0, description="Maximum allowable slope for pond placement")
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
    7. Delineates the exact contributing rainwater catchment watershed basin from pour points.
    8. Returns comprehensive catchment metrics, top pond candidates, and standard GeoJSON FeatureCollection.
    """
    return await process_contour_analysis(
        contour_map=contour_map,
        top_n=top_n,
        resolution=resolution,
        min_separation_meters=min_separation_meters,
        max_slope_degrees=max_slope_degrees
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
    resolution: float = Query(1.0, ge=0.5, le=10.0, description="DEM grid resolution in meters (default: 1.0m)"),
    min_separation_meters: float = Query(150.0, ge=10.0, description="Minimum spatial distance between pond candidates"),
    max_slope_degrees: float = Query(8.0, ge=1.0, le=45.0, description="Maximum allowable slope for pond placement")
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
        max_slope_degrees=max_slope_degrees
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

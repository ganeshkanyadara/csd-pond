from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class FileInfo(BaseModel):
    filename: str
    file_size_bytes: int
    total_contours_parsed: int
    total_contour_points: int

class BBoxWGS84(BaseModel):
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float

class CoordinateSystem(BaseModel):
    source: str
    target: str
    projection: str
    utm_zone: int
    hemisphere: str
    units: str
    center_lon: float
    center_lat: float
    bbox_wgs84: BBoxWGS84

class DEMDimensions(BaseModel):
    rows: int
    cols: int
    total_cells: int
    resolution_meters: float

class ElevationStats(BaseModel):
    min_m: float
    max_m: float
    mean_m: float
    relief_m: float

class SlopeStats(BaseModel):
    mean_degrees: float
    min_degrees: float
    max_degrees: float
    flat_terrain_pct: float
    gentle_terrain_pct: float
    steep_terrain_pct: float

class FlowAccumulationStats(BaseModel):
    max_accumulation_m2: float
    mean_accumulation_m2: float

class TerrainSummary(BaseModel):
    dem_dimensions: DEMDimensions
    elevation_stats: ElevationStats
    slope_stats: SlopeStats
    flow_accumulation_stats: FlowAccumulationStats

class PondCandidate(BaseModel):
    rank: int
    latitude: float
    longitude: float
    x_m: float
    y_m: float
    elevation_m: float
    slope_deg: float
    flow_accumulation_m2: float
    suitability_score: float
    google_maps_url: str

class PondLocation(BaseModel):
    latitude: float
    longitude: float
    elevation_m: float

class WaterYieldEstimate(BaseModel):
    annual_rainfall_mm: float = Field(..., description="Annual rainfall depth in mm")
    runoff_coefficient: float = Field(..., description="Catchment runoff coefficient (C)")
    gross_runoff_m3: float = Field(..., description="Gross annual runoff volume in cubic meters")
    harvestable_volume_m3: float = Field(..., description="Harvestable water volume in m3 (70% collection efficiency)")
    harvestable_volume_liters: float = Field(..., description="Harvestable water volume in liters")
    recommended_pond_capacity_m3: float = Field(..., description="Recommended pond storage volume in m3")
    recommended_depth_m: float = Field(..., description="Recommended pond depth in meters")
    recommended_top_width_m: float = Field(..., description="Recommended pond top width in meters (2:1 length-to-width ratio)")
    recommended_top_length_m: float = Field(..., description="Recommended pond top length in meters (2:1 length-to-width ratio)")
    recommended_surface_area_m2: float = Field(..., description="Recommended pond surface area in square meters")

class CatchmentSummary(BaseModel):
    pond_rank: int
    pond_location: PondLocation
    catchment_area_m2: float
    catchment_area_hectares: float
    catchment_area_acres: float
    catchment_cell_count: int
    elevation_min_m: float
    elevation_max_m: float
    elevation_mean_m: float
    slope_mean_deg: float
    water_yield: Optional[WaterYieldEstimate] = None

class ContourAnalysisResponse(BaseModel):
    status: str = Field("success", description="Status of the operation")
    file_info: FileInfo
    coordinate_system: CoordinateSystem
    terrain_summary: TerrainSummary
    selected_pond: PondCandidate
    pond_candidates: List[PondCandidate]
    primary_catchment: CatchmentSummary
    all_catchments: List[CatchmentSummary]
    water_yield: Optional[WaterYieldEstimate] = Field(None, description="Hydrological water yield and pond sizing recommendation for primary site")
    selected_land_bbox: Optional[BBoxWGS84] = Field(None, description="Optional bounding box of the user-selected land area")
    geojson: Dict[str, Any] = Field(..., description="RFC 7946 standard GeoJSON FeatureCollection")


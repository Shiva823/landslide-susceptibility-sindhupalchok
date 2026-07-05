"""
config.py
═══════════════════════════════════════════════════════════════
Central configuration for Landslide Susceptibility Mapping
Sindhupalchok District, Nepal — KU COMP 313

All paths, settings and constants are defined here.
Every other file imports from this — never hardcode paths.

Project Structure:
    sindhupalchok_landslide/
    ├── data/
    │   └── processed/
    │       ├── rasters/             ← all 9 .tif files
    │       ├── shapefiles/          ← boundary .shp files
    │       └── landslide_inventory/ ← landslide .csv
    ├── src/
    │   ├── __init__.py
    │   ├── config.py
    │   └── eda.py
    ├── outputs/
    │   ├── figures/
    │   ├── models/
    │   └── maps/
    ├── notebooks/
    ├── reports/
    ├── main.py
    ├── README.md
    └── requirements.txt
═══════════════════════════════════════════════════════════════
"""

import os

# ── ROOT DIRECTORY ──────────────────────────────────────────────────
# Goes two levels up from src/config.py → project root
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── DATA DIRECTORIES ────────────────────────────────────────────────
DATA_DIR             = os.path.join(ROOT_DIR, "data")
PROCESSED_DIR        = os.path.join(DATA_DIR, "processed")
RASTER_DIR           = os.path.join(PROCESSED_DIR, "rasters")
SHAPEFILE_DIR        = os.path.join(PROCESSED_DIR, "shapefiles")
INVENTORY_DIR        = os.path.join(PROCESSED_DIR, "landslide_inventory")

# ── OUTPUT DIRECTORIES ──────────────────────────────────────────────
OUTPUT_DIR           = os.path.join(ROOT_DIR, "outputs")
FIGURES_DIR          = os.path.join(OUTPUT_DIR, "figures")
MODELS_DIR           = os.path.join(OUTPUT_DIR, "models")
MAPS_DIR             = os.path.join(OUTPUT_DIR, "maps")

# ── INPUT FILES ─────────────────────────────────────────────────────
BOUNDARY_SHP         = os.path.join(SHAPEFILE_DIR, "sindhupalchok_boundary.shp")
LANDSLIDE_CSV        = os.path.join(INVENTORY_DIR, "sindhupalchowk_landslides.csv")

# ── RASTER FILES ────────────────────────────────────────────────────
RASTERS = {
    "Slope"          : os.path.join(RASTER_DIR, "Sindhupalchok_Slope.tif"),
    "Elevation"      : os.path.join(RASTER_DIR, "Sindhupalchok_DEM.tif"),
    "Aspect"         : os.path.join(RASTER_DIR, "Sindhupalchok_Aspect.tif"),
    "NDVI"           : os.path.join(RASTER_DIR, "Sindhupalchok_NDVI_2025_30m.tif"),
    "LULC"           : os.path.join(RASTER_DIR, "Sindhupalchok_LULC_30m.tif"),
    "Rainfall"       : os.path.join(RASTER_DIR, "Sindhupalchok_Rainfall_Raster.tif"),
    "River Proximity": os.path.join(RASTER_DIR, "Sindhupalchok_RiverProximity.tif"),
    "Road Proximity" : os.path.join(RASTER_DIR, "Sindhupalchok_RoadProximity.tif"),
    "TWI"            : os.path.join(RASTER_DIR, "Sindhupalchok_TWI_2025.tif"),
}

# ── FEATURE ORDER ───────────────────────────────────────────────────
# Keep this order consistent across all files
FEATURE_NAMES = [
    "Slope",
    "Elevation",
    "Aspect",
    "NDVI",
    "LULC",
    "Rainfall",
    "River Proximity",
    "Road Proximity",
    "TWI",
]

# ── MODEL SETTINGS ──────────────────────────────────────────────────
RANDOM_SEED = 42
TEST_SIZE   = 0.2
N_FOLDS     = 5
TARGET_CRS  = "EPSG:4326"

# ── OUTPUT FILE PATHS ───────────────────────────────────────────────
CLEAN_LANDSLIDE_CSV = os.path.join(INVENTORY_DIR, "clean_landslide_samples.csv")
TRAINING_CSV        = os.path.join(INVENTORY_DIR, "training_dataset.csv")
BEST_MODEL_PKL     = os.path.join(MODELS_DIR,    "best_model.pkl")
SUSCEPTIBILITY_MAP = os.path.join(MAPS_DIR,      "susceptibility_map.tif")

# ── VISUALIZATION COLORS ────────────────────────────────────────────
COLORS = {
    "dark_bg" : "#0d1117",
    "card_bg" : "#161b22",
    "accent"  : "#58a6ff",
    "green"   : "#3fb950",
    "orange"  : "#d29922",
    "red"     : "#f85149",
    "purple"  : "#bc8cff",
    "text"    : "#e6edf3",
    "subtext" : "#8b949e",
    "gold"    : "#ffd700",
}

FEATURE_COLORS = [
    "#58a6ff",  # Slope
    "#3fb950",  # Elevation
    "#d29922",  # Aspect
    "#bc8cff",  # NDVI
    "#f85149",  # LULC
    "#ff7b72",  # Rainfall
    "#79c0ff",  # River Proximity
    "#56d364",  # Road Proximity
    "#ffa657",  # TWI
]

# ── AUTO-CREATE OUTPUT DIRECTORIES ──────────────────────────────────
for _dir in [FIGURES_DIR, MODELS_DIR, MAPS_DIR]:
    os.makedirs(_dir, exist_ok=True)

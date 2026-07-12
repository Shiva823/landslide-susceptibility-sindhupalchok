"""
Export web dashboard assets for the landslide warning app.

The dashboard is static HTML/JS, so this script converts GeoTIFF rasters and
CSV summaries into browser-friendly PNG overlays, GeoJSON, and JSON metadata.
"""

import json
import os
import shutil
import sys

import numpy as np
import pandas as pd
from PIL import Image
import rasterio
from scipy.interpolate import griddata

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import BOUNDARY_SHP, CLEAN_LANDSLIDE_CSV, FIGURES_DIR, MAPS_DIR, ROOT_DIR
from src.dynamic_risk import (
    DYNAMIC_RISK_MAP,
    DYNAMIC_RISK_SUMMARY_CSV,
    RAINFALL_POINTS_CSV,
    RAINFALL_TRIGGER_THRESHOLDS,
    RISK_COLORS,
    RISK_NODATA,
    _calculate_dynamic_risk,
)
from src.validation import (
    CLASS_COLORS,
    CLASS_NODATA,
    CLASSIFIED_MAP,
    CLASS_SUMMARY_CSV,
)


WEB_DIR = os.path.join(ROOT_DIR, "web_app")
WEB_ASSET_DIR = os.path.join(WEB_DIR, "assets")
WEB_DATA_DIR = os.path.join(WEB_DIR, "data")

SUSCEPTIBILITY_OVERLAY = os.path.join(WEB_ASSET_DIR, "susceptibility_classes.png")
RISK_OVERLAY_TEMPLATE = os.path.join(WEB_ASSET_DIR, "dynamic_risk_{window}.png")
BOUNDARY_GEOJSON = os.path.join(WEB_DATA_DIR, "boundary.geojson")
LANDSLIDE_POINTS_GEOJSON = os.path.join(WEB_DATA_DIR, "landslide_points.geojson")
RAINFALL_POINTS_GEOJSON = os.path.join(WEB_DATA_DIR, "rainfall_points.geojson")
APP_DATA_JSON = os.path.join(WEB_DATA_DIR, "app-data.json")

WINDOWS = ["combined", "1h", "3h", "24h", "72h"]


def _ensure_dirs():
    os.makedirs(WEB_ASSET_DIR, exist_ok=True)
    os.makedirs(WEB_DATA_DIR, exist_ok=True)


def _raster_bounds(src):
    bounds = src.bounds
    return [[bounds.bottom, bounds.left], [bounds.top, bounds.right]]


def _hex_to_rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))


def _classified_png(values, nodata, colors, bins=None):
    rgba = np.zeros((values.shape[0], values.shape[1], 4), dtype=np.uint8)
    if bins is None:
        for class_value, color in enumerate(colors, start=1):
            rgba[values == class_value, :3] = _hex_to_rgb(color)
            rgba[values == class_value, 3] = 220
        rgba[values == nodata, 3] = 0
        return rgba

    valid = np.isfinite(values) & (values != nodata)
    class_ids = np.digitize(values[valid], bins[1:-1], right=False)
    for idx, color in enumerate(colors):
        mask = np.zeros(values.shape, dtype=bool)
        mask[valid] = class_ids == idx
        rgba[mask, :3] = _hex_to_rgb(color)
        rgba[mask, 3] = 220
    return rgba


def _write_png(rgba, path):
    Image.fromarray(rgba, mode="RGBA").save(path)


def _export_susceptibility_overlay():
    with rasterio.open(CLASSIFIED_MAP) as src:
        values = src.read(1)
        _write_png(
            _classified_png(values, CLASS_NODATA, CLASS_COLORS),
            SUSCEPTIBILITY_OVERLAY,
        )
        return _raster_bounds(src)


def _load_risk_inputs():
    with rasterio.open(DYNAMIC_RISK_MAP) as risk_src:
        profile = risk_src.profile.copy()
        risk = risk_src.read(1).astype(np.float32)
        risk_bounds = _raster_bounds(risk_src)
        transform = risk_src.transform
        rows, cols = np.indices((risk_src.height, risk_src.width))
        xs = transform.c + (cols + 0.5) * transform.a
        ys = transform.f + (rows + 0.5) * transform.e

    susceptibility_path = os.path.join(MAPS_DIR, "susceptibility_map.tif")
    with rasterio.open(susceptibility_path) as src:
        susceptibility = src.read(1).astype(np.float32)
        valid_mask = np.isfinite(susceptibility)
        if src.nodata is not None:
            valid_mask &= susceptibility != src.nodata
        susceptibility = np.clip(susceptibility, 0.0, 1.0)

    rainfall = pd.read_csv(RAINFALL_POINTS_CSV)
    return profile, risk, risk_bounds, susceptibility, valid_mask, rainfall, xs, ys


def _interpolate_window_trigger(rainfall, xs, ys, window):
    if window == "combined":
        values = rainfall["rainfall_trigger_score"].to_numpy(dtype=float)
    else:
        column = f"rain_{window}_mm"
        threshold = RAINFALL_TRIGGER_THRESHOLDS[column]
        values = (rainfall[column] / threshold).clip(0.0, 1.0).to_numpy(dtype=float)

    points = rainfall[["longitude", "latitude"]].to_numpy()
    linear = griddata(points, values, (xs, ys), method="linear")
    nearest = griddata(points, values, (xs, ys), method="nearest")
    return np.where(np.isfinite(linear), linear, nearest).astype(np.float32)


def _export_risk_overlays():
    _, combined_risk, risk_bounds, susceptibility, valid_mask, rainfall, xs, ys = (
        _load_risk_inputs()
    )
    paths = {}
    bins = [0.0, 0.2, 0.4, 0.6, 0.8, 1.000001]

    for window in WINDOWS:
        if window == "combined":
            risk = combined_risk
        else:
            trigger = _interpolate_window_trigger(rainfall, xs, ys, window)
            risk = _calculate_dynamic_risk(susceptibility, valid_mask, trigger)
        path = RISK_OVERLAY_TEMPLATE.format(window=window)
        _write_png(_classified_png(risk, RISK_NODATA, RISK_COLORS, bins=bins), path)
        paths[window] = os.path.relpath(path, WEB_DIR).replace("\\", "/")

    return risk_bounds, paths


def _export_boundary():
    import geopandas as gpd

    boundary = gpd.read_file(BOUNDARY_SHP).to_crs("EPSG:4326")
    boundary.to_file(BOUNDARY_GEOJSON, driver="GeoJSON")


def _points_geojson(df, lon_col, lat_col, property_columns):
    features = []
    for _, row in df.iterrows():
        properties = {column: row[column] for column in property_columns}
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(row[lon_col]), float(row[lat_col])],
                },
                "properties": properties,
            }
        )
    return {"type": "FeatureCollection", "features": features}


def _export_points():
    landslides = pd.read_csv(CLEAN_LANDSLIDE_CSV)
    if len(landslides) > 1200:
        landslides = landslides.sample(1200, random_state=42)
    with open(LANDSLIDE_POINTS_GEOJSON, "w", encoding="utf-8") as handle:
        json.dump(
            _points_geojson(
                landslides,
                "longitude",
                "latitude",
                ["sample_id", "longitude", "latitude"],
            ),
            handle,
        )

    rainfall = pd.read_csv(RAINFALL_POINTS_CSV)
    with open(RAINFALL_POINTS_GEOJSON, "w", encoding="utf-8") as handle:
        json.dump(
            _points_geojson(
                rainfall,
                "longitude",
                "latitude",
                [
                    "rain_1h_mm",
                    "rain_3h_mm",
                    "rain_24h_mm",
                    "rain_72h_mm",
                    "current_rain_mm",
                    "latest_time",
                    "rainfall_trigger_score",
                ],
            ),
            handle,
        )


def _copy_report_figures():
    for figure in [
        "fig7_susceptibility_validation.png",
        "fig8_susceptibility_class_stats.png",
        "fig9_dynamic_landslide_risk.png",
    ]:
        src = os.path.join(FIGURES_DIR, figure)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(WEB_ASSET_DIR, figure))


def _table(path):
    return pd.read_csv(path).to_dict(orient="records")


def _write_app_data(susceptibility_bounds, risk_bounds, risk_overlay_paths):
    risk_summary = pd.read_csv(DYNAMIC_RISK_SUMMARY_CSV)
    rainfall = pd.read_csv(RAINFALL_POINTS_CSV)
    high_area = risk_summary.loc[
        risk_summary["risk_label"].isin(["High", "Severe"]), "area_percent"
    ].sum()
    severe_area = risk_summary.loc[
        risk_summary["risk_label"] == "Severe", "area_percent"
    ].sum()

    data = {
        "generatedAt": str(risk_summary.iloc[0]["generated_at"]),
        "rainfallLatestTime": str(rainfall["latest_time"].iloc[0]),
        "bounds": {
            "susceptibility": susceptibility_bounds,
            "risk": risk_bounds,
        },
        "overlays": {
            "susceptibility": os.path.relpath(SUSCEPTIBILITY_OVERLAY, WEB_DIR).replace(
                "\\", "/"
            ),
            "risk": risk_overlay_paths,
        },
        "cards": {
            "maxRain1h": float(rainfall["rain_1h_mm"].max()),
            "maxRain3h": float(rainfall["rain_3h_mm"].max()),
            "maxRain24h": float(rainfall["rain_24h_mm"].max()),
            "maxRain72h": float(rainfall["rain_72h_mm"].max()),
            "maxTrigger": float(rainfall["rainfall_trigger_score"].max()),
            "highSevereArea": float(high_area),
            "severeArea": float(severe_area),
        },
        "summaries": {
            "risk": _table(DYNAMIC_RISK_SUMMARY_CSV),
            "susceptibility": _table(CLASS_SUMMARY_CSV),
            "rainfall": rainfall.to_dict(orient="records"),
        },
    }

    with open(APP_DATA_JSON, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)


def export_web_app_assets(progress_callback=None):
    if progress_callback:
        progress_callback(82, "Ensuring web app export directories...")
    _ensure_dirs()
    
    if progress_callback:
        progress_callback(85, "Exporting static susceptibility overlay...")
    susceptibility_bounds = _export_susceptibility_overlay()
    
    if progress_callback:
        progress_callback(90, "Exporting dynamic warning risk overlays...")
    risk_bounds, risk_overlay_paths = _export_risk_overlays()
    
    if progress_callback:
        progress_callback(94, "Exporting region boundary layer...")
    _export_boundary()
    
    if progress_callback:
        progress_callback(96, "Exporting rainfall and landslide inventory point layers...")
    _export_points()
    
    if progress_callback:
        progress_callback(98, "Copying dynamic warning report figures...")
    _copy_report_figures()
    
    if progress_callback:
        progress_callback(99, "Writing dashboard configuration and state...")
    _write_app_data(susceptibility_bounds, risk_bounds, risk_overlay_paths)
    print(f"Web app assets exported to: {WEB_DIR}")
    
    if progress_callback:
        progress_callback(100, "Web app assets successfully exported.")



if __name__ == "__main__":
    export_web_app_assets()

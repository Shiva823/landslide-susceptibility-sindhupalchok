"""
Dynamic landslide warning map from live rainfall.

This module keeps the trained susceptibility map as a static terrain baseline
and updates a rainfall-triggered warning layer using Open-Meteo hourly rainfall.
"""

import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()  # load variables from .env

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap
import numpy as np
import pandas as pd
import rasterio
import requests
from scipy.interpolate import griddata

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import BOUNDARY_SHP, FIGURES_DIR, MAPS_DIR, SUSCEPTIBILITY_MAP
from src.validation import _load_boundary_lines


OPEN_METEO_URL = os.getenv("OPEN_METEO_URL", "https://api.open-meteo.com/v1/forecast")
LOCAL_TIMEZONE = "Asia/Kathmandu"

DYNAMIC_RISK_MAP = os.path.join(MAPS_DIR, "dynamic_landslide_risk_map.tif")
RAINFALL_POINTS_CSV = os.path.join(MAPS_DIR, "dynamic_rainfall_points.csv")
DYNAMIC_RISK_SUMMARY_CSV = os.path.join(MAPS_DIR, "dynamic_risk_summary.csv")
DYNAMIC_RISK_FIGURE = os.path.join(FIGURES_DIR, "fig9_dynamic_landslide_risk.png")
DYNAMIC_RISK_REPORT = os.path.join("reports", "dynamic_landslide_warning_summary.md")

RISK_LABELS = ["Low", "Guarded", "Moderate", "High", "Severe"]
RISK_COLORS = ["#2c7bb6", "#abd9e9", "#ffffbf", "#fdae61", "#d7191c"]
RISK_BINS = [0.0, 0.2, 0.4, 0.6, 0.8, 1.000001]
RISK_NODATA = -9999.0

RAINFALL_TRIGGER_THRESHOLDS = {
    "rain_1h_mm": 20.0,
    "rain_3h_mm": 40.0,
    "rain_24h_mm": 100.0,
    "rain_72h_mm": 180.0,
}


def _load_boundary_geometry():
    try:
        import geopandas as gpd
    except Exception as exc:
        raise ImportError("geopandas is required to sample rainfall points.") from exc

    if not os.path.exists(BOUNDARY_SHP):
        raise FileNotFoundError(f"Boundary shapefile not found: {BOUNDARY_SHP}")

    boundary = gpd.read_file(BOUNDARY_SHP).to_crs("EPSG:4326")
    return boundary.geometry.union_all()


def _make_rainfall_sample_points(count_per_axis=8):
    try:
        from shapely.geometry import Point
    except Exception as exc:
        raise ImportError("shapely is required to sample rainfall points.") from exc

    boundary = _load_boundary_geometry()
    minx, miny, maxx, maxy = boundary.bounds
    xs = np.linspace(minx, maxx, count_per_axis)
    ys = np.linspace(miny, maxy, count_per_axis)
    points = []

    for y in ys:
        for x in xs:
            point = Point(float(x), float(y))
            if boundary.contains(point):
                points.append({"longitude": float(x), "latitude": float(y)})

    centroid = boundary.centroid
    points.append({"longitude": float(centroid.x), "latitude": float(centroid.y)})
    return pd.DataFrame(points).drop_duplicates().reset_index(drop=True)


def _fetch_open_meteo_rainfall(points):
    params = {
        "latitude": ",".join(f"{value:.5f}" for value in points["latitude"]),
        "longitude": ",".join(f"{value:.5f}" for value in points["longitude"]),
        "hourly": "precipitation,rain",
        "current": "precipitation,rain",
        "past_days": 3,
        "forecast_days": 1,
        "timezone": LOCAL_TIMEZONE,
    }
    response = requests.get(OPEN_METEO_URL, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    if isinstance(data, dict):
        data = [data]
    return data


def _rainfall_totals_for_location(location):
    hourly = location.get("hourly", {})
    times = pd.to_datetime(hourly.get("time", []))
    precipitation = np.array(hourly.get("precipitation", []), dtype=float)
    current = location.get("current", {})

    if len(times) == 0 or len(precipitation) == 0:
        raise ValueError("Open-Meteo response did not include hourly rainfall.")

    valid = np.isfinite(precipitation)
    times = times[valid]
    precipitation = precipitation[valid]
    current_time = pd.to_datetime(
        current.get("time") or datetime.now(ZoneInfo(LOCAL_TIMEZONE)).isoformat()
    )
    if getattr(current_time, "tzinfo", None) is not None:
        current_time = current_time.tz_localize(None)

    past_or_current = times <= current_time
    if not past_or_current.any():
        raise ValueError("Open-Meteo response did not include rainfall up to current time.")
    times = times[past_or_current]
    precipitation = precipitation[past_or_current]

    totals = {}
    for hours in [1, 3, 24, 72]:
        window_start = current_time - pd.Timedelta(hours=hours)
        in_window = times > window_start
        totals[f"rain_{hours}h_mm"] = float(precipitation[in_window].sum())

    totals["current_rain_mm"] = float(current.get("rain", 0.0) or 0.0)
    totals["current_precipitation_mm"] = float(
        current.get("precipitation", totals["current_rain_mm"]) or 0.0
    )
    totals["latest_time"] = current_time.isoformat()
    return totals


def _build_rainfall_table():
    points = _make_rainfall_sample_points()
    locations = _fetch_open_meteo_rainfall(points)
    if len(locations) != len(points):
        raise ValueError(
            f"Expected {len(points)} Open-Meteo locations, received {len(locations)}."
        )

    rows = []
    for (_, point), location in zip(points.iterrows(), locations):
        row = point.to_dict()
        row.update(_rainfall_totals_for_location(location))
        rows.append(row)

    rainfall = pd.DataFrame(rows)
    trigger_components = []
    for column, threshold in RAINFALL_TRIGGER_THRESHOLDS.items():
        trigger_components.append((rainfall[column] / threshold).clip(0.0, 1.0))
    rainfall["rainfall_trigger_score"] = np.max(np.vstack(trigger_components), axis=0)
    rainfall.to_csv(RAINFALL_POINTS_CSV, index=False)
    return rainfall


def _interpolate_rainfall_trigger(rainfall, src):
    transform = src.transform
    rows, cols = np.indices((src.height, src.width))
    xs = transform.c + (cols + 0.5) * transform.a
    ys = transform.f + (rows + 0.5) * transform.e

    points = rainfall[["longitude", "latitude"]].to_numpy()
    values = rainfall["rainfall_trigger_score"].to_numpy(dtype=float)
    linear = griddata(points, values, (xs, ys), method="linear")
    nearest = griddata(points, values, (xs, ys), method="nearest")
    return np.where(np.isfinite(linear), linear, nearest).astype(np.float32)


def _calculate_dynamic_risk(susceptibility, valid_mask, rainfall_trigger):
    risk = np.full(susceptibility.shape, RISK_NODATA, dtype=np.float32)
    dynamic = (
        0.65 * susceptibility[valid_mask]
        + 0.35 * rainfall_trigger[valid_mask]
        + 0.25 * susceptibility[valid_mask] * rainfall_trigger[valid_mask]
    )
    risk[valid_mask] = np.clip(dynamic, 0.0, 1.0).astype(np.float32)
    return risk


def _write_risk_raster(risk, reference_profile):
    profile = reference_profile.copy()
    profile.update(dtype="float32", count=1, nodata=RISK_NODATA, compress="lzw")
    os.makedirs(os.path.dirname(DYNAMIC_RISK_MAP), exist_ok=True)
    with rasterio.open(DYNAMIC_RISK_MAP, "w", **profile) as dst:
        dst.write(risk, 1)


def _summarize_risk(risk, valid_mask, rainfall):
    valid_risk = risk[valid_mask]
    rows = []
    for label, lower, upper in zip(RISK_LABELS, RISK_BINS[:-1], RISK_BINS[1:]):
        class_mask = (valid_risk >= lower) & (valid_risk < upper)
        rows.append(
            {
                "risk_label": label,
                "risk_min": lower,
                "risk_max": min(upper, 1.0),
                "pixel_count": int(class_mask.sum()),
                "area_percent": float(class_mask.mean() * 100),
            }
        )

    summary = pd.DataFrame(rows)
    summary["generated_at"] = datetime.now(ZoneInfo(LOCAL_TIMEZONE)).isoformat()
    summary["max_rain_1h_mm"] = float(rainfall["rain_1h_mm"].max())
    summary["max_rain_3h_mm"] = float(rainfall["rain_3h_mm"].max())
    summary["max_rain_24h_mm"] = float(rainfall["rain_24h_mm"].max())
    summary["max_rain_72h_mm"] = float(rainfall["rain_72h_mm"].max())
    summary["max_trigger_score"] = float(rainfall["rainfall_trigger_score"].max())
    summary.to_csv(DYNAMIC_RISK_SUMMARY_CSV, index=False)
    return summary


def _plot_dynamic_risk_map(risk, valid_mask, rainfall, profile):
    os.makedirs(FIGURES_DIR, exist_ok=True)
    cmap = ListedColormap(RISK_COLORS)
    norm = BoundaryNorm(RISK_BINS, cmap.N)
    display = np.ma.masked_where(~valid_mask, risk)

    transform = profile["transform"]
    height = profile["height"]
    width = profile["width"]
    extent = [
        transform.c,
        transform.c + transform.a * width,
        transform.f + transform.e * height,
        transform.f,
    ]

    fig, ax = plt.subplots(figsize=(12, 10), facecolor="white")
    ax.imshow(display, cmap=cmap, norm=norm, extent=extent, interpolation="nearest")

    for x, y in _load_boundary_lines():
        ax.plot(x, y, color="black", linewidth=1.0, alpha=0.9)

    scatter = ax.scatter(
        rainfall["longitude"],
        rainfall["latitude"],
        s=80,
        c=rainfall["rainfall_trigger_score"],
        cmap="Blues",
        edgecolor="black",
        linewidth=0.8,
        vmin=0,
        vmax=1,
        label="Rainfall sample points",
    )
    fig.colorbar(scatter, ax=ax, shrink=0.72, label="Rainfall trigger score")

    patches = [
        mpatches.Patch(color=color, label=label)
        for color, label in zip(RISK_COLORS, RISK_LABELS)
    ]
    ax.legend(handles=patches, loc="lower left", frameon=True, framealpha=0.92)
    ax.set_title("Dynamic Landslide Warning Map from Live Rainfall", fontsize=14)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(DYNAMIC_RISK_FIGURE, dpi=180)
    plt.close(fig)


def _write_report(summary, rainfall):
    high_area = summary.loc[
        summary["risk_label"].isin(["High", "Severe"]), "area_percent"
    ].sum()
    severe_area = summary.loc[summary["risk_label"] == "Severe", "area_percent"].sum()

    os.makedirs(os.path.dirname(DYNAMIC_RISK_REPORT), exist_ok=True)
    with open(DYNAMIC_RISK_REPORT, "w", encoding="utf-8") as handle:
        handle.write("# Dynamic Landslide Warning Summary\n\n")
        handle.write("## Data Source\n\n")
        handle.write("- Rainfall API: Open-Meteo Forecast API\n")
        handle.write(f"- Rainfall sample points: `{RAINFALL_POINTS_CSV}`\n")
        handle.write(f"- Dynamic risk raster: `{DYNAMIC_RISK_MAP}`\n")
        handle.write(f"- Dynamic risk figure: `{DYNAMIC_RISK_FIGURE}`\n")
        handle.write(f"- Summary table: `{DYNAMIC_RISK_SUMMARY_CSV}`\n\n")
        handle.write("## Current Rainfall Signal\n\n")
        handle.write(f"- Max 1-hour rainfall: {rainfall['rain_1h_mm'].max():.1f} mm\n")
        handle.write(f"- Max 3-hour rainfall: {rainfall['rain_3h_mm'].max():.1f} mm\n")
        handle.write(f"- Max 24-hour rainfall: {rainfall['rain_24h_mm'].max():.1f} mm\n")
        handle.write(f"- Max 72-hour rainfall: {rainfall['rain_72h_mm'].max():.1f} mm\n")
        handle.write(
            f"- Max rainfall trigger score: "
            f"{rainfall['rainfall_trigger_score'].max():.3f}\n\n"
        )
        handle.write("## Dynamic Warning Area\n\n")
        handle.write(f"- High + Severe warning area: {high_area:.1f}%\n")
        handle.write(f"- Severe warning area: {severe_area:.1f}%\n\n")
        handle.write(
            "This is a dynamic warning layer. The terrain susceptibility map stays "
            "static, while the warning score changes when rainfall changes.\n"
        )


def generate_dynamic_landslide_risk_map(progress_callback=None):
    if not os.path.exists(SUSCEPTIBILITY_MAP):
        raise FileNotFoundError(
            "Susceptibility map is missing. Run: python main.py --step model"
        )

    if progress_callback:
        progress_callback(10, "Fetching live rainfall from Open-Meteo...")
    print("Fetching live rainfall from Open-Meteo...")
    rainfall = _build_rainfall_table()

    if progress_callback:
        progress_callback(30, "Combining rainfall trigger with susceptibility map...")
    print("Combining rainfall trigger with susceptibility map...")
    with rasterio.open(SUSCEPTIBILITY_MAP) as src:
        susceptibility = src.read(1).astype(np.float32)
        valid_mask = np.isfinite(susceptibility)
        if src.nodata is not None:
            valid_mask &= susceptibility != src.nodata
        susceptibility = np.clip(susceptibility, 0.0, 1.0)
        
        if progress_callback:
            progress_callback(40, "Interpolating rainfall trigger...")
        rainfall_trigger = _interpolate_rainfall_trigger(rainfall, src)
        
        if progress_callback:
            progress_callback(50, "Calculating dynamic risk...")
        risk = _calculate_dynamic_risk(susceptibility, valid_mask, rainfall_trigger)
        profile = src.profile.copy()
        profile["height"] = src.height
        profile["width"] = src.width

    if progress_callback:
        progress_callback(60, "Writing risk raster...")
    _write_risk_raster(risk, profile)
    
    if progress_callback:
        progress_callback(65, "Summarizing risk...")
    summary = _summarize_risk(risk, valid_mask, rainfall)

    if progress_callback:
        progress_callback(70, "Creating dynamic warning figure and report...")
    print("Creating dynamic warning figure and report...")
    _plot_dynamic_risk_map(risk, valid_mask, rainfall, profile)
    _write_report(summary, rainfall)

    high_area = summary.loc[
        summary["risk_label"].isin(["High", "Severe"]), "area_percent"
    ].sum()
    print("\nDynamic landslide warning complete")
    print(f"  Dynamic risk raster : {DYNAMIC_RISK_MAP}")
    print(f"  Dynamic risk figure : {DYNAMIC_RISK_FIGURE}")
    print(f"  Rainfall points     : {RAINFALL_POINTS_CSV}")
    print(f"  Warning summary     : {DYNAMIC_RISK_SUMMARY_CSV}")
    print(f"  High/Severe area    : {high_area:.1f}%")
    
    if progress_callback:
        progress_callback(80, "Dynamic warning calculations complete.")



if __name__ == "__main__":
    generate_dynamic_landslide_risk_map()

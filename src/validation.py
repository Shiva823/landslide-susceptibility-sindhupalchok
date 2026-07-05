"""
Susceptibility map validation and visualization.

Classifies the probability map into five susceptibility zones, samples known
landslide points against those zones, and creates report-ready outputs.
"""

import os
import sys

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
import numpy as np
import pandas as pd
import rasterio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import (
    BOUNDARY_SHP,
    CLEAN_LANDSLIDE_CSV,
    FIGURES_DIR,
    MAPS_DIR,
    SUSCEPTIBILITY_MAP,
)


CLASSIFIED_MAP = os.path.join(MAPS_DIR, "susceptibility_classes.tif")
CLASS_SUMMARY_CSV = os.path.join(MAPS_DIR, "susceptibility_class_summary.csv")
LANDSLIDE_VALIDATION_CSV = os.path.join(MAPS_DIR, "landslide_validation_points.csv")
VALIDATION_FIGURE = os.path.join(FIGURES_DIR, "fig7_susceptibility_validation.png")
VALIDATION_CHART = os.path.join(FIGURES_DIR, "fig8_susceptibility_class_stats.png")
VALIDATION_REPORT = os.path.join("reports", "susceptibility_validation_summary.md")

CLASS_BINS = [0.0, 0.2, 0.4, 0.6, 0.8, 1.000001]
CLASS_LABELS = ["Very Low", "Low", "Moderate", "High", "Very High"]
CLASS_COLORS = ["#2c7bb6", "#abd9e9", "#ffffbf", "#fdae61", "#d7191c"]
CLASS_VALUES = [1, 2, 3, 4, 5]
CLASS_NODATA = 0


def _summary_to_markdown(summary):
    columns = [
        "class_value",
        "class_label",
        "probability_min",
        "probability_max",
        "pixel_count",
        "area_percent",
        "landslide_count",
        "landslide_percent",
    ]
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join(["---"] * len(columns)) + " |"
    rows = []
    for _, row in summary[columns].iterrows():
        values = []
        for column in columns:
            value = row[column]
            if isinstance(value, float):
                value = f"{value:.3f}"
            values.append(str(value))
        rows.append("| " + " | ".join(values) + " |")
    return "\n".join([header, separator] + rows)


def _load_boundary_lines():
    if not os.path.exists(BOUNDARY_SHP):
        return []

    try:
        import fiona
        from shapely.geometry import shape
    except Exception:
        return []

    lines = []
    with fiona.open(BOUNDARY_SHP) as src:
        for feature in src:
            geom = shape(feature["geometry"])
            if geom.geom_type == "Polygon":
                lines.append(geom.exterior.xy)
            elif geom.geom_type == "MultiPolygon":
                for part in geom.geoms:
                    lines.append(part.exterior.xy)
    return lines


def _classify_array(probability, nodata):
    valid = np.isfinite(probability)
    if nodata is not None:
        valid &= probability != nodata

    classified = np.full(probability.shape, CLASS_NODATA, dtype=np.uint8)
    classified[valid] = np.digitize(probability[valid], CLASS_BINS[1:-1], right=False) + 1
    return classified, valid


def _write_classified_raster(classified, reference_profile):
    profile = reference_profile.copy()
    profile.update(dtype="uint8", count=1, nodata=CLASS_NODATA, compress="lzw")
    os.makedirs(os.path.dirname(CLASSIFIED_MAP), exist_ok=True)
    with rasterio.open(CLASSIFIED_MAP, "w", **profile) as dst:
        dst.write(classified, 1)


def _sample_landslide_points():
    df = pd.read_csv(CLEAN_LANDSLIDE_CSV)
    coords = list(zip(df["longitude"], df["latitude"]))

    with rasterio.open(SUSCEPTIBILITY_MAP) as prob_src:
        probability = np.array([value[0] for value in prob_src.sample(coords)], dtype=float)

    with rasterio.open(CLASSIFIED_MAP) as class_src:
        class_value = np.array([value[0] for value in class_src.sample(coords)], dtype=np.uint8)

    df_validation = df[["sample_id", "longitude", "latitude"]].copy()
    df_validation["susceptibility_probability"] = probability
    df_validation["susceptibility_class"] = class_value
    label_map = dict(zip(CLASS_VALUES, CLASS_LABELS))
    df_validation["susceptibility_label"] = df_validation["susceptibility_class"].map(label_map)
    df_validation = df_validation[df_validation["susceptibility_class"] != CLASS_NODATA].copy()
    df_validation.to_csv(LANDSLIDE_VALIDATION_CSV, index=False)
    return df_validation


def _build_summary(classified, valid_mask, df_validation):
    total_valid_pixels = int(valid_mask.sum())
    total_landslides = len(df_validation)
    rows = []

    for class_value, label, lower, upper in zip(
        CLASS_VALUES, CLASS_LABELS, CLASS_BINS[:-1], CLASS_BINS[1:]
    ):
        class_mask = classified == class_value
        pixel_count = int(class_mask.sum())
        landslide_count = int((df_validation["susceptibility_class"] == class_value).sum())
        rows.append(
            {
                "class_value": class_value,
                "class_label": label,
                "probability_min": lower,
                "probability_max": min(upper, 1.0),
                "pixel_count": pixel_count,
                "area_percent": (pixel_count / total_valid_pixels) * 100,
                "landslide_count": landslide_count,
                "landslide_percent": (
                    (landslide_count / total_landslides) * 100
                    if total_landslides else 0
                ),
            }
        )

    summary = pd.DataFrame(rows)
    summary.to_csv(CLASS_SUMMARY_CSV, index=False)
    return summary


def _plot_validation_map(probability, classified, valid_mask, df_validation, profile):
    os.makedirs(FIGURES_DIR, exist_ok=True)
    cmap = ListedColormap(CLASS_COLORS)
    norm = BoundaryNorm([0.5, 1.5, 2.5, 3.5, 4.5, 5.5], cmap.N)
    display = np.ma.masked_where(~valid_mask, classified)

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

    ax.scatter(
        df_validation["longitude"],
        df_validation["latitude"],
        s=7,
        c="black",
        alpha=0.45,
        linewidths=0,
        label="Landslide inventory",
    )

    patches = [
        mpatches.Patch(color=color, label=label)
        for color, label in zip(CLASS_COLORS, CLASS_LABELS)
    ]
    ax.legend(
        handles=patches + [mpatches.Patch(color="black", label="Landslide points")],
        loc="lower left",
        frameon=True,
        framealpha=0.92,
    )
    ax.set_title("Landslide Susceptibility Classes with Inventory Points", fontsize=14)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(VALIDATION_FIGURE, dpi=180)
    plt.close(fig)


def _plot_class_stats(summary):
    x = np.arange(len(summary))
    width = 0.38

    fig, ax = plt.subplots(figsize=(11, 6), facecolor="white")
    ax.bar(
        x - width / 2,
        summary["area_percent"],
        width,
        color="#6baed6",
        label="Map area %",
    )
    ax.bar(
        x + width / 2,
        summary["landslide_percent"],
        width,
        color="#e6550d",
        label="Landslide points %",
    )
    ax.set_xticks(x)
    ax.set_xticklabels(summary["class_label"], rotation=20, ha="right")
    ax.set_ylabel("Percent")
    ax.set_title("Area vs Landslide Distribution by Susceptibility Class")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(VALIDATION_CHART, dpi=180)
    plt.close(fig)


def _write_report(summary, df_validation):
    high_mask = summary["class_label"].isin(["High", "Very High"])
    high_landslide_pct = summary.loc[high_mask, "landslide_percent"].sum()
    high_area_pct = summary.loc[high_mask, "area_percent"].sum()
    mean_probability = df_validation["susceptibility_probability"].mean()

    os.makedirs(os.path.dirname(VALIDATION_REPORT), exist_ok=True)
    with open(VALIDATION_REPORT, "w", encoding="utf-8") as handle:
        handle.write("# Susceptibility Validation Summary\n\n")
        handle.write("## Outputs\n\n")
        handle.write(f"- Classified raster: `{CLASSIFIED_MAP}`\n")
        handle.write(f"- Validation map: `{VALIDATION_FIGURE}`\n")
        handle.write(f"- Class statistics chart: `{VALIDATION_CHART}`\n")
        handle.write(f"- Class summary table: `{CLASS_SUMMARY_CSV}`\n")
        handle.write(f"- Sampled landslide points: `{LANDSLIDE_VALIDATION_CSV}`\n\n")
        handle.write("## Key Findings\n\n")
        handle.write(
            f"- Mean predicted susceptibility at landslide points: "
            f"{mean_probability:.3f}\n"
        )
        handle.write(
            f"- High + Very High zones contain {high_landslide_pct:.1f}% of "
            f"cleaned landslide points.\n"
        )
        handle.write(
            f"- High + Very High zones cover {high_area_pct:.1f}% of valid map pixels.\n\n"
        )
        handle.write("## Class Summary\n\n")
        handle.write(_summary_to_markdown(summary))
        handle.write("\n")


def validate_susceptibility_map():
    if not os.path.exists(SUSCEPTIBILITY_MAP):
        raise FileNotFoundError(
            "Susceptibility map is missing. Run: python main.py --step model"
        )
    if not os.path.exists(CLEAN_LANDSLIDE_CSV):
        raise FileNotFoundError(
            "Clean landslide samples are missing. Run: python main.py --step preprocess"
        )

    print("Classifying susceptibility map...")
    with rasterio.open(SUSCEPTIBILITY_MAP) as src:
        probability = src.read(1).astype(float)
        classified, valid_mask = _classify_array(probability, src.nodata)
        reference_profile = src.profile.copy()
        reference_profile["height"] = src.height
        reference_profile["width"] = src.width

    _write_classified_raster(classified, reference_profile)

    print("Sampling landslide points against susceptibility classes...")
    df_validation = _sample_landslide_points()
    summary = _build_summary(classified, valid_mask, df_validation)

    print("Creating validation figures and report...")
    _plot_validation_map(probability, classified, valid_mask, df_validation, reference_profile)
    _plot_class_stats(summary)
    _write_report(summary, df_validation)

    high_landslide_pct = summary.loc[
        summary["class_label"].isin(["High", "Very High"]),
        "landslide_percent",
    ].sum()

    print("\nSusceptibility validation complete")
    print(f"  Classified raster      : {CLASSIFIED_MAP}")
    print(f"  Validation map figure  : {VALIDATION_FIGURE}")
    print(f"  Class stats chart      : {VALIDATION_CHART}")
    print(f"  Class summary CSV      : {CLASS_SUMMARY_CSV}")
    print(f"  Landslide validation   : {LANDSLIDE_VALIDATION_CSV}")
    print(f"  High/Very High capture : {high_landslide_pct:.1f}% of landslide points")


if __name__ == "__main__":
    validate_susceptibility_map()

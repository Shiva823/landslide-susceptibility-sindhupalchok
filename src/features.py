"""
Feature dataset builder.

Creates a balanced binary modelling table:
  landslide = 1  cleaned landslide inventory points
  landslide = 0  valid background/non-landslide raster pixels
"""

import os
import sys

import numpy as np
import pandas as pd
import rasterio
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import (
    CLEAN_LANDSLIDE_CSV,
    FEATURE_NAMES,
    RASTERS,
    RANDOM_SEED,
    TRAINING_CSV,
)
from src.preprocessing import DOMAIN_RULES, NODATA_SENTINELS


BACKGROUND_CSV = os.path.join(
    os.path.dirname(TRAINING_CSV), "background_non_landslide_samples.csv"
)
FEATURE_REPORT_CSV = os.path.join(
    os.path.dirname(TRAINING_CSV), "feature_build_report.csv"
)

MIN_LANDSLIDE_DISTANCE_DEGREES = 0.0009
MAX_BACKGROUND_ATTEMPTS = 100


def _clean_sampled_values(df):
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.replace(NODATA_SENTINELS, np.nan)
    df = df.dropna(subset=["longitude", "latitude"] + FEATURE_NAMES).copy()

    mask = pd.Series(True, index=df.index)
    for col, (lower, upper) in DOMAIN_RULES.items():
        if col in df.columns:
            mask &= df[col].between(lower, upper, inclusive="both")
    return df.loc[mask].copy()


def _sample_features_at_coords(coords):
    sampled = {
        "longitude": [coord[0] for coord in coords],
        "latitude": [coord[1] for coord in coords],
    }

    for feature, path in RASTERS.items():
        with rasterio.open(path) as src:
            values = np.array([value[0] for value in src.sample(coords)], dtype=float)
            nodata = src.nodata
            if nodata is not None:
                values[np.isclose(values, nodata, equal_nan=False)] = np.nan
        sampled[feature] = values

    return _clean_sampled_values(pd.DataFrame(sampled))


def _candidate_background_coords(rng, batch_size):
    reference_path = RASTERS["Slope"]
    with rasterio.open(reference_path) as src:
        arr = src.read(1).astype(float)
        nodata = src.nodata
        valid = np.isfinite(arr)
        if nodata is not None:
            valid &= ~np.isclose(arr, nodata, equal_nan=False)

        rows, cols = np.where(valid)
        choices = rng.choice(len(rows), size=min(batch_size, len(rows)), replace=False)
        selected_rows = rows[choices]
        selected_cols = cols[choices]
        xs, ys = rasterio.transform.xy(
            src.transform, selected_rows, selected_cols, offset="center"
        )

    return list(zip(xs, ys))


def _build_background_samples(landslide_df, n_samples):
    rng = np.random.default_rng(RANDOM_SEED)
    landslide_tree = cKDTree(landslide_df[["longitude", "latitude"]].to_numpy())
    collected = []
    seen = set()
    batch_size = max(n_samples * 4, 1000)

    for _ in range(MAX_BACKGROUND_ATTEMPTS):
        coords = _candidate_background_coords(rng, batch_size)
        if not coords:
            continue

        distances, _ = landslide_tree.query(np.array(coords), k=1)
        coords = [
            coord for coord, dist in zip(coords, distances)
            if dist > MIN_LANDSLIDE_DISTANCE_DEGREES
        ]
        coords = [coord for coord in coords if coord not in seen]
        for coord in coords:
            seen.add(coord)

        sampled = _sample_features_at_coords(coords)
        collected.append(sampled)
        background_df = pd.concat(collected, ignore_index=True)
        background_df = background_df.drop_duplicates(subset=["longitude", "latitude"])
        if len(background_df) >= n_samples:
            background_df = background_df.sample(
                n=n_samples, random_state=RANDOM_SEED
            ).reset_index(drop=True)
            background_df["sample_id"] = [
                f"bg_{idx}" for idx in range(len(background_df))
            ]
            background_df["landslide"] = 0
            return background_df[["sample_id", "longitude", "latitude"] + FEATURE_NAMES + ["landslide"]]

    raise RuntimeError(
        f"Could not collect {n_samples} valid background samples after "
        f"{MAX_BACKGROUND_ATTEMPTS} attempts."
    )


def build_features():
    if not os.path.exists(CLEAN_LANDSLIDE_CSV):
        raise FileNotFoundError(
            "Clean landslide samples are missing. Run: python main.py --step preprocess"
        )

    print("Building balanced binary feature dataset...")
    landslide_df = pd.read_csv(CLEAN_LANDSLIDE_CSV)
    landslide_df = landslide_df[["sample_id", "longitude", "latitude"] + FEATURE_NAMES + ["landslide"]]
    landslide_df["landslide"] = 1

    background_df = _build_background_samples(landslide_df, len(landslide_df))
    training_df = pd.concat([landslide_df, background_df], ignore_index=True)
    training_df = training_df.sample(frac=1.0, random_state=RANDOM_SEED).reset_index(drop=True)

    os.makedirs(os.path.dirname(TRAINING_CSV), exist_ok=True)
    background_df.to_csv(BACKGROUND_CSV, index=False)
    training_df.to_csv(TRAINING_CSV, index=False)

    report = pd.DataFrame(
        [
            {"metric": "clean_landslide_samples", "value": len(landslide_df)},
            {"metric": "background_samples", "value": len(background_df)},
            {"metric": "total_training_rows", "value": len(training_df)},
            {
                "metric": "min_background_distance_degrees",
                "value": MIN_LANDSLIDE_DISTANCE_DEGREES,
            },
            {"metric": "random_seed", "value": RANDOM_SEED},
        ]
    )
    report.to_csv(FEATURE_REPORT_CSV, index=False)

    print("\nFeature dataset complete")
    print(f"  Landslide rows        : {len(landslide_df):,}")
    print(f"  Background rows       : {len(background_df):,}")
    print(f"  Training rows         : {len(training_df):,}")
    print(f"  Training CSV          : {TRAINING_CSV}")
    print(f"  Background audit CSV  : {BACKGROUND_CSV}")
    print(f"  Feature report CSV    : {FEATURE_REPORT_CSV}")


if __name__ == "__main__":
    build_features()

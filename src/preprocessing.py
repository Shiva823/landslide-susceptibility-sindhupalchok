"""
Data preprocessing for the Sindhupalchok landslide project.

This module turns the raw landslide inventory plus raster covariates into a
clean, training-ready point dataset. Raw source files are never modified.
"""

import os
import sys
from dataclasses import dataclass

import numpy as np
import pandas as pd
import rasterio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import CLEAN_LANDSLIDE_CSV, FEATURE_NAMES, LANDSLIDE_CSV, RASTERS


CLEANING_REPORT_CSV = os.path.join(
    os.path.dirname(CLEAN_LANDSLIDE_CSV), "preprocessing_cleaning_report.csv"
)
REMOVED_ROWS_CSV = os.path.join(
    os.path.dirname(CLEAN_LANDSLIDE_CSV), "removed_landslide_samples.csv"
)

CONTINUOUS_OUTLIER_FEATURES = [
    "Slope",
    "Elevation",
    "NDVI",
    "Rainfall",
    "River Proximity",
    "Road Proximity",
    "TWI",
]

DOMAIN_RULES = {
    "longitude": (80.0, 90.0),
    "latitude": (25.0, 31.0),
    "Slope": (0.0, 90.0),
    "Elevation": (0.0, 9000.0),
    "Aspect": (0.0, 360.0),
    "NDVI": (-1.0, 1.0),
    "Rainfall": (0.0, np.inf),
    "River Proximity": (0.0, np.inf),
    "Road Proximity": (0.0, np.inf),
    "TWI": (0.0, np.inf),
}

NODATA_SENTINELS = [-9999.0, -32768.0, 3.4028235e38, -3.4028235e38]


@dataclass
class CleaningStep:
    step: str
    rows_before: int
    rows_after: int
    rows_removed: int
    detail: str


def _record_step(steps, step, before, after, detail):
    steps.append(
        CleaningStep(
            step=step,
            rows_before=before,
            rows_after=after,
            rows_removed=before - after,
            detail=detail,
        )
    )


def _load_inventory():
    df = pd.read_csv(LANDSLIDE_CSV)
    df["sample_id"] = np.arange(len(df))
    return df


def _sample_rasters(df):
    sampled = {
        "sample_id": df["sample_id"].values,
        "longitude": df["longitude"].values,
        "latitude": df["latitude"].values,
    }

    coords = list(zip(df["longitude"], df["latitude"]))
    for feature, path in RASTERS.items():
        if not os.path.exists(path):
            raise FileNotFoundError(f"Missing raster for {feature}: {path}")

        with rasterio.open(path) as src:
            values = np.array([value[0] for value in src.sample(coords)], dtype=float)
            nodata = src.nodata
            if nodata is not None:
                values[np.isclose(values, nodata, equal_nan=False)] = np.nan
        sampled[feature] = values

    df_sample = pd.DataFrame(sampled)
    df_sample = df_sample.replace([np.inf, -np.inf], np.nan)
    df_sample = df_sample.replace(NODATA_SENTINELS, np.nan)
    return df_sample


def _apply_domain_rules(df):
    invalid_reasons = pd.Series("", index=df.index, dtype=object)
    valid_mask = pd.Series(True, index=df.index)

    for col, (lower, upper) in DOMAIN_RULES.items():
        if col not in df.columns:
            continue
        col_mask = df[col].between(lower, upper, inclusive="both") | df[col].isna()
        invalid_reasons.loc[~col_mask] += f"{col}_outside_domain;"
        valid_mask &= col_mask

    return valid_mask, invalid_reasons


def _iqr_bounds(series):
    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1
    return q1 - 1.5 * iqr, q3 + 1.5 * iqr, q1, q3, iqr


def _apply_iqr_outlier_rules(df):
    outlier_reasons = pd.Series("", index=df.index, dtype=object)
    keep_mask = pd.Series(True, index=df.index)
    bounds = []

    for feature in CONTINUOUS_OUTLIER_FEATURES:
        values = df[feature].dropna()
        lower, upper, q1, q3, iqr = _iqr_bounds(values)
        feature_mask = df[feature].between(lower, upper, inclusive="both")
        outlier_reasons.loc[~feature_mask] += f"{feature}_iqr_outlier;"
        keep_mask &= feature_mask
        bounds.append(
            {
                "feature": feature,
                "q1": q1,
                "q3": q3,
                "iqr": iqr,
                "lower_bound": lower,
                "upper_bound": upper,
                "outliers": int((~feature_mask).sum()),
            }
        )

    return keep_mask, outlier_reasons, pd.DataFrame(bounds)


def run_preprocessing():
    print("Loading landslide inventory and raster predictors...")
    steps = []
    raw_df = _load_inventory()

    before = len(raw_df)
    df_unique = raw_df.drop_duplicates(subset=["longitude", "latitude"]).copy()
    _record_step(
        steps,
        "duplicate_coordinate_removal",
        before,
        len(df_unique),
        "Dropped exact duplicate longitude/latitude pairs.",
    )

    sampled_df = _sample_rasters(df_unique)

    before = len(sampled_df)
    required_cols = ["longitude", "latitude"] + FEATURE_NAMES
    missing_mask = sampled_df[required_cols].isna().any(axis=1)
    missing_removed = sampled_df.loc[missing_mask].copy()
    missing_removed["removal_reason"] = "missing_or_nodata_raster_value"
    working_df = sampled_df.loc[~missing_mask].copy()
    _record_step(
        steps,
        "missing_value_removal",
        before,
        len(working_df),
        "Dropped rows with missing/NoData values in any required feature.",
    )

    before = len(working_df)
    domain_mask, domain_reasons = _apply_domain_rules(working_df)
    domain_removed = working_df.loc[~domain_mask].copy()
    domain_removed["removal_reason"] = domain_reasons.loc[~domain_mask].str.rstrip(";")
    working_df = working_df.loc[domain_mask].copy()
    _record_step(
        steps,
        "domain_rule_filtering",
        before,
        len(working_df),
        "Applied physical bounds for coordinates and raster feature values.",
    )

    before = len(working_df)
    outlier_mask, outlier_reasons, outlier_bounds = _apply_iqr_outlier_rules(working_df)
    outlier_removed = working_df.loc[~outlier_mask].copy()
    outlier_removed["removal_reason"] = outlier_reasons.loc[~outlier_mask].str.rstrip(";")
    clean_df = working_df.loc[outlier_mask].copy()
    _record_step(
        steps,
        "eda_iqr_outlier_removal",
        before,
        len(clean_df),
        "Removed 1.5*IQR outliers for continuous non-circular EDA features only.",
    )

    clean_df = clean_df[["sample_id", "longitude", "latitude"] + FEATURE_NAMES]
    clean_df["landslide"] = 1

    removed_df = pd.concat(
        [missing_removed, domain_removed, outlier_removed],
        ignore_index=True,
        sort=False,
    )

    os.makedirs(os.path.dirname(CLEAN_LANDSLIDE_CSV), exist_ok=True)
    clean_df.to_csv(CLEAN_LANDSLIDE_CSV, index=False)
    removed_df.to_csv(REMOVED_ROWS_CSV, index=False)

    report_df = pd.DataFrame([step.__dict__ for step in steps])
    bounds_rows = outlier_bounds.assign(
        step="eda_iqr_outlier_bounds",
        rows_before="",
        rows_after="",
        rows_removed="",
        detail="Feature-specific 1.5*IQR thresholds calculated after missing/domain cleaning.",
    )
    report_df.to_csv(CLEANING_REPORT_CSV, index=False)
    bounds_rows.to_csv(
        os.path.join(
            os.path.dirname(CLEAN_LANDSLIDE_CSV),
            "preprocessing_outlier_bounds.csv",
        ),
        index=False,
    )

    print("\nPreprocessing complete")
    print(f"  Raw landslide rows       : {len(raw_df):,}")
    print(f"  Clean landslide rows     : {len(clean_df):,}")
    print(f"  Removed rows             : {len(removed_df):,}")
    print(f"  Clean landslide CSV      : {CLEAN_LANDSLIDE_CSV}")
    print(f"  Removed-row audit CSV    : {REMOVED_ROWS_CSV}")
    print(f"  Cleaning report CSV      : {CLEANING_REPORT_CSV}")


if __name__ == "__main__":
    run_preprocessing()

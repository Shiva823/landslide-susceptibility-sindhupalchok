"""
Model training and susceptibility map generation.

Trains Random Forest, SVM, and Logistic Regression on the cleaned feature table,
selects the best model by test ROC-AUC, and writes a probability raster.
"""

import os
import sys

import joblib
import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import Resampling, reproject
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.svm import SVC

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import (
    BEST_MODEL_PKL,
    FEATURE_NAMES,
    MODELS_DIR,
    RANDOM_SEED,
    RASTERS,
    SUSCEPTIBILITY_MAP,
    TEST_SIZE,
    TRAINING_CSV,
)
from src.preprocessing import DOMAIN_RULES, NODATA_SENTINELS


TRAIN_SPLIT_CSV = os.path.join(os.path.dirname(TRAINING_CSV), "train_split.csv")
TEST_SPLIT_CSV = os.path.join(os.path.dirname(TRAINING_CSV), "test_split.csv")
METRICS_CSV = os.path.join(MODELS_DIR, "model_metrics.csv")
CONFUSION_CSV = os.path.join(MODELS_DIR, "confusion_matrices.csv")
FEATURE_IMPORTANCE_CSV = os.path.join(MODELS_DIR, "feature_importance.csv")
MODEL_SUMMARY_TXT = os.path.join(MODELS_DIR, "model_summary.txt")

ASPECT_ENGINEERED_COLUMNS = ["Aspect_sin", "Aspect_cos"]
MODEL_FEATURES = [
    "Slope",
    "Elevation",
    "Aspect_sin",
    "Aspect_cos",
    "NDVI",
    "LULC",
    "Rainfall",
    "River Proximity",
    "Road Proximity",
    "TWI",
]
CATEGORICAL_FEATURES = ["LULC"]
NUMERIC_FEATURES = [col for col in MODEL_FEATURES if col not in CATEGORICAL_FEATURES]
MAP_NODATA = -9999.0


def _add_engineered_features(df):
    engineered = df.copy()
    radians = np.deg2rad(engineered["Aspect"].astype(float))
    engineered["Aspect_sin"] = np.sin(radians)
    engineered["Aspect_cos"] = np.cos(radians)
    return engineered


def _build_preprocessor(scale_numeric):
    numeric_transformer = StandardScaler() if scale_numeric else "passthrough"
    return ColumnTransformer(
        transformers=[
            ("numeric", numeric_transformer, NUMERIC_FEATURES),
            (
                "lulc",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                CATEGORICAL_FEATURES,
            ),
        ]
    )


def _build_models():
    return {
        "Random Forest": Pipeline(
            steps=[
                ("preprocess", _build_preprocessor(scale_numeric=False)),
                (
                    "classifier",
                    RandomForestClassifier(
                        n_estimators=300,
                        max_depth=None,
                        min_samples_leaf=2,
                        class_weight="balanced",
                        random_state=RANDOM_SEED,
                        n_jobs=-1,
                    ),
                ),
            ]
        ),
        "SVM": Pipeline(
            steps=[
                ("preprocess", _build_preprocessor(scale_numeric=True)),
                (
                    "classifier",
                    CalibratedClassifierCV(
                        estimator=SVC(
                            kernel="rbf",
                            C=2.0,
                            gamma="scale",
                            class_weight="balanced",
                            random_state=RANDOM_SEED,
                        ),
                        method="sigmoid",
                        cv=3,
                        ensemble=False,
                    ),
                ),
            ]
        ),
        "Logistic Regression": Pipeline(
            steps=[
                ("preprocess", _build_preprocessor(scale_numeric=True)),
                (
                    "classifier",
                    LogisticRegression(
                        max_iter=2000,
                        class_weight="balanced",
                        random_state=RANDOM_SEED,
                    ),
                ),
            ]
        ),
    }


def _load_training_data():
    if not os.path.exists(TRAINING_CSV):
        raise FileNotFoundError(
            "Training dataset is missing. Run: python main.py --step features"
        )
    df = pd.read_csv(TRAINING_CSV)
    required = ["sample_id", "longitude", "latitude", "landslide"] + FEATURE_NAMES
    missing_cols = [col for col in required if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Training dataset is missing columns: {missing_cols}")

    df = _add_engineered_features(df)
    df = df.dropna(subset=MODEL_FEATURES + ["landslide"]).copy()
    return df


def _evaluate_model(name, model, x_train, y_train, x_test, y_test):
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_SEED)
    cv_auc = cross_val_score(model, x_train, y_train, cv=cv, scoring="roc_auc")

    model.fit(x_train, y_train)
    y_pred = model.predict(x_test)
    y_prob = model.predict_proba(x_test)[:, 1]
    tn, fp, fn, tp = confusion_matrix(y_test, y_pred).ravel()

    metrics = {
        "model": name,
        "train_rows": len(x_train),
        "test_rows": len(x_test),
        "cv_roc_auc_mean": cv_auc.mean(),
        "cv_roc_auc_std": cv_auc.std(),
        "test_accuracy": accuracy_score(y_test, y_pred),
        "test_precision": precision_score(y_test, y_pred, zero_division=0),
        "test_recall": recall_score(y_test, y_pred, zero_division=0),
        "test_f1": f1_score(y_test, y_pred, zero_division=0),
        "test_roc_auc": roc_auc_score(y_test, y_prob),
    }
    confusion = {
        "model": name,
        "true_negative": tn,
        "false_positive": fp,
        "false_negative": fn,
        "true_positive": tp,
    }
    return metrics, confusion, model


def _extract_feature_importance(best_model, best_name):
    preprocessor = best_model.named_steps["preprocess"]
    feature_names = preprocessor.get_feature_names_out()
    classifier = best_model.named_steps["classifier"]

    if hasattr(classifier, "feature_importances_"):
        values = classifier.feature_importances_
        kind = "feature_importance"
    elif hasattr(classifier, "coef_"):
        values = np.abs(classifier.coef_[0])
        kind = "absolute_coefficient"
    else:
        return pd.DataFrame()

    return pd.DataFrame(
        {
            "model": best_name,
            "feature": feature_names,
            "importance_type": kind,
            "importance": values,
        }
    ).sort_values("importance", ascending=False)


def _read_feature_on_reference_grid(feature, path, reference_profile):
    with rasterio.open(path) as src:
        source = src.read(1).astype(np.float32)
        source = np.where(np.isfinite(source), source, np.nan)
        for sentinel in NODATA_SENTINELS:
            source[np.isclose(source, sentinel, equal_nan=False)] = np.nan
        if src.nodata is not None:
            source[np.isclose(source, src.nodata, equal_nan=False)] = np.nan

        destination = np.full(
            (reference_profile["height"], reference_profile["width"]),
            np.nan,
            dtype=np.float32,
        )
        resampling = Resampling.nearest if feature == "LULC" else Resampling.bilinear
        reproject(
            source=source,
            destination=destination,
            src_transform=src.transform,
            src_crs=src.crs,
            src_nodata=np.nan,
            dst_transform=reference_profile["transform"],
            dst_crs=reference_profile["crs"],
            dst_nodata=np.nan,
            resampling=resampling,
        )
    return destination


def _valid_prediction_mask(feature_arrays):
    valid = np.ones(next(iter(feature_arrays.values())).shape, dtype=bool)
    for feature, values in feature_arrays.items():
        valid &= np.isfinite(values)
        if feature in DOMAIN_RULES:
            lower, upper = DOMAIN_RULES[feature]
            valid &= values >= lower
            valid &= values <= upper
    return valid


def _generate_susceptibility_map(model):
    reference_path = RASTERS["Slope"]
    os.makedirs(os.path.dirname(SUSCEPTIBILITY_MAP), exist_ok=True)

    with rasterio.open(reference_path) as ref:
        reference_profile = {
            "height": ref.height,
            "width": ref.width,
            "transform": ref.transform,
            "crs": ref.crs,
        }
        profile = ref.profile.copy()
        profile.update(dtype="float32", count=1, nodata=MAP_NODATA, compress="lzw")

        feature_arrays = {
            feature: _read_feature_on_reference_grid(feature, path, reference_profile)
            for feature, path in RASTERS.items()
        }
        valid_mask = _valid_prediction_mask(feature_arrays)
        susceptibility = np.full(ref.shape, MAP_NODATA, dtype=np.float32)
        valid_rows, valid_cols = np.where(valid_mask)
        chunk_size = 250_000

        for start in range(0, len(valid_rows), chunk_size):
            stop = min(start + chunk_size, len(valid_rows))
            rows = valid_rows[start:stop]
            cols = valid_cols[start:stop]
            chunk = pd.DataFrame(
                {feature: values[rows, cols] for feature, values in feature_arrays.items()}
            )
            chunk = _add_engineered_features(chunk)
            probabilities = model.predict_proba(chunk[MODEL_FEATURES])[:, 1]
            susceptibility[rows, cols] = probabilities.astype(np.float32)

        with rasterio.open(SUSCEPTIBILITY_MAP, "w", **profile) as dst:
            dst.write(susceptibility, 1)

    return SUSCEPTIBILITY_MAP


def train_models():
    print("Loading model-ready feature table...")
    df = _load_training_data()
    x = df[MODEL_FEATURES]
    y = df["landslide"].astype(int)

    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=TEST_SIZE,
        random_state=RANDOM_SEED,
        stratify=y,
    )

    train_export = df.loc[x_train.index, ["sample_id", "longitude", "latitude"] + MODEL_FEATURES + ["landslide"]]
    test_export = df.loc[x_test.index, ["sample_id", "longitude", "latitude"] + MODEL_FEATURES + ["landslide"]]
    train_export.to_csv(TRAIN_SPLIT_CSV, index=False)
    test_export.to_csv(TEST_SPLIT_CSV, index=False)

    print(f"  Train rows: {len(x_train):,}")
    print(f"  Test rows : {len(x_test):,}")

    os.makedirs(MODELS_DIR, exist_ok=True)
    metrics_rows = []
    confusion_rows = []
    fitted_models = {}

    for name, model in _build_models().items():
        print(f"  Training {name}...")
        metrics, confusion, fitted = _evaluate_model(
            name, model, x_train, y_train, x_test, y_test
        )
        metrics_rows.append(metrics)
        confusion_rows.append(confusion)
        fitted_models[name] = fitted
        print(
            f"    ROC-AUC={metrics['test_roc_auc']:.3f} "
            f"F1={metrics['test_f1']:.3f}"
        )

    metrics_df = pd.DataFrame(metrics_rows).sort_values("test_roc_auc", ascending=False)
    confusion_df = pd.DataFrame(confusion_rows)
    best_name = metrics_df.iloc[0]["model"]
    best_model = fitted_models[best_name]

    artifact = {
        "model_name": best_name,
        "model": best_model,
        "model_features": MODEL_FEATURES,
        "raw_features": FEATURE_NAMES,
        "test_size": TEST_SIZE,
        "random_seed": RANDOM_SEED,
        "metrics": metrics_df.to_dict(orient="records"),
    }
    joblib.dump(artifact, BEST_MODEL_PKL)

    metrics_df.to_csv(METRICS_CSV, index=False)
    confusion_df.to_csv(CONFUSION_CSV, index=False)

    importance_df = _extract_feature_importance(best_model, best_name)
    if not importance_df.empty:
        importance_df.to_csv(FEATURE_IMPORTANCE_CSV, index=False)

    print("  Generating susceptibility probability map...")
    map_path = _generate_susceptibility_map(best_model)

    with open(MODEL_SUMMARY_TXT, "w", encoding="utf-8") as handle:
        handle.write("Landslide susceptibility model summary\n")
        handle.write(f"Best model: {best_name}\n")
        handle.write(f"Train rows: {len(x_train)}\n")
        handle.write(f"Test rows: {len(x_test)}\n")
        handle.write(f"Best model pickle: {BEST_MODEL_PKL}\n")
        handle.write(f"Susceptibility map: {map_path}\n\n")
        handle.write(metrics_df.to_string(index=False))

    print("\nModel training complete")
    print(f"  Best model           : {best_name}")
    print(f"  Metrics CSV          : {METRICS_CSV}")
    print(f"  Train split CSV      : {TRAIN_SPLIT_CSV}")
    print(f"  Test split CSV       : {TEST_SPLIT_CSV}")
    print(f"  Best model pickle    : {BEST_MODEL_PKL}")
    print(f"  Susceptibility map   : {map_path}")


if __name__ == "__main__":
    train_models()

# Modeling Summary

## Dataset Split

- Source dataset: `data/processed/landslide_inventory/training_dataset.csv`
- Total rows: 2,218
- Train rows: 1,774
- Test rows: 444
- Split method: stratified 80/20 split
- Train class balance: 887 non-landslide, 887 landslide
- Test class balance: 222 non-landslide, 222 landslide

## Feature Engineering Used For Modeling

- Raw predictors: Slope, Elevation, Aspect, NDVI, LULC, Rainfall, River Proximity, Road Proximity, TWI
- Aspect was converted to `Aspect_sin` and `Aspect_cos` because aspect is circular.
- LULC was one-hot encoded because it is categorical.
- Numeric features were scaled for SVM and Logistic Regression.
- Random Forest used unscaled numeric features.

## Model Results

| Model | Test ROC-AUC | Accuracy | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|
| Random Forest | 0.924 | 0.860 | 0.828 | 0.910 | 0.867 |
| SVM | 0.921 | 0.851 | 0.822 | 0.896 | 0.858 |
| Logistic Regression | 0.871 | 0.795 | 0.789 | 0.806 | 0.797 |

Best model: Random Forest

## Key Outputs

- Train split: `data/processed/landslide_inventory/train_split.csv`
- Test split: `data/processed/landslide_inventory/test_split.csv`
- Metrics: `outputs/models/model_metrics.csv`
- Confusion matrices: `outputs/models/confusion_matrices.csv`
- Feature importance: `outputs/models/feature_importance.csv`
- Best model: `outputs/models/best_model.pkl`
- Susceptibility map: `outputs/maps/susceptibility_map.tif`

## Susceptibility Map

- CRS: EPSG:4326
- Shape: 2167 rows x 2313 columns
- Valid predicted pixels: 3,120,766
- Probability range: 0.000 to 0.999
- Mean susceptibility probability: 0.250

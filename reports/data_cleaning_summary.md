# Data Cleaning Summary

## What the EDA showed

- The raster stack is usable, but most district-masked rasters have about 37-38% NoData outside the study area.
- The landslide inventory has 1,434 raw points and no duplicate longitude/latitude pairs.
- Sampling rasters at landslide locations produced 1,429 complete points; 5 points touched missing/NoData raster cells.
- Boxplots showed outliers in several continuous predictors, especially rainfall, road proximity, elevation, TWI, slope, and river proximity.
- Aspect was treated as circular, not linear. LULC was treated as categorical, not numeric.

## Cleaning decisions

- Kept raw inventory and rasters unchanged.
- Removed rows with any missing/NoData required raster value.
- Enforced physical/domain ranges for coordinates and feature values.
- Removed 1.5*IQR outliers for continuous non-circular features only:
  Slope, Elevation, NDVI, Rainfall, River Proximity, Road Proximity, and TWI.
- Did not remove LULC classes as outliers because class codes are categories.
- Did not remove Aspect outliers because 0 and 360 degrees are adjacent directions.

## Results

- Raw landslide rows: 1,434
- Clean landslide rows: 1,109
- Removed rows: 325
- Final balanced training rows: 2,218
- Landslide class rows: 1,109
- Background class rows: 1,109

## Output files

- `data/processed/landslide_inventory/clean_landslide_samples.csv`
- `data/processed/landslide_inventory/removed_landslide_samples.csv`
- `data/processed/landslide_inventory/preprocessing_cleaning_report.csv`
- `data/processed/landslide_inventory/preprocessing_outlier_bounds.csv`
- `data/processed/landslide_inventory/background_non_landslide_samples.csv`
- `data/processed/landslide_inventory/feature_build_report.csv`
- `data/processed/landslide_inventory/training_dataset.csv`

## Next step

Use `training_dataset.csv` for model training. The next missing pipeline piece is
`src/model.py`, which should train and compare Random Forest, SVM, and Logistic
Regression, then save the best model to `outputs/models/`.

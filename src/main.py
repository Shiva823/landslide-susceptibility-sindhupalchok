import numpy as np
import pandas as pd
import rasterio
import os

# ==========================
# Create output folders
# ==========================

os.makedirs("../processed", exist_ok=True)

# ==========================
# Load inventory CSV
# ==========================

inventory = pd.read_csv(
    "../data/raw/Inventory_datasets/sindhupalchowk_landslides (1).csv"
)

inventory = inventory[['longitude', 'latitude']]

# ==========================
# Open raster files
# ==========================

aspect   = rasterio.open("../data/raw/DEM/Sindhupalchok_Aspect.tif")
dem      = rasterio.open("../data/raw/DEM/Sindhupalchok_DEM.tif")
slope    = rasterio.open("../data/raw/Slope/Sindhupalchok_Slope.tif")
lulc     = rasterio.open("../data/raw/LULC/Sindhupalchok_LULC_30m.tif")
ndvi     = rasterio.open("../data/raw/NDVI/Sindhupalchok_NDVI_2025_30m.tif")
rainfall = rasterio.open("../data/raw/rainfall/Sindhupalchok_Rainfall_Raster.tif")
twi      = rasterio.open("../data/raw/TWI/Sindhupalchok_TWI_2025.tif")
river    = rasterio.open("../data/raw/RoadAndriver/Sindhupalchok_RiverProximity.tif")
road     = rasterio.open("../data/raw/RoadAndriver/Sindhupalchok_RoadProximity.tif")

# ==========================
# Sample raster values
# ==========================

coords = list(zip(inventory["longitude"], inventory["latitude"]))

inventory["Aspect"]   = [x[0] for x in aspect.sample(coords)]
inventory["DEM"]      = [x[0] for x in dem.sample(coords)]
inventory["Slope"]    = [x[0] for x in slope.sample(coords)]
inventory["LULC"]     = [x[0] for x in lulc.sample(coords)]
inventory["NDVI"]     = [x[0] for x in ndvi.sample(coords)]
inventory["Rainfall"] = [x[0] for x in rainfall.sample(coords)]
inventory["TWI"]      = [x[0] for x in twi.sample(coords)]
inventory["River"]    = [x[0] for x in river.sample(coords)]
inventory["Road"]     = [x[0] for x in road.sample(coords)]

print(inventory.head())
print("\nShape:", inventory.shape)

# ==========================
# Save dataset
# ==========================

inventory.to_csv(
    "../processed/landslide_factor_dataset.csv",
    index=False
)

print("\nDataset saved successfully!")
print(inventory[['River', 'Road']].head(10))
print(inventory[['River', 'Road']].isnull().sum())

print("River CRS:", river.crs)
print("Road CRS:", road.crs)

print("River Bounds:", river.bounds)
print("Road Bounds:", road.bounds)

print("River Nodata:", river.nodata)
print("Road Nodata:", road.nodata)

river_data = river.read(1)
road_data  = road.read(1)

print("River Min:", river_data.min())
print("River Max:", river_data.max())

print("Road Min:", road_data.min())
print("Road Max:", road_data.max())

print("Shape:", river_data.shape)
print("NaN count:", np.isnan(river_data).sum())
print("Total cells:", river_data.size)

print(aspect.crs)
print(dem.crs)
print(slope.crs)
print(lulc.crs)
print(ndvi.crs)
print(rainfall.crs)
print(twi.crs)
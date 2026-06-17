# import pandas as pd
# import rasterio

# inventory = pd.read_csv("Inventory_datasets/sindhupalchowk_landslides (1).csv")
# aspect = rasterio.open("DEM/Sindhupalchok_Aspect.tif")
# dem=rasterio.open("DEM/Sindhupalchok_DEM.tif")
# lulc=rasterio.open("LULC/Sindhupalchok_LULC_30m.tif")
# ndvi=rasterio.open("NDVI/Sindhupalchok_NDVI_2025_30m.tif")
# rainfall=rasterio.open("Rainfall/Sindhupalchok_Rainfall_Raster.tif")
# twi=rasterio.open("TWI/Sindhupalchok_TWI_2025.tif")
# slope=rasterio.open("Slope/Sindhupalchok_Slope.tif")

# inventory = inventory[['longitude', 'latitude']]  # there are many unnecessary columns in the original dataset, we only need longitude and latitude for this example so we did it 

# coords = [(x, y) for x, y in zip(inventory["longitude"],
#                                  inventory["latitude"])]

# inventory["DEM"] = [x[0] for x in dem.sample(coords)]
# inventory["Aspect"] = [x[0] for x in aspect.sample(coords)]
# inventory["LULC"] = [x[0] for x in lulc.sample(coords)]
# inventory["NDVI"] = [x[0] for x in ndvi.sample(coords)]
# inventory["Rainfall"] = [x[0] for x in rainfall.sample(coords)]
# inventory["TWI"] = [x[0] for x in twi.sample(coords)]
# inventory["Slope"] = [x[0] for x in slope.sample(coords)]


# print(inventory.head())    # default only 5 rows
# print(inventory.shape)   #shows number of rows and columns in the dataframe


import pandas as pd
import rasterio


inventory = pd.read_csv(
    "Inventory_datasets/sindhupalchowk_landslides (1).csv"
)

inventory = inventory[['longitude', 'latitude']]


aspect = rasterio.open("DEM/Sindhupalchok_Aspect.tif")
slope = rasterio.open("Slope/Sindhupalchok_Slope.tif")
lulc = rasterio.open("LULC/Sindhupalchok_LULC_30m.tif")
ndvi = rasterio.open("NDVI/Sindhupalchok_NDVI_2025_30m.tif")
rainfall = rasterio.open("Rainfall/Sindhupalchok_Rainfall_Raster.tif")
twi = rasterio.open("TWI/Sindhupalchok_TWI_2025.tif")


coords = list(zip(
    inventory["longitude"],
    inventory["latitude"]
))


inventory["Aspect"] = [x[0] for x in aspect.sample(coords)]
inventory["Slope"] = [x[0] for x in slope.sample(coords)]
inventory["LULC"] = [x[0] for x in lulc.sample(coords)]
inventory["NDVI"] = [x[0] for x in ndvi.sample(coords)]
inventory["Rainfall"] = [x[0] for x in rainfall.sample(coords)]
inventory["TWI"] = [x[0] for x in twi.sample(coords)]


print(inventory.head())
print("\nShape:", inventory.shape)

# ==========================
# Save dataset
# ==========================

inventory.to_csv(
    "landslide_factor_dataset.csv",
    index=False
)

print("\nDataset saved successfully!")
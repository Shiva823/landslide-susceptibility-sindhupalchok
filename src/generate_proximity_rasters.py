import ee
import geopandas as gpd
import json
import os
import time
from dotenv import load_dotenv

load_dotenv()  # loads variables from .env file

_project = os.getenv("EE_PROJECT")
if not _project:
    raise RuntimeError("EE_PROJECT is not set. Add it to your .env file.")
ee.Initialize(project=_project)
print("✅ GEE initialized!")

# ============================================================
# AOI
# ============================================================
gdf = gpd.read_file(
    "D:/sindupalchok_landslide/data/processed/shapefiles/sindhupalchok_boundary.shp"
)
gdf = gdf.to_crs("EPSG:4326")
gdf = gdf[['geometry']]
geojson = json.loads(gdf.to_json())
aoi = ee.FeatureCollection(geojson).geometry()
print("✅ AOI loaded!")

# ============================================================
# RIVER PROXIMITY
# ============================================================
print("\n⏳ Computing river proximity...")

flow_acc = ee.Image("WWF/HydroSHEDS/15ACC")   # no clip here
river_network = flow_acc.gte(1000)

river_proximity = (
    river_network
    .fastDistanceTransform()
    .sqrt()
    .multiply(30)
    .rename('river_proximity')
    .clip(aoi)                                  # clip only at end
)

task_river = ee.batch.Export.image.toDrive(
    image=river_proximity,
    description='Sindhupalchok_RiverProximity',
    folder='LSM_Exports',
    fileNamePrefix='Sindhupalchok_RiverProximity',
    region=aoi,
    scale=30,
    crs='EPSG:4326',
    maxPixels=1e13,
    fileFormat='GeoTIFF'
)
task_river.start()
print("✅ River proximity export started!")

# ============================================================
# ROAD PROXIMITY
# ============================================================
print("\n⏳ Computing road proximity...")

roads = ee.FeatureCollection("projects/lsms-497103/assets/hotosm_npl_roads")
roads = roads.filterBounds(aoi)

road_img = (
    ee.Image()
    .paint(roads, 1)
    .unmask(0)                                  # no clip here
)

road_proximity = (
    road_img
    .fastDistanceTransform()
    .sqrt()
    .multiply(30)
    .rename('road_proximity')
    .clip(aoi)                                  # clip only at end
)

task_road = ee.batch.Export.image.toDrive(
    image=road_proximity,
    description='Sindhupalchok_RoadProximity',
    folder='LSM_Exports',
    fileNamePrefix='Sindhupalchok_RoadProximity',
    region=aoi,
    scale=30,
    crs='EPSG:4326',
    maxPixels=1e13,
    fileFormat='GeoTIFF'
)
task_road.start()
print("✅ Road proximity export started!")

# ============================================================
# MONITOR
# ============================================================
print("\n⏳ Monitoring exports (10–30 mins)...")
tasks = [task_river, task_road]

while True:
    statuses = [t.status() for t in tasks]
    print("\n--- Task Status ---")
    for s in statuses:
        print(f"  {s['description']} → {s['state']}")

    all_done = all(
        s['state'] in ('COMPLETED', 'FAILED', 'CANCELLED')
        for s in statuses
    )
    if all_done:
        print("\n✅ All exports finished!")
        for s in statuses:
            icon = "✅" if s['state'] == 'COMPLETED' else "❌"
            print(f"  {icon} {s['description']} — {s['state']}")
        break

    print("  Still running... checking again in 60 seconds.")
    time.sleep(60)
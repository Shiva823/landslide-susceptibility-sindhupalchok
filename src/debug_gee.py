import ee

ee.Initialize(project='lsms-497103')

# ── 1. Check if AOI is found ──────────────────────────────
print("Checking AOI...")
sindhupalchok = (
    ee.FeatureCollection("FAO/GAUL/2015/level2")
    .filter(ee.Filter.eq('ADM2_NAME', 'Sindhupalchok'))
)
count = sindhupalchok.size().getInfo()
print(f"  Features found for 'Sindhupalchok': {count}")

if count == 0:
    print("  ❌ AOI NOT FOUND — trying alternate spellings...")
    # Search what names exist for Nepal
    nepal = (
        ee.FeatureCollection("FAO/GAUL/2015/level2")
        .filter(ee.Filter.eq('ADM0_NAME', 'Nepal'))
    )
    names = nepal.aggregate_array('ADM2_NAME').getInfo()
    print("  Districts found in Nepal:")
    for n in sorted(names):
        print(f"    - {n}")
else:
    print(f"  ✅ AOI found!")
    aoi = sindhupalchok.geometry()
    bounds = aoi.bounds().getInfo()
    print(f"  Bounds: {bounds['coordinates']}")

# ── 2. Check if roads asset exists ───────────────────────
print("\nChecking roads asset...")
try:
    roads = ee.FeatureCollection("projects/lsms-497103/assets/hotosm_npl_roads")
    road_count = roads.size().getInfo()
    print(f"  ✅ Roads asset found! Features: {road_count}")
except Exception as e:
    print(f"  ❌ Roads asset error: {e}")

# ── 3. Check HydroSHEDS dataset ───────────────────────────
print("\nChecking HydroSHEDS...")
try:
    flow = ee.Image("WWF/HydroSHEDS/15ACC")
    info = flow.getInfo()
    print(f"  ✅ HydroSHEDS accessible!")
except Exception as e:
    print(f"  ❌ HydroSHEDS error: {e}")
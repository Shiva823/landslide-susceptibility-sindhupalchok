# 🏔️ Landslide Susceptibility Mapping — Sindhupalchok District, Nepal

## Overview

This project develops a hybrid machine learning approach for landslide
susceptibility mapping of Sindhupalchok District, Nepal. It combines static
terrain features with live rainfall data to produce both a **static
susceptibility map** and a **dynamic landslide warning dashboard**.

## Team

| Name                  
| --------------------- 
Shiva Acharya         
Utsav Adhikari       
Aayushman Bajracharya 
Suniti Shrestha       
Silviya Thapa         

---

## Prerequisites

- **Python 3.13+** (the virtual environment was built with 3.13)
- **Git**
- **Windows** (instructions below use PowerShell; adapt for bash on Linux/macOS)

---

## 1. Clone the Repository

```powershell
git clone https://github.com/Shiva823/landslide-susceptibility-sindhupalchok.git
cd landslide-susceptibility-sindhupalchok
```

## 2. Create & Activate the Virtual Environment

```powershell
python -m venv venv
```

**Activate the venv (PowerShell):**

```powershell
.\venv\Scripts\Activate.ps1
```

> **If you get an execution-policy error**, run this once first:
>
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
> ```

**Activate the venv (CMD):**

```cmd
venv\Scripts\activate.bat
```

**Activate the venv (Linux / macOS):**

```bash
source venv/bin/activate
```

After activation you should see `(venv)` at the start of your prompt.

## 3. Install Dependencies

```powershell
pip install -r requirements.txt
```

## 4. Place the Data Files

The following data files are required but **not tracked by Git** (they are too
large). Obtain them from the team's shared drive and place them at the paths
shown below:

```
data/
└── processed/
    ├── rasters/                         ← 9 GeoTIFF files
    │   ├── Sindhupalchok_Slope.tif
    │   ├── Sindhupalchok_DEM.tif
    │   ├── Sindhupalchok_Aspect.tif
    │   ├── Sindhupalchok_NDVI_2025_30m.tif
    │   ├── Sindhupalchok_LULC_30m.tif
    │   ├── Sindhupalchok_Rainfall_Raster.tif
    │   ├── Sindhupalchok_RiverProximity.tif
    │   ├── Sindhupalchok_RoadProximity.tif
    │   └── Sindhupalchok_TWI_2025.tif
    ├── shapefiles/                      ← boundary shapefile set
    │   └── sindhupalchok_boundary.shp   (+ .shx, .dbf, .prj)
    └── landslide_inventory/             ← landslide CSV
        └── sindhupalchowk_landslides.csv
```

---

## 5. Run the Pipeline

### Full pipeline (all steps in order)

```powershell
python main.py
```

### Run individual steps

| Command                            | Step | Description                                  |
| ---------------------------------- | ---- | -------------------------------------------- |
| `python main.py --step eda`        | 1    | Exploratory Data Analysis → `outputs/figures/` |
| `python main.py --step preprocess` | 2    | Data Preprocessing → `data/processed/`        |
| `python main.py --step features`   | 3    | Feature Engineering → training CSV            |
| `python main.py --step model`      | 4    | Model Training & Evaluation → `outputs/models/`, `outputs/maps/` |
| `python main.py --step validate`   | 5    | Susceptibility Map Validation → `outputs/maps/`, `outputs/figures/` |
| `python main.py --step risk`       | 6    | Dynamic Warning from Live Rainfall → `outputs/maps/`, `reports/` |
| `python main.py --step app`        | 7    | Export Web Dashboard Assets → `web_app/`      |

### Features Used

| # | Feature          | # | Feature          |
|---|------------------|---|------------------|
| 1 | Slope            | 6 | Rainfall         |
| 2 | Elevation        | 7 | River Proximity  |
| 3 | Aspect           | 8 | Road Proximity   |
| 4 | NDVI             | 9 | TWI              |
| 5 | LULC             |   |                  |

### Models

- Random Forest
- Support Vector Machine (SVM)
- Logistic Regression

---

## 6. Launch the Web Dashboard

After running at least the `validate`, `risk`, and `app` steps:

```powershell
python -m src.serve_web_app
```

Then open **http://127.0.0.1:8000/** in your browser.

The dashboard includes:
- Interactive Leaflet map with dynamic warning overlays
- Rainfall signal bars (1h / 3h / 24h / 72h)
- Live refresh button (fetches latest Open-Meteo data and rebuilds the map)
- Map layer toggles (dynamic risk, static susceptibility, rainfall points, landslide inventory)
- Rainfall hotspot drill-down with click-to-zoom

> **Note:** The "Refresh rainfall and risk map" button inside the dashboard
> only works when the app is served via `python -m src.serve_web_app`. Opening
> `web_app/index.html` directly in a browser will load the map but the live
> refresh and reverse-geocode features will not function.

---

## Project Structure

```
landslide-susceptibility-sindhupalchok/
├── main.py                  ← Pipeline entry point
├── requirements.txt         ← Python dependencies
├── README.md
├── src/
│   ├── config.py            ← All paths and settings
│   ├── eda.py               ← Step 1: EDA
│   ├── preprocessing.py     ← Step 2: Preprocessing
│   ├── features.py          ← Step 3: Feature engineering
│   ├── model.py             ← Step 4: Model training
│   ├── validation.py        ← Step 5: Validation
│   ├── dynamic_risk.py      ← Step 6: Dynamic risk
│   ├── export_web_app.py    ← Step 7: Web app export
│   └── serve_web_app.py     ← Web server with API endpoints
├── data/
│   └── processed/           ← Rasters, shapefiles, inventory
├── outputs/
│   ├── figures/             ← Charts and plots
│   ├── models/              ← Trained model .pkl files
│   └── maps/                ← Susceptibility & risk GeoTIFFs
├── reports/                 ← Generated reports
└── web_app/
    ├── index.html           ← Dashboard UI
    ├── app.js               ← Dashboard logic
    ├── styles.css            ← Dashboard styles
    ├── data/                ← JSON data for the dashboard
    └── assets/              ← Map overlay PNGs
```

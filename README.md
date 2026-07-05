# 🏔️ Landslide Susceptibility Mapping — Sindhupalchok District, Nepal

## Overview
This project develops a hybrid machine learning approach for landslide 
susceptibility mapping of Sindhupalchok District, Nepal.

## Team
- Shiva Acharya 
- Utsav Adhikari 
- Aayushman Bajracharya
- Suniti Shrestha 
- Silviya Thapa 

## Features Used
1. Slope | 2. Elevation | 3. Aspect | 4. NDVI
5. LULC | 6. Rainfall | 7. River Proximity
8. Road Proximity | 9. TWI

## Models
- Random Forest
- Support Vector Machine (SVM)
- Logistic Regression

## Dynamic Warning Map
The project can also generate a rainfall-triggered landslide warning map using
live Open-Meteo rainfall data over Sindhupalchok. The susceptibility map remains
the static terrain baseline, while recent 1h, 3h, 24h, and 72h rainfall totals
update the dynamic risk score.

```bash
python main.py --step risk
```

Outputs are saved to `outputs/maps/`, `outputs/figures/`, and `reports/`.

## Web Dashboard
Export the interactive dashboard assets after generating susceptibility,
validation, and dynamic warning outputs.

```bash
python main.py --step app
python -m src.serve_web_app
```

Then open `http://127.0.0.1:8000/`. The dashboard refresh button works
when served with `src.serve_web_app`.

## Setup
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

"""
main.py
═══════════════════════════════════════════════════════════════
Main pipeline runner for Landslide Susceptibility Mapping
Sindhupalchok District, Nepal — KU COMP 313

Team:
    Shiva Acharya         (Roll 01)
    Utsav Adhikari        (Roll 03)
    Aayushman Bajracharya (Roll 05)
    Suniti Shrestha       (Roll 51)
    Silviya Thapa         (Roll 55)

Supervisor: Suman Shrestha

Usage:
    Run full pipeline : python main.py
    Run only EDA      : python main.py --step eda
    Run preprocessing : python main.py --step preprocess
    Run features      : python main.py --step features
    Run models        : python main.py --step model
    Run validation    : python main.py --step validate
    Run dynamic risk  : python main.py --step risk
    Export web app    : python main.py --step app
═══════════════════════════════════════════════════════════════
"""

import argparse
import sys
import os
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ── Make src importable ─────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ── Banner ──────────────────────────────────────────────────────────
def print_banner():
    print("""
╔══════════════════════════════════════════════════════════╗
║   🏔️  LANDSLIDE SUSCEPTIBILITY MAPPING PIPELINE         ║
║       Sindhupalchok District, Nepal                      ║
║       Kathmandu University — COMP 313                    ║
╚══════════════════════════════════════════════════════════╝
    """)


def print_step(number, name):
    print(f"\n{'─'*55}")
    print(f"  STEP {number}: {name}")
    print(f"{'─'*55}\n")


# ── Step runners ────────────────────────────────────────────────────
def run_eda():
    print_step(1, "Exploratory Data Analysis")
    from src.eda import run_eda as eda_main
    start = time.time()
    eda_main()
    print(f"\n✅ EDA done in {time.time() - start:.1f}s")
    print("   Figures saved → outputs/figures/")


def run_preprocessing():
    print_step(2, "Data Preprocessing")
    from src.preprocessing import run_preprocessing as preprocess_main
    start = time.time()
    preprocess_main()
    print(f"\n✅ Preprocessing done in {time.time() - start:.1f}s")
    print("   Processed data → data/processed/")


def run_features():
    print_step(3, "Feature Engineering")
    from src.features import build_features
    start = time.time()
    build_features()
    print(f"\n✅ Features done in {time.time() - start:.1f}s")
    print("   Training CSV → data/processed/landslide_inventory/")


def run_model():
    print_step(4, "Model Training & Evaluation")
    from src.model import train_models
    start = time.time()
    train_models()
    print(f"\n✅ Modelling done in {time.time() - start:.1f}s")
    print("   Models → outputs/models/")
    print("   Map    → outputs/maps/")


# ── Main ────────────────────────────────────────────────────────────
def run_validation():
    print_step(5, "Susceptibility Map Validation")
    from src.validation import validate_susceptibility_map
    start = time.time()
    validate_susceptibility_map()
    print(f"\n✅ Validation done in {time.time() - start:.1f}s")
    print("   Validation outputs → outputs/maps/ and outputs/figures/")


def run_dynamic_risk():
    print_step(6, "Dynamic Landslide Warning from Live Rainfall")
    from src.dynamic_risk import generate_dynamic_landslide_risk_map
    start = time.time()
    generate_dynamic_landslide_risk_map()
    print(f"\nDynamic warning done in {time.time() - start:.1f}s")
    print("   Dynamic warning outputs -> outputs/maps/, outputs/figures/, and reports/")


def run_web_app_export():
    print_step(7, "Web App Asset Export")
    from src.export_web_app import export_web_app_assets
    start = time.time()
    export_web_app_assets()
    print(f"\nWeb app export done in {time.time() - start:.1f}s")
    print("   Open web app -> web_app/index.html")


def main():
    print_banner()

    parser = argparse.ArgumentParser(
        description="Landslide Susceptibility Mapping Pipeline"
    )
    parser.add_argument(
        "--step",
        type=str,
        choices=[
            "eda",
            "preprocess",
            "features",
            "model",
            "validate",
            "risk",
            "app",
            "all",
        ],
        default="all",
        help="Which step to run (default: all)"
    )
    args = parser.parse_args()

    total_start = time.time()

    if args.step == "eda":
        run_eda()

    elif args.step == "preprocess":
        run_preprocessing()

    elif args.step == "features":
        run_features()

    elif args.step == "model":
        run_model()

    elif args.step == "validate":
        run_validation()

    elif args.step == "risk":
        run_dynamic_risk()

    elif args.step == "app":
        run_web_app_export()

    elif args.step == "all":
        run_eda()
        run_preprocessing()
        run_features()
        run_model()
        run_validation()
        run_dynamic_risk()
        run_web_app_export()

    print(f"""
{'═'*55}
  🎉 DONE  —  Total time: {time.time() - total_start:.1f}s

  Outputs:
    📊 Figures  → outputs/figures/
    🤖 Models   → outputs/models/
    🗺️  Map      → outputs/maps/
{'═'*55}
    """)


if __name__ == "__main__":
    main()

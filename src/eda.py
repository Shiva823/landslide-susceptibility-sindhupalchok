"""
eda.py
═══════════════════════════════════════════════════════════════
Exploratory Data Analysis
Landslide Susceptibility Mapping — Sindhupalchok District

Generates 6 figures saved to outputs/figures/:
    fig1_dataset_overview.png   — stats table + spatial map
    fig2_distributions.png      — histograms per feature
    fig3_correlation.png        — pearson correlation matrix
    fig4_boxplots.png           — boxplots at landslide points
    fig5_scatter.png            — feature pair relationships
    fig6_spatial_maps.png       — spatial view of all rasters

Run directly  : python src/eda.py
Via pipeline  : python main.py --step eda
═══════════════════════════════════════════════════════════════
"""

import os
import sys
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.colors import LinearSegmentedColormap
import rasterio
from scipy import stats

warnings.filterwarnings("ignore")
os.environ["SHAPE_RESTORE_SHX"] = "YES"

# ── Allow running as standalone script ──────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import (
    RASTERS,
    LANDSLIDE_CSV,
    BOUNDARY_SHP,
    FIGURES_DIR,
    FEATURE_NAMES,
    COLORS,
    FEATURE_COLORS,
)

# ── Color shortcuts ─────────────────────────────────────────────────
DARK_BG = COLORS["dark_bg"]
CARD_BG = COLORS["card_bg"]
ACCENT  = COLORS["accent"]
GREEN   = COLORS["green"]
ORANGE  = COLORS["orange"]
RED     = COLORS["red"]
PURPLE  = COLORS["purple"]
TEXT    = COLORS["text"]
SUBTEXT = COLORS["subtext"]
GOLD    = COLORS["gold"]
FC      = FEATURE_COLORS


# ════════════════════════════════════════════════════════════════════
#  DATA LOADING FUNCTIONS
# ════════════════════════════════════════════════════════════════════

def load_rasters():
    """
    Load all 9 raster .tif files into numpy arrays.
    Replaces NoData values with NaN.

    Returns
    -------
    arrays : dict  {feature_name -> 2D numpy array}
    metas  : dict  {feature_name -> metadata dict}
    """
    arrays, metas = {}, {}
    print("  Loading rasters...")
    for name, path in RASTERS.items():
        if not os.path.exists(path):
            print(f"  ⚠️  NOT FOUND: {path}")
            continue
        with rasterio.open(path) as src:
            data = src.read(1).astype(float)
            nd   = src.nodata
            if nd is not None:
                data[data == nd] = np.nan
            arrays[name] = data
            metas[name]  = {
                "crs"   : str(src.crs),
                "shape" : src.shape,
                "res"   : src.res,
                "bounds": src.bounds,
            }
        nan_pct = np.isnan(arrays[name]).mean() * 100
        print(f"    ✅ {name:<18} shape={arrays[name].shape}  NaN={nan_pct:.1f}%")
    return arrays, metas


def load_landslide_csv():
    """
    Load landslide inventory CSV.

    Returns
    -------
    df : DataFrame  with columns latitude, longitude (and others)
    """
    print("  Loading landslide CSV...")
    df = pd.read_csv(LANDSLIDE_CSV)
    print(f"    ✅ {len(df):,} landslide points loaded")
    return df


def load_boundary():
    """
    Load Sindhupalchok district boundary shapefile.

    Returns
    -------
    bnd_x  : list of x (longitude) coordinates of boundary exterior
    bnd_y  : list of y (latitude)  coordinates of boundary exterior
    """
    print("  Loading boundary shapefile...")
    try:
        import fiona
        from shapely.geometry import shape
        with fiona.open(BOUNDARY_SHP) as src:
            geoms = [shape(feat["geometry"]) for feat in src]
        geom  = geoms[0]
        bnd_x, bnd_y = list(geom.exterior.xy[0]), list(geom.exterior.xy[1])
        print(f"    ✅ Boundary loaded  bounds={geom.bounds}")
        return bnd_x, bnd_y
    except Exception as err:
        print(f"    ⚠️  Boundary load failed: {err}")
        return None, None


def sample_rasters_at_landslide_points(df_ls, arrays):
    """
    Extract raster pixel value at every landslide location.

    Parameters
    ----------
    df_ls  : DataFrame  landslide points (must have latitude, longitude)
    arrays : dict       loaded raster arrays

    Returns
    -------
    df_sample : DataFrame  one row per valid landslide point,
                           columns = feature names + lat/lon
    """
    print("  Sampling raster values at landslide points...")
    coords = list(zip(df_ls["longitude"], df_ls["latitude"]))

    sample_dict = {
        "longitude": df_ls["longitude"].values,
        "latitude" : df_ls["latitude"].values,
    }

    for name, path in RASTERS.items():
        if name not in arrays:
            continue
        with rasterio.open(path) as src:
            sampled = [v[0] for v in src.sample(coords)]
        sample_dict[name] = sampled

    df_sample = pd.DataFrame(sample_dict)
    df_sample = df_sample.replace([np.inf, -np.inf], np.nan)
    df_sample = df_sample.replace(-9999.0,  np.nan)
    df_sample = df_sample.replace(-32768.0, np.nan)
    df_sample = df_sample.dropna()
    print(f"    ✅ Valid samples after NaN removal: {len(df_sample):,}")
    return df_sample


# ════════════════════════════════════════════════════════════════════
#  HELPER FUNCTIONS
# ════════════════════════════════════════════════════════════════════

def style_axes(ax):
    """Apply consistent dark theme to a matplotlib Axes."""
    ax.set_facecolor(CARD_BG)
    for spine in ax.spines.values():
        spine.set_color("#30363d")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(colors=SUBTEXT, labelsize=9)


def save_fig(fig, filename):
    """Save figure to outputs/figures/ and close it."""
    filepath = os.path.join(FIGURES_DIR, filename)
    fig.savefig(filepath, dpi=150, bbox_inches="tight",
                facecolor=DARK_BG, edgecolor="none")
    plt.close(fig)
    print(f"    💾 Saved → outputs/figures/{filename}")


def compute_stats(arrays):
    """
    Compute summary statistics for all raster features.

    Returns
    -------
    df_stats : DataFrame  with Min, Max, Mean, Std, NaN%, Skewness
    """
    rows = []
    for name, arr in arrays.items():
        flat = arr[~np.isnan(arr)].flatten()
        rows.append({
            "Feature" : name,
            "Min"     : np.nanmin(arr),
            "Max"     : np.nanmax(arr),
            "Mean"    : np.nanmean(arr),
            "Std"     : np.nanstd(arr),
            "NaN %"   : np.isnan(arr).mean() * 100,
            "Skewness": float(stats.skew(flat)),
        })
    return pd.DataFrame(rows)


# ════════════════════════════════════════════════════════════════════
#  FIGURE 1 — DATASET OVERVIEW & SUMMARY STATISTICS
# ════════════════════════════════════════════════════════════════════

def generate_fig1(arrays, df_ls, df_sample, bnd_x, bnd_y):
    """
    Figure 1: Dataset Overview
    ──────────────────────────
    Panel A  Mean value per feature (horizontal bar)
    Panel B  Missing data % per feature (horizontal bar)
    Panel C  Full statistics table
    Panel D  Spatial distribution of landslide points
    Panel E  Dataset summary info box
    """
    print("\n  Generating fig1_dataset_overview.png ...")
    df_stats = compute_stats(arrays)

    fig = plt.figure(figsize=(24, 15), facecolor=DARK_BG)
    fig.suptitle(
        "🏔️  LANDSLIDE SUSCEPTIBILITY MAPPING — Sindhupalchok District, Nepal\n"
        "Dataset Overview & Summary Statistics",
        fontsize=18, fontweight="bold", color=GOLD, y=0.99,
    )
    gs = gridspec.GridSpec(3, 4, figure=fig,
                           hspace=0.55, wspace=0.4,
                           left=0.05, right=0.97,
                           top=0.92,  bottom=0.06)

    # ── Panel A: mean value bar ──────────────────────────────────────
    ax_a = fig.add_subplot(gs[0, :2])
    style_axes(ax_a)
    ax_a.barh(df_stats["Feature"], df_stats["Mean"],
              color=FC, edgecolor="none", height=0.65)
    ax_a.set_title("Mean Value per Feature",
                   color=TEXT, fontsize=12, fontweight="bold", pad=8)
    ax_a.set_xlabel("Mean Value", color=SUBTEXT, fontsize=9)
    ax_a.tick_params(colors=TEXT)

    # ── Panel B: NaN % bar ──────────────────────────────────────────
    ax_b = fig.add_subplot(gs[0, 2:])
    style_axes(ax_b)
    nan_colors = [RED if v > 40 else ORANGE if v > 20 else GREEN
                  for v in df_stats["NaN %"]]
    ax_b.barh(df_stats["Feature"], df_stats["NaN %"],
              color=nan_colors, edgecolor="none", height=0.65)
    ax_b.axvline(37, color=GOLD, linestyle="--", linewidth=1.5,
                 label="~37% boundary mask")
    ax_b.set_title("Missing / NoData % per Feature",
                   color=TEXT, fontsize=12, fontweight="bold", pad=8)
    ax_b.set_xlabel("NaN %", color=SUBTEXT, fontsize=9)
    ax_b.tick_params(colors=TEXT)
    ax_b.legend(fontsize=9, labelcolor=TEXT,
                facecolor=CARD_BG, edgecolor="none")

    # ── Panel C: statistics table ────────────────────────────────────
    ax_c = fig.add_subplot(gs[1, :])
    ax_c.set_facecolor(CARD_BG)
    ax_c.axis("off")
    table_data = [
        [row["Feature"],
         f"{row['Min']:.2f}",
         f"{row['Max']:.2f}",
         f"{row['Mean']:.2f}",
         f"{row['Std']:.2f}",
         f"{row['NaN %']:.1f}%",
         f"{row['Skewness']:.2f}"]
        for _, row in df_stats.iterrows()
    ]
    tbl = ax_c.table(
        cellText=table_data,
        colLabels=["Feature", "Min", "Max", "Mean", "Std Dev", "NaN %", "Skewness"],
        cellLoc="center",
        loc="center",
        bbox=[0, 0, 1, 1],
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(10)
    for (r, c), cell in tbl.get_celld().items():
        cell.set_facecolor(DARK_BG if r == 0 else CARD_BG)
        cell.set_text_props(color=GOLD if r == 0 else TEXT)
        cell.set_edgecolor("#30363d")
    ax_c.set_title("Complete Feature Statistics Summary",
                   color=TEXT, fontsize=13, fontweight="bold", pad=10)

    # ── Panel D: spatial map ─────────────────────────────────────────
    ax_d = fig.add_subplot(gs[2, :2])
    style_axes(ax_d)
    if bnd_x is not None:
        ax_d.plot(bnd_x, bnd_y, color=ACCENT, linewidth=2)
    ax_d.scatter(df_ls["longitude"], df_ls["latitude"],
                 c=RED, s=8, alpha=0.5, zorder=5,
                 label=f"Landslide Points (n={len(df_ls):,})")
    ax_d.set_title("Spatial Distribution of Landslide Inventory",
                   color=TEXT, fontsize=12, fontweight="bold", pad=8)
    ax_d.set_xlabel("Longitude", color=SUBTEXT, fontsize=9)
    ax_d.set_ylabel("Latitude",  color=SUBTEXT, fontsize=9)
    ax_d.legend(fontsize=9, labelcolor=TEXT,
                facecolor=CARD_BG, edgecolor="none")

    # ── Panel E: info box ────────────────────────────────────────────
    ax_e = fig.add_subplot(gs[2, 2:])
    ax_e.set_facecolor(CARD_BG)
    ax_e.axis("off")
    info_rows = [
        ("Total Landslide Points", f"{len(df_ls):,}"),
        ("Valid Sampled Points",   f"{len(df_sample):,}"),
        ("Latitude Range",
         f"{df_ls['latitude'].min():.3f}° — {df_ls['latitude'].max():.3f}°"),
        ("Longitude Range",
         f"{df_ls['longitude'].min():.3f}° — {df_ls['longitude'].max():.3f}°"),
        ("District",       "Sindhupalchok, Bagmati, Nepal"),
        ("CRS",            "EPSG:4326"),
        ("Resolution",     "~30m per pixel"),
        ("Total Features", f"{len(arrays)} raster layers"),
    ]
    for i, (label, value) in enumerate(info_rows):
        y_pos = 0.92 - i * 0.115
        ax_e.text(0.02, y_pos, label + ":",
                  color=SUBTEXT, fontsize=10,
                  transform=ax_e.transAxes, fontweight="bold")
        ax_e.text(0.52, y_pos, value,
                  color=GOLD, fontsize=10,
                  transform=ax_e.transAxes)
    ax_e.set_title("Dataset Summary",
                   color=TEXT, fontsize=13, fontweight="bold", pad=10)

    save_fig(fig, "fig1_dataset_overview.png")


# ════════════════════════════════════════════════════════════════════
#  FIGURE 2 — FEATURE DISTRIBUTIONS
# ════════════════════════════════════════════════════════════════════

def generate_fig2(arrays, df_sample):
    """
    Figure 2: Feature Value Distributions
    ──────────────────────────────────────
    For each feature:
      Blue histogram  = all raster pixels
      Red  histogram  = pixels at landslide locations
      Dashed lines    = mean of each distribution

    Where red shifts from blue → landslides prefer
    certain value ranges of that feature.
    """
    print("\n  Generating fig2_distributions.png ...")
    fig, axes = plt.subplots(3, 3, figsize=(24, 17), facecolor=DARK_BG)
    fig.suptitle(
        "Feature Value Distributions\n"
        "Blue = Full raster  |  Red = Landslide points  |  Dashed = Mean",
        fontsize=16, fontweight="bold", color=GOLD, y=0.99,
    )
    plt.subplots_adjust(hspace=0.5, wspace=0.35,
                        left=0.06, right=0.97,
                        top=0.93,  bottom=0.06)

    for idx, (name, arr) in enumerate(arrays.items()):
        ax = axes[idx // 3][idx % 3]
        style_axes(ax)

        flat_all = arr[~np.isnan(arr)].flatten()
        flat_ls  = df_sample[name].dropna().values

        # Clip to 1–99 percentile for cleaner display
        p1, p99 = np.percentile(flat_all, 1), np.percentile(flat_all, 99)
        fa = flat_all[(flat_all >= p1) & (flat_all <= p99)]
        fl = flat_ls[ (flat_ls  >= p1) & (flat_ls  <= p99)]

        ax.hist(fa, bins=60, color=FC[idx], alpha=0.5,
                density=True, label="Full Raster", edgecolor="none")
        ax.hist(fl, bins=60, color=RED, alpha=0.75,
                density=True, label="Landslide Points", edgecolor="none")
        ax.axvline(np.mean(fa), color=FC[idx],
                   linestyle="--", linewidth=2, alpha=0.9)
        ax.axvline(np.mean(fl), color=RED,
                   linestyle="--", linewidth=2, alpha=0.9)

        ax.set_title(name, color=TEXT, fontsize=12, fontweight="bold", pad=6)
        ax.set_xlabel("Value",   color=SUBTEXT, fontsize=9)
        ax.set_ylabel("Density", color=SUBTEXT, fontsize=9)
        ax.legend(fontsize=8, labelcolor=TEXT,
                  facecolor=DARK_BG, edgecolor="none")

    save_fig(fig, "fig2_distributions.png")


# ════════════════════════════════════════════════════════════════════
#  FIGURE 3 — CORRELATION MATRIX
# ════════════════════════════════════════════════════════════════════

def generate_fig3(arrays, df_sample):
    """
    Figure 3: Pearson Correlation Matrix
    ──────────────────────────────────────
    Left  = correlation across 5,000 random background pixels
    Right = correlation across landslide inventory points

    Blue  = positive correlation
    Red   = negative correlation

    Low inter-feature correlation = good — means features
    carry independent information for the ML model.
    """
    print("\n  Generating fig3_correlation.png ...")
    feat_names = list(arrays.keys())

    # Build random background sample DataFrame
    np.random.seed(42)
    min_size   = min(arr[~np.isnan(arr)].size for arr in arrays.values())
    sample_n   = min(5000, min_size)
    rand_idx   = np.random.choice(min_size, sample_n, replace=False)
    bg_df = pd.DataFrame({
        name: arr[~np.isnan(arr)].flatten()[:min_size][rand_idx]
        for name, arr in arrays.items()
    })
    corr_bg = bg_df.corr()
    corr_ls = df_sample[feat_names].dropna().corr()

    cmap = LinearSegmentedColormap.from_list(
        "rw_blue", [RED, "#21262d", ACCENT], N=256
    )

    fig, axes = plt.subplots(1, 2, figsize=(24, 10), facecolor=DARK_BG)
    fig.suptitle(
        "Pearson Correlation Matrix\n"
        "Left: Random background sample (n=5,000)  |  "
        "Right: Landslide inventory points",
        fontsize=16, fontweight="bold", color=GOLD, y=1.01,
    )
    plt.subplots_adjust(wspace=0.4, left=0.05, right=0.97)

    for ax, corr, title in zip(
        axes,
        [corr_bg, corr_ls],
        ["Background Sample (n=5,000)", "Landslide Inventory Points"],
    ):
        ax.set_facecolor(CARD_BG)
        im = ax.imshow(corr.values, cmap=cmap,
                       vmin=-1, vmax=1, aspect="auto")
        ax.set_xticks(range(len(feat_names)))
        ax.set_yticks(range(len(feat_names)))
        ax.set_xticklabels(feat_names, rotation=40,
                           ha="right", color=TEXT, fontsize=10)
        ax.set_yticklabels(feat_names, color=TEXT, fontsize=10)
        ax.set_title(title, color=TEXT,
                     fontsize=13, fontweight="bold", pad=10)

        for i in range(len(feat_names)):
            for j in range(len(feat_names)):
                val = corr.values[i, j]
                ax.text(j, i, f"{val:.2f}",
                        ha="center", va="center",
                        fontsize=9, fontweight="bold",
                        color="white" if abs(val) > 0.5 else TEXT)

        cbar = plt.colorbar(im, ax=ax, shrink=0.8)
        cbar.ax.tick_params(colors=TEXT, labelsize=9)
        cbar.set_label("Pearson r", color=SUBTEXT, fontsize=10)

    save_fig(fig, "fig3_correlation.png")


# ════════════════════════════════════════════════════════════════════
#  FIGURE 4 — BOXPLOTS AT LANDSLIDE LOCATIONS
# ════════════════════════════════════════════════════════════════════

def generate_fig4(df_sample):
    """
    Figure 4: Boxplots at Landslide Locations
    ───────────────────────────────────────────
    For each feature, shows value spread at landslide points.

    Gold line = median
    Box       = interquartile range Q1–Q3
    Whiskers  = 1.5 × IQR
    Red dots  = outliers

    Tight boxes = landslides occur in narrow value ranges
                = high predictive power for that feature.
    """
    print("\n  Generating fig4_boxplots.png ...")
    feat_names = [n for n in FEATURE_NAMES if n in df_sample.columns]

    fig, axes = plt.subplots(3, 3, figsize=(24, 17), facecolor=DARK_BG)
    fig.suptitle(
        "Feature Value Range at Landslide Locations — Boxplots\n"
        "Gold = Median  |  Box = IQR  |  Red dots = Outliers",
        fontsize=16, fontweight="bold", color=GOLD, y=0.99,
    )
    plt.subplots_adjust(hspace=0.5, wspace=0.4,
                        left=0.06, right=0.97,
                        top=0.93,  bottom=0.06)

    for idx, name in enumerate(feat_names):
        ax = axes[idx // 3][idx % 3]
        style_axes(ax)

        data = df_sample[name].dropna().values
        ax.boxplot(
            data,
            patch_artist=True,
            notch=False,
            medianprops ={"color": GOLD,       "linewidth": 2.5},
            boxprops     ={"facecolor": FC[idx], "alpha": 0.7},
            whiskerprops ={"color": TEXT,        "linewidth": 1.5},
            capprops     ={"color": TEXT,        "linewidth": 2},
            flierprops   ={"marker": "o",  "color": RED,
                           "markersize": 3, "alpha": 0.4},
        )

        q1, med, q3 = np.percentile(data, [25, 50, 75])
        iqr = q3 - q1

        ax.text(
            0.05, 0.97,
            f"Median : {med:.2f}\n"
            f"Q1     : {q1:.2f}\n"
            f"Q3     : {q3:.2f}\n"
            f"IQR    : {iqr:.2f}\n"
            f"Mean   : {data.mean():.2f}\n"
            f"Std    : {data.std():.2f}",
            transform=ax.transAxes, color=TEXT,
            fontsize=8.5, va="top", family="monospace",
            bbox=dict(facecolor=DARK_BG, alpha=0.85,
                      edgecolor="#30363d", boxstyle="round,pad=0.4"),
        )

        ax.set_title(name, color=TEXT,
                     fontsize=12, fontweight="bold", pad=6)
        ax.set_ylabel("Value", color=SUBTEXT, fontsize=9)
        ax.set_xticklabels(["Landslide\nLocations"], color=SUBTEXT)

    save_fig(fig, "fig4_boxplots.png")


# ════════════════════════════════════════════════════════════════════
#  FIGURE 5 — SCATTER PLOTS
# ════════════════════════════════════════════════════════════════════

def generate_fig5(df_sample):
    """
    Figure 5: Key Feature Pair Scatter Plots
    ─────────────────────────────────────────
    6 scatter plots of important feature combinations.

    White line = linear trend
    r          = Pearson correlation coefficient
    ***        = p < 0.001  (statistically significant)
    **         = p < 0.01
    *          = p < 0.05
    ns         = not significant
    """
    print("\n  Generating fig5_scatter.png ...")
    pairs = [
        ("Slope",           "Elevation",      ACCENT),
        ("Slope",           "NDVI",           GREEN),
        ("Elevation",       "Rainfall",       ORANGE),
        ("River Proximity", "Slope",          PURPLE),
        ("TWI",             "Slope",          RED),
        ("NDVI",            "Rainfall",       "#ffa657"),
    ]

    fig, axes = plt.subplots(2, 3, figsize=(24, 14), facecolor=DARK_BG)
    fig.suptitle(
        "Key Feature Relationships at Landslide Locations\n"
        "White = trend line  |  r = Pearson r  |  *** p<0.001",
        fontsize=16, fontweight="bold", color=GOLD, y=0.99,
    )
    plt.subplots_adjust(hspace=0.45, wspace=0.35,
                        left=0.06, right=0.97,
                        top=0.92,  bottom=0.07)

    for idx, (xf, yf, col) in enumerate(pairs):
        ax = axes[idx // 3][idx % 3]
        style_axes(ax)

        x = df_sample[xf].dropna()
        y = df_sample[yf].reindex(x.index).dropna()
        x = x.reindex(y.index)
       

        ax.scatter(x, y, c=col, alpha=0.3, s=12, edgecolors="none")

        # Trend line
        z      = np.polyfit(x, y, 1)
        x_line = np.linspace(x.min(), x.max(), 200)
        ax.plot(x_line, np.poly1d(z)(x_line),
                color="white", linewidth=2, alpha=0.9)

        r, pval = stats.pearsonr(x, y)
        sig = ("***" if pval < 0.001 else
               "**"  if pval < 0.01  else
               "*"   if pval < 0.05  else "ns")

        ax.set_title(f"{xf}  vs  {yf}",
                     color=TEXT, fontsize=12, fontweight="bold", pad=6)
        ax.set_xlabel(xf, color=SUBTEXT, fontsize=9)
        ax.set_ylabel(yf, color=SUBTEXT, fontsize=9)
        ax.text(
            0.05, 0.93,
            f"r = {r:.3f}  |  {sig}",
            transform=ax.transAxes, color=GOLD,
            fontsize=10, fontweight="bold",
            bbox=dict(facecolor=DARK_BG, edgecolor="none", alpha=0.8),
        )

    save_fig(fig, "fig5_scatter.png")


# ════════════════════════════════════════════════════════════════════
#  FIGURE 6 — SPATIAL RASTER MAPS
# ════════════════════════════════════════════════════════════════════

def generate_fig6(arrays, metas, df_ls):
    """
    Figure 6: Spatial Raster Maps
    ───────────────────────────────
    Shows the spatial distribution of all 9 features
    across Sindhupalchok district.

    Red dots = landslide inventory points overlaid.

    Visual check that:
    - Rasters cover the correct geographic area
    - Landslide points fall within the study area
    - No obvious data errors or misalignment
    """
    print("\n  Generating fig6_spatial_maps.png ...")
    cmaps_list = [
        "RdYlGn_r",  # Slope
        "terrain",   # Elevation
        "hsv",       # Aspect
        "RdYlGn",    # NDVI
        "tab20",     # LULC
        "Blues",     # Rainfall
        "YlOrRd",    # River Proximity
        "Purples",   # Road Proximity
        "RdBu",      # TWI
    ]

    fig, axes = plt.subplots(3, 3, figsize=(24, 19), facecolor=DARK_BG)
    fig.suptitle(
        "Spatial Distribution of All Features — Sindhupalchok District\n"
        "Red dots = Landslide Inventory Points",
        fontsize=16, fontweight="bold", color=GOLD, y=0.99,
    )
    plt.subplots_adjust(hspace=0.4, wspace=0.3,
                        left=0.04, right=0.97,
                        top=0.94,  bottom=0.04)

    for idx, (name, arr) in enumerate(arrays.items()):
        ax = axes[idx // 3][idx % 3]
        ax.set_facecolor(CARD_BG)

        p2, p98 = np.nanpercentile(arr, 2), np.nanpercentile(arr, 98)
        im = ax.imshow(arr, cmap=cmaps_list[idx],
                       vmin=p2, vmax=p98,
                       interpolation="bilinear")

        # Convert lon/lat to pixel coordinates
        b  = metas[name]["bounds"]
        rs = metas[name]["res"]
        px = [(lon - b.left) / rs[0] for lon in df_ls["longitude"]]
        py = [(b.top - lat)  / rs[1] for lat in df_ls["latitude"]]
        ax.scatter(px, py, c=RED, s=2, alpha=0.3, zorder=5)

        cbar = plt.colorbar(im, ax=ax, shrink=0.78, pad=0.02)
        cbar.ax.tick_params(colors=TEXT, labelsize=7)
        ax.set_title(name, color=TEXT,
                     fontsize=12, fontweight="bold", pad=6)
        ax.set_xticks([])
        ax.set_yticks([])

    save_fig(fig, "fig6_spatial_maps.png")


# ════════════════════════════════════════════════════════════════════
#  PRINT KEY INSIGHTS
# ════════════════════════════════════════════════════════════════════

def print_key_insights(arrays, df_sample):
    """Print how landslide mean differs from district mean per feature."""
    print("\n" + "═" * 55)
    print("  📋 KEY EDA INSIGHTS")
    print("═" * 55)
    for name, arr in arrays.items():
        if name not in df_sample.columns:
            continue
        ls_mean  = df_sample[name].mean()
        all_mean = np.nanmean(arr)
        if all_mean == 0:
            continue
        diff_pct  = ((ls_mean - all_mean) / abs(all_mean)) * 100
        direction = "HIGHER" if diff_pct > 0 else "LOWER"
        print(f"  {name:<18} landslide mean is "
              f"{abs(diff_pct):5.1f}% {direction} than district mean")
    print("═" * 55)


# ════════════════════════════════════════════════════════════════════
#  MAIN EDA RUNNER
# ════════════════════════════════════════════════════════════════════

def run_eda():
    """
    Run the complete EDA pipeline.
    Called by main.py or directly via: python src/eda.py
    """
    print("\n" + "═" * 55)
    print("  EXPLORATORY DATA ANALYSIS")
    print("  Sindhupalchok Landslide Susceptibility Mapping")
    print("═" * 55)

    # ── Load data ────────────────────────────────────────────────────
    print("\n📂 Loading data...")
    arrays, metas = load_rasters()
    df_ls         = load_landslide_csv()
    bnd_x, bnd_y  = load_boundary()
    df_sample     = sample_rasters_at_landslide_points(df_ls, arrays)

    # ── Generate all 6 figures ───────────────────────────────────────
    print("\n🎨 Generating figures...")
    generate_fig1(arrays, df_ls, df_sample, bnd_x, bnd_y)
    generate_fig2(arrays, df_sample)
    generate_fig3(arrays, df_sample)
    generate_fig4(df_sample)
    generate_fig5(df_sample)
    generate_fig6(arrays, metas, df_ls)

    # ── Print insights ───────────────────────────────────────────────
    print_key_insights(arrays, df_sample)

    print(f"\n✅ All 6 figures saved to outputs/figures/")


# ── Allow running as standalone script ──────────────────────────────
if __name__ == "__main__":
    run_eda()
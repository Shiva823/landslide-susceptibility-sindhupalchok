import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# =====================
# STEP 1: Load dataset
# =====================

df = pd.read_csv("../processed/landslide_factor_dataset.csv")
print("Dataset loaded\n")

# =====================
# STEP 2: Inspect data
# =====================

print(df.head())
print("\nShape:", df.shape)
print("\nData types:\n", df.dtypes)

# =====================
# STEP 3: Missing values
# =====================

print("\nMissing values:\n", df.isnull().sum())

# =====================
# STEP 4: Statistical summary
# =====================

print("\nStatistical Summary:\n", df.describe())

# =====================
# STEP 5: All Boxplots in ONE page (3x3 grid)
# =====================

factors = df.drop(["longitude", "latitude"], axis=1)
factor_cols = factors.columns.tolist()

n_cols = 3
n_rows = -(-len(factor_cols) // n_cols)  # ceiling division

fig, axes = plt.subplots(n_rows, n_cols, figsize=(15, n_rows * 3.5))
axes = axes.flatten()

for i, col in enumerate(factor_cols):
    sns.boxplot(x=factors[col], ax=axes[i], color="steelblue")
    axes[i].set_title(col, fontsize=11, fontweight="bold")
    axes[i].set_xlabel("")

# Hide unused subplots
for j in range(i + 1, len(axes)):
    axes[j].set_visible(False)

plt.suptitle("Landslide Conditioning Factors – Boxplots", fontsize=14, fontweight="bold", y=1.01)
plt.tight_layout()
plt.savefig(
    "../outputs/boxplots_all_factors.png",
    dpi=150,
    bbox_inches="tight"
)
plt.show()
print("Boxplot grid saved → ../outputs/boxplots_all_factors.png")

# =====================
# STEP 6: Remove outliers (IQR method)
# =====================

clean_df = factors.dropna().copy()

for col in clean_df.columns:
    Q1 = clean_df[col].quantile(0.25)
    Q3 = clean_df[col].quantile(0.75)
    IQR = Q3 - Q1
    lower = Q1 - 1.5 * IQR
    upper = Q3 + 1.5 * IQR
    clean_df = clean_df[(clean_df[col] >= lower) & (clean_df[col] <= upper)]

print(f"\nAfter removing outliers: {clean_df.shape}")



# =====================
# STEP 7: Correlation matrix + Heatmap
# =====================

corr = clean_df.corr()
print("\nCorrelation Matrix:\n", corr)
corr.to_csv("../processed/correlation_matrix.csv")

plt.figure(figsize=(9, 7))
sns.heatmap(
    corr,
    annot=True,
    fmt=".2f",
    cmap="coolwarm",
    vmin=-1,
    vmax=1,
    linewidths=0.5,
    square=True,
)
plt.title("Factor Correlation Heatmap", fontsize=13, fontweight="bold")
plt.tight_layout()
plt.savefig("../outputs/correlation_heatmap.png", dpi=150, bbox_inches="tight")
plt.show()
print("Heatmap saved → ../outputs/correlation_heatmap.png")

# =====================
# STEP 8: Distribution plots (KDE) – all in one page
# =====================

fig, axes = plt.subplots(n_rows, n_cols, figsize=(15, n_rows * 3.5))
axes = axes.flatten()

for i, col in enumerate(factor_cols):
    clean_df[col].plot.kde(ax=axes[i], color="darkorange")
    axes[i].set_title(col, fontsize=11, fontweight="bold")
    axes[i].set_xlabel("")

for j in range(i + 1, len(axes)):
    axes[j].set_visible(False)

plt.suptitle("Landslide Conditioning Factors – KDE Distributions", fontsize=14, fontweight="bold", y=1.01)
plt.tight_layout()
plt.savefig("../outputs/kde_all_factors.png", dpi=150, bbox_inches="tight")
plt.show()
print("KDE plots saved → ../outputs/kde_all_factors.png")

# =====================
# STEP 9: Save cleaned data
# =====================

clean_df.to_csv("../processed/clean_factor_dataset.csv", index=False)
print("\nAnalysis complete. Cleaned data → ../processed/clean_factor_dataset.csv")
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# =====================
# STEP 1: Load dataset
# =====================

df = pd.read_csv("landslide_factor_dataset.csv")

print("Dataset loaded\n")

# =====================
# STEP 2: Inspect data
# =====================

print(df.head())

print("\nShape:")
print(df.shape)

print("\nColumns:")
print(df.columns)

print("\nData types:")
print(df.dtypes)

# =====================
# STEP 3: Missing values
# =====================

print("\nMissing values:")

print(df.isnull().sum())

# =====================
# STEP 4: Statistical summary
# =====================

print("\nStatistical Summary")

print(df.describe())

# =====================
# STEP 5: Boxplots
# =====================

factors = df.drop(
    ["longitude","latitude"],
    axis=1
)

for col in factors.columns:

    plt.figure(figsize=(5,3))

    sns.boxplot(
        x=factors[col]
    )

    plt.title(col)

    plt.show()

# =====================
# STEP 6: Remove outliers
# =====================

clean_df = factors.copy()

for col in clean_df.columns:

    Q1 = clean_df[col].quantile(0.25)

    Q3 = clean_df[col].quantile(0.75)

    IQR = Q3 - Q1

    lower = Q1 - 1.5*IQR

    upper = Q3 + 1.5*IQR

    clean_df = clean_df[
        (clean_df[col] >= lower)
        &
        (clean_df[col] <= upper)
    ]

print("\nAfter removing outliers")

print(clean_df.shape)

# =====================
# STEP 7: Correlation
# =====================

corr = clean_df.corr()

print("\nCorrelation Matrix")

print(corr)

corr.to_csv(
    "correlation_matrix.csv"
)

# =====================
# STEP 8: Heatmap
# =====================

plt.figure(figsize=(8,6))

sns.heatmap(
    corr,
    annot=True,
    cmap="coolwarm",
    vmin=-1,
    vmax=1
)

plt.title("Factor Correlation")

plt.tight_layout()

plt.show()

# =====================
# STEP 9: Save cleaned data
# =====================

clean_df.to_csv(
    "clean_factor_dataset.csv",
    index=False
)

print("\nAnalysis completed.")
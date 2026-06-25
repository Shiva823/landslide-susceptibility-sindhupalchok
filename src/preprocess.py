import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler

# ==========================
# STEP 1: Load dataset
# ==========================

df = pd.read_csv("../processed/landslide_factor_dataset.csv")

print("Dataset loaded")
print(df.shape)

# ==========================
# STEP 2: Check missing values
# ==========================

print("\nMissing values:")
print(df.isnull().sum())

# ==========================
# STEP 3: Remove missing values
# ==========================

df = df.dropna()

print("\nAfter removing missing values:")
print(df.shape)

# ==========================
# STEP 4: Remove coordinates
# ==========================

features = df.drop(
    ["longitude", "latitude"],
    axis=1
)

# ==========================
# STEP 5: Check invalid values
# ==========================

print("\nMinimum values:")
print(features.min())

# Replace common NoData values

features.replace(
    [-9999, -999, -32768],
    np.nan,
    inplace=True
)

features = features.dropna()

# ==========================
# STEP 6: Feature Scaling
# ==========================

scaler = StandardScaler()

scaled_array = scaler.fit_transform(features)

scaled_df = pd.DataFrame(
    scaled_array,
    columns=features.columns
)

print("\nScaled Dataset:")
print(scaled_df.head())

# ==========================
# STEP 7: Save final dataset
# ==========================

scaled_df.to_csv(
    "../processed/final_training_dataset.csv",
    index=False
)

print("\nSaved:")
print("../processed/final_training_dataset.csv")

print("\nFinal shape:")
print(scaled_df.shape)
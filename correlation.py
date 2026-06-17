import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

# Read the dataset you created
df = pd.read_csv("landslide_factor_dataset.csv")

# Remove coordinate columns
corr_data = df.drop(
    ["longitude", "latitude"],
    axis=1
)

# Calculate correlation matrix
corr = corr_data.corr()

# Print correlation matrix
print(corr)

# Save correlation matrix
corr.to_csv("correlation_matrix.csv")

# Plot heatmap
plt.figure(figsize=(8, 6))

sns.heatmap(
    corr,
    annot=True,
    cmap="coolwarm",
    vmin=-1,
    vmax=1
)

plt.title("Correlation Matrix")
plt.tight_layout()

plt.show()

print("Correlation matrix saved successfully!")
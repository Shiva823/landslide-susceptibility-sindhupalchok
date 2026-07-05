# Susceptibility Validation Summary

## Outputs

- Classified raster: `D:\sindupalchok_landslide\outputs\maps\susceptibility_classes.tif`
- Validation map: `D:\sindupalchok_landslide\outputs\figures\fig7_susceptibility_validation.png`
- Class statistics chart: `D:\sindupalchok_landslide\outputs\figures\fig8_susceptibility_class_stats.png`
- Class summary table: `D:\sindupalchok_landslide\outputs\maps\susceptibility_class_summary.csv`
- Sampled landslide points: `D:\sindupalchok_landslide\outputs\maps\landslide_validation_points.csv`

## Key Findings

- Mean predicted susceptibility at landslide points: 0.799
- High + Very High zones contain 87.8% of cleaned landslide points.
- High + Very High zones cover 12.9% of valid map pixels.

## Class Summary

| class_value | class_label | probability_min | probability_max | pixel_count | area_percent | landslide_count | landslide_percent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Very Low | 0.000 | 0.200 | 1727469 | 55.354 | 6 | 0.541 |
| 2 | Low | 0.200 | 0.400 | 629255 | 20.163 | 32 | 2.885 |
| 3 | Moderate | 0.400 | 0.600 | 361329 | 11.578 | 97 | 8.747 |
| 4 | High | 0.600 | 0.800 | 264985 | 8.491 | 300 | 27.051 |
| 5 | Very High | 0.800 | 1.000 | 137728 | 4.413 | 674 | 60.775 |

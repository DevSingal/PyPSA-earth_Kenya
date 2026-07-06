import os
import geopandas as gpd
import pandas as pd
import xarray as xr
import matplotlib.pyplot as plt

# ==========================================
# 0. Setup: Publishable Aesthetics & Directories
# ==========================================
output_dir = "output_plots"
os.makedirs(output_dir, exist_ok=True)

plt.rcParams.update({
    'font.size': 12,
    'axes.titlesize': 16,
    'axes.labelsize': 12,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'font.family': 'sans-serif',
    'figure.autolayout': True,
    'axes.spines.top': False,
    'axes.spines.right': False
})

# ==========================================
# 1. Load Data
# ==========================================
regions = gpd.read_file("resources/bus_regions/regions_onshore.geojson")
solar_ds = xr.open_dataset("resources/renewable_profiles/profile_solar.nc")
onwind_ds = xr.open_dataset("resources/renewable_profiles/profile_onwind.nc")

# Country outline for raster overlaying
country_outline = regions.dissolve()

# ==========================================
# 2. Extract & Process Spatial Variables
# ==========================================
# A. High-Res Max Capacity (2D Rasters)
solar_potential = solar_ds['potential']
onwind_potential = onwind_ds['potential']

# B. Extract 1D Data and Convert to Pandas Series
solar_p_nom = solar_ds['p_nom_max'].to_series().rename('solar_p_nom')
onwind_p_nom = onwind_ds['p_nom_max'].to_series().rename('onwind_p_nom')

# Calculate Mean Capacity Factor over the time dimension (results in 1D profiles per bus)
solar_cf = solar_ds['profile'].mean(dim='time').to_series().rename('solar_cf')
onwind_cf = onwind_ds['profile'].mean(dim='time').to_series().rename('onwind_cf')

# Ensure IDs match cleanly as strings
regions['name'] = regions['name'].astype(str)
for df in [solar_p_nom, onwind_p_nom, solar_cf, onwind_cf]:
    df.index = df.index.astype(str)

# Merge all processed series into the GeoDataFrame
regions = regions.merge(solar_p_nom, left_on='name', right_index=True, how='left')
regions = regions.merge(onwind_p_nom, left_on='name', right_index=True, how='left')
regions = regions.merge(solar_cf, left_on='name', right_index=True, how='left')
regions = regions.merge(onwind_cf, left_on='name', right_index=True, how='left')

# Calculate area in km² using an equal-area projection for density calculations
regions['area_km2'] = regions.to_crs(epsg=6933).geometry.area / 1e6
regions['solar_density'] = regions['solar_p_nom'] / regions['area_km2']
regions['onwind_density'] = regions['onwind_p_nom'] / regions['area_km2']

# Helper function to maintain aesthetic consistency across axes
def format_map_axes(ax):
    ax.set_aspect('equal')
    ax.grid(color='grey', linestyle=':', linewidth=0.5, alpha=0.5)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")

# ==========================================
# 3. Plot 1: Voronoi Average Capacity Factor (Profiles)
# ==========================================
fig1, axes1 = plt.subplots(1, 2, figsize=(16, 8))

# Solar Capacity Factor Choropleth
regions.plot(column='solar_cf', ax=axes1[0], cmap='magma', 
             legend=True, legend_kwds={'label': 'Capacity Factor (p.u.)', 'shrink': 0.8},
             edgecolor='black', linewidth=0.3)
axes1[0].set_title("Solar: Region-Average Capacity Factor")
format_map_axes(axes1[0])

# Wind Capacity Factor Choropleth
regions.plot(column='onwind_cf', ax=axes1[1], cmap='viridis', 
             legend=True, legend_kwds={'label': 'Capacity Factor (p.u.)', 'shrink': 0.8},
             edgecolor='black', linewidth=0.3)
axes1[1].set_title("Onshore Wind: Region-Average Capacity Factor")
format_map_axes(axes1[1])

fig1.savefig(f"{output_dir}/01_Voronoi_CapacityFactor.png", dpi=300, bbox_inches='tight')
fig1.savefig(f"{output_dir}/01_Voronoi_CapacityFactor.pdf", bbox_inches='tight')

# ==========================================
# 4. Plot 2: High-Resolution Max Potential
# ==========================================
fig2, axes2 = plt.subplots(1, 2, figsize=(16, 8))

# Solar Raster
solar_potential.plot(ax=axes2[0], cmap='YlOrRd', cbar_kwargs={'label': 'Potential Capacity (MW)', 'shrink': 0.8})
country_outline.plot(ax=axes2[0], facecolor='none', edgecolor='black', linewidth=1.2)
axes2[0].set_title("Solar: Max Potential Layout")
format_map_axes(axes2[0])

# Wind Raster
onwind_potential.plot(ax=axes2[1], cmap='Blues', cbar_kwargs={'label': 'Potential Capacity (MW)', 'shrink': 0.8})
country_outline.plot(ax=axes2[1], facecolor='none', edgecolor='black', linewidth=1.2)
axes2[1].set_title("Onshore Wind: Max Potential Layout")
format_map_axes(axes2[1])

fig2.savefig(f"{output_dir}/02_HighRes_Potential.png", dpi=300, bbox_inches='tight')
fig2.savefig(f"{output_dir}/02_HighRes_Potential.pdf", bbox_inches='tight')

# ==========================================
# 5. Plot 3: Voronoi Potential Density
# ==========================================
fig3, axes3 = plt.subplots(1, 2, figsize=(16, 8))

# Solar Density
regions.plot(column='solar_density', ax=axes3[0], cmap='YlOrRd', 
             legend=True, legend_kwds={'label': 'Density (MW / km²)', 'shrink': 0.8},
             edgecolor='black', linewidth=0.3)
axes3[0].set_title("Solar: Voronoi Potential Density")
format_map_axes(axes3[0])

# Wind Density
regions.plot(column='onwind_density', ax=axes3[1], cmap='Blues', 
             legend=True, legend_kwds={'label': 'Density (MW / km²)', 'shrink': 0.8},
             edgecolor='black', linewidth=0.3)
axes3[1].set_title("Onshore Wind: Voronoi Potential Density")
format_map_axes(axes3[1])

fig3.savefig(f"{output_dir}/03_Voronoi_Density.png", dpi=300, bbox_inches='tight')
fig3.savefig(f"{output_dir}/03_Voronoi_Density.pdf", bbox_inches='tight')

print(f"Success: All 3 plot pairs saved to '{output_dir}/' in high-resolution PNG and vector PDF formats.")
plt.show()
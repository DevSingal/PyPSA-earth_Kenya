import os
import warnings
import geopandas as gpd
import matplotlib.pyplot as plt
import atlite
import rioxarray

# 1. Suppress the harmless atlite FutureWarnings so your terminal stays clean
warnings.simplefilter(action='ignore', category=FutureWarning)

# ==========================================
# 2. Setup Aesthetics and Output Directory
# ==========================================
output_dir = "output_plots"
os.makedirs(output_dir, exist_ok=True)

plt.rcParams.update({
    'font.size': 12, 'axes.titlesize': 16, 'axes.labelsize': 12,
    'figure.autolayout': True, 'axes.spines.top': False, 'axes.spines.right': False
})

# ==========================================
# 3. Load Kenya Boundary (Foolproof method)
# ==========================================
print("Loading geographic boundaries...")
regions_path = "resources/bus_regions/regions_onshore.geojson"
if not os.path.exists(regions_path):
    raise FileNotFoundError(f"Could not find {regions_path}")

regions = gpd.read_file(regions_path)

# Since your PyPSA-Earth model is already built for Kenya, 
# 'regions' contains exactly the Kenyan regions. We just dissolve them all
# to get the outer national boundary.
kenya_outline = regions.dissolve()
kenya_outline = kenya_outline.to_crs("EPSG:4326")

if kenya_outline.empty:
    raise ValueError("The regions_onshore.geojson file loaded as empty. Check your PyPSA resources.")

# ==========================================
# 4. Load Cutout and Compute Capacity Factors
# ==========================================
cutout_path = "cutouts/cutout-2013-era5.nc"
if not os.path.exists(cutout_path):
    raise FileNotFoundError(f"Cutout file not found at: {cutout_path}")

cutout = atlite.Cutout(cutout_path)

print("Calculating raw high-resolution capacity factors (this may take a moment)...")
# Using capacity_factor=True is the correct syntax for your Atlite version.
solar_cf_raw = cutout.pv(panel="CSi", orientation="latitude_optimal", capacity_factor=True)
onwind_cf_raw = cutout.wind(turbine="Vestas_V112_3MW", capacity_factor=True)

# ==========================================
# 5. Clip Exactly to Kenya's Borders
# ==========================================
print("Clipping raw grids strictly to Kenya's borders...")

# Define the spatial dimensions so rioxarray knows how to project the raster map
solar_cf_raw = solar_cf_raw.rio.set_spatial_dims(x_dim="x", y_dim="y").rio.write_crs("EPSG:4326")
onwind_cf_raw = onwind_cf_raw.rio.set_spatial_dims(x_dim="x", y_dim="y").rio.write_crs("EPSG:4326")

# Execute the geographic clip
solar_cf_kenya = solar_cf_raw.rio.clip(kenya_outline.geometry, kenya_outline.crs, drop=True)
onwind_cf_kenya = onwind_cf_raw.rio.clip(kenya_outline.geometry, kenya_outline.crs, drop=True)

# ==========================================
# 6. Create the High-Quality Visualizations
# ==========================================
print("Generating and saving plots...")
fig, axes = plt.subplots(1, 2, figsize=(16, 8))

def format_map(ax, title):
    ax.set_aspect('equal')
    ax.set_title(title, fontweight='bold', pad=15)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.grid(color='grey', linestyle=':', linewidth=0.5, alpha=0.4)

# Plot Solar CF Raster
solar_cf_kenya.plot(
    ax=axes[0], 
    cmap='magma_r', 
    cbar_kwargs={'label': 'Capacity Factor (p.u.)', 'shrink': 0.8}
)
kenya_outline.plot(ax=axes[0], facecolor='none', edgecolor='black', linewidth=1.5)
format_map(axes[0], "Solar: Raw High-Res Capacity Factor")

# Plot Onshore Wind CF Raster
onwind_cf_kenya.plot(
    ax=axes[1], 
    cmap='viridis', 
    cbar_kwargs={'label': 'Capacity Factor (p.u.)', 'shrink': 0.8}
)
kenya_outline.plot(ax=axes[1], facecolor='none', edgecolor='black', linewidth=1.5)
format_map(axes[1], "Onshore Wind: Raw High-Res Capacity Factor")

# Save configurations
fig.savefig(f"{output_dir}/Kenya_Raw_HighRes_CF.png", dpi=300, bbox_inches='tight')
fig.savefig(f"{output_dir}/Kenya_Raw_HighRes_CF.pdf", bbox_inches='tight')

print(f"Success! Map plots saved inside the '{output_dir}/' folder.")
plt.show()
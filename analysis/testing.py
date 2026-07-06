import pypsa
import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import cartopy.crs as ccrs

# =============================================================================
# 1. PATH CONFIGURATION
# =============================================================================
# Using the intermediate 104-bus network file (before clustering to 10)
NETWORK_104_PATH = "networks/elec.nc" 
REGIONS_104_PATH = "resources/bus_regions/regions_onshore.geojson"

# Fallback paths if the '_104' suffix isn't explicitly in your file names:
# NETWORK_104_PATH = "networks/elec.nc"
# REGIONS_104_PATH = "resources/2030_scenenario/bus_regions/regions_onshore_elec.geojson"

# =============================================================================
# 2. LOAD HIGH-RESOLUTION NETWORK & GEOMETRY
# =============================================================================
print("Loading the 104-bus network layer...")
n_104 = pypsa.Network(NETWORK_104_PATH)

print("Loading the 104-bus Voronoi regions...")
regions_104 = gpd.read_file(REGIONS_104_PATH)
regions_104 = regions_104.set_index('name')

# =============================================================================
# 3. EXTRACT AND COMPUTE CAPACITY FACTORS
# =============================================================================
print("Extracting hourly renewable profiles...")

# p_max_pu contains the hourly available capacity factor (0.0 to 1.0) for each generator
# We take the mean over the entire year to get the static layout value
if not n_104.generators_t.p_max_pu.empty:
    annual_cf = n_104.generators_t.p_max_pu.mean()
else:
    raise ValueError("p_max_pu is empty. Make sure you are loading a network file that has gone through 'build_renewable_profiles'.")

# Attach the computed averages back to the generator dataframe
gens = n_104.generators.copy()
gens['mean_cf'] = annual_cf

# Isolate the carriers
solar_gens = gens[gens.carrier == 'solar']
onwind_gens = gens[gens.carrier == 'onwind']

# Map the generator capacity factors back to their respective buses
# Groupby handles cases where a single bus might contain multiple weather sub-cells
regions_104['solar_cf'] = solar_gens.groupby('bus')['mean_cf'].mean()
regions_104['onwind_cf'] = onwind_gens.groupby('bus')['mean_cf'].mean()

# =============================================================================
# 4. PLOT VISUALIZATION
# =============================================================================
print("Generating publication-quality spatial plots...")
fig, axes = plt.subplots(
    1, 2, 
    figsize=(18, 9), 
    subplot_kw={'projection': ccrs.PlateCarree()}
)

# Plot 1: 104-Bus Solar Capacity Factor
regions_104.plot(
    column='solar_cf',
    ax=axes[0],
    cmap='YlOrRd',
    legend=True,
    legend_kwds={'label': "Annual Mean Capacity Factor", 'orientation': "horizontal", 'pad': 0.05},
    missing_kwds={'color': '#e0e0e0', 'label': 'Excluded Land / No Potential'},
    edgecolor='black',
    linewidth=0.4
)
axes[0].set_title('Solar Capacity Factor\n(104 Bus Resolution)', fontsize=14, fontweight='bold')
axes[0].axis('off')

# Plot 2: 104-Bus Onshore Wind Capacity Factor
regions_104.plot(
    column='onwind_cf',
    ax=axes[1],
    cmap='Blues',
    legend=True,
    legend_kwds={'label': "Annual Mean Capacity Factor", 'orientation': "horizontal", 'pad': 0.05},
    missing_kwds={'color': '#e0e0e0', 'label': 'Excluded Land / No Potential'},
    edgecolor='black',
    linewidth=0.4
)
axes[1].set_title('Onshore Wind Capacity Factor\n(104 Bus Resolution)', fontsize=14, fontweight='bold')
axes[1].axis('off')

# Overlay the actual bus nodes as scatter points to visually anchor the Voronoi centers
axes[0].scatter(n_104.buses.x, n_104.buses.y, color='black', s=8, alpha=0.6, transform=ccrs.PlateCarree())
axes[1].scatter(n_104.buses.x, n_104.buses.y, color='black', s=8, alpha=0.6, transform=ccrs.PlateCarree())

plt.tight_layout()

# Save the resulting figure
output_image = "kenya_104_bus_capacity_factors.png"
plt.savefig(output_image, dpi=300, bbox_inches='tight')
print(f"Plot successfully saved to {output_image}")
plt.show()
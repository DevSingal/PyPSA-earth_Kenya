import pypsa
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
from cartopy.io.img_tiles import OSM
import warnings
warnings.filterwarnings('ignore')

# 1. Load the Network
print("Loading the solved year-long network...")
network_path = "../results/2030_scenenario/networks/elec_s_4_ec_lcopt_Co2L-3h.nc"
n = pypsa.Network(network_path)

# Fix PyPSA string bug for pandas/plotting compatibility
for comp_name, comp in n.components.items():
    df = comp.static
    for col in df.select_dtypes(include=["string"]).columns:
        df[col] = df[col].astype(object)

# ==============================================================================
# SECTION 1: TERMINAL PRINTOUT (Direct Comparison to LCPDP Paper Metrics)
# ==============================================================================

# Time weights (because of 3h downsampling, every snapshot represents 3 hours of energy)
weightings = n.snapshot_weightings.generators

# 1. Demand Metrics (Matches Paper Fig 2)
total_demand_twh = (n.loads_t.p_set.sum(axis=1) * weightings).sum() / 1e6
peak_demand_gw = n.loads_t.p_set.sum(axis=1).max() / 1000

# 2. Energy Generation (Matches Paper Fig 5 & 7)
generation_twh = (n.generators_t.p.multiply(weightings, axis=0)).sum().groupby(n.generators.carrier).sum() / 1e6
total_generation = generation_twh.sum()

# 3. Capacity Metrics (Matches Paper Fig 3, 4 & 6)
capacity_gw = n.generators.groupby("carrier").p_nom_opt.sum() / 1000
storage_capacity_gw = n.storage_units.groupby("carrier").p_nom_opt.sum() / 1000

# 4. System Costs (Matches Paper Fig 8)
# Capital Costs (Annualized)
capex = (n.generators.p_nom_opt * n.generators.capital_cost).sum() + \
        (n.storage_units.p_nom_opt * n.storage_units.capital_cost).sum()
# Operational Costs (Marginal/Fuel/Variable)
opex = (n.generators_t.p.multiply(weightings, axis=0) * n.generators.marginal_cost).sum().sum()
total_cost_bln = (capex + opex) / 1e9

# 5. Grid Stability & Losses
# Load shedding (Blackouts)
if 'load' in n.generators_t.p.columns or 'load shedding' in generation_twh.index:
    ls_energy = generation_twh.get('load shedding', 0)
else:
    ls_energy = 0
# VRE Curtailment (Wind/Solar available vs actually dispatched)
vre_gens = n.generators[n.generators.carrier.isin(["onwind", "solar", "offwind"])].index
available_vre = (n.generators_t.p_max_pu[vre_gens] * n.generators.p_nom_opt[vre_gens]).multiply(weightings, axis=0).sum().sum() / 1e6
dispatched_vre = generation_twh.reindex(["onwind", "solar", "offwind"]).fillna(0).sum()
curtailment = available_vre - dispatched_vre

print("\n" + "="*50)
print("🇰🇪 LCPDP COMPARATIVE ANALYSIS: EXECUTIVE SUMMARY")
print("="*50)
print(f"Total Annual Demand:     {total_demand_twh:.2f} TWh")
print(f"Peak Demand:             {peak_demand_gw:.2f} GW")
print(f"Total System Cost:       ${total_cost_bln:.2f} Billion/Year")
print(f"Load Shedding (Deficit): {ls_energy:.4f} TWh")
print(f"VRE Curtailment:         {curtailment:.2f} TWh ({(curtailment/available_vre*100 if available_vre>0 else 0):.1f}% of available VRE)")
print("\n--- Installed Capacity (GW) ---")
print(capacity_gw.round(2))
print("--- Storage Capacity (GW) ---")
print(storage_capacity_gw.round(2))
print("\n--- Annual Generation Mix (TWh) ---")
print(generation_twh.round(2))
print("="*50 + "\n")


# ==============================================================================
# SECTION 2: PLOTTING VISUALIZATIONS
# ==============================================================================

# Define consistent colors
tech_colors = {
    'geothermal': 'darkred', 'solar': '#f9d002', 'onwind': '#235ebc', 
    'hydro': '#08ad97', 'ror': '#4adbc8', 'oil': 'purple', 'CCGT': 'brown',
    'OCGT': 'orange', 'biomass': 'green', 'coal': 'black', 'load shedding': 'red',
    'PHS': 'cyan', 'battery': 'lime'
}

# --- Plot 1: Annual Generation Mix (Pie Chart) ---
fig1, ax1 = plt.subplots(figsize=(8, 8))
# Filter out near-zero generation for a clean pie chart
gen_pie = generation_twh[generation_twh > 0.1]
colors_pie = [tech_colors.get(c, 'gray') for c in gen_pie.index]
ax1.pie(gen_pie, labels=gen_pie.index, autopct='%1.1f%%', startangle=140, colors=colors_pie)
ax1.set_title("Annual Generation Mix (TWh)\nCompare to Paper Fig 7", fontsize=14, fontweight='bold')

# --- Plot 2: 2-Week System Dispatch (The "Duck Curve" & Storage check) ---
# We take two weeks in March to see how the grid behaves dynamically
fig2, ax2 = plt.subplots(figsize=(14, 6))
start_date, end_date = "2013-03-01", "2013-03-14"
slice_gen = n.generators_t.p.loc[start_date:end_date]
slice_gen = slice_gen.T.groupby(n.generators.carrier).sum().T

# Add battery/PHS discharging to the generation stack
if not n.storage_units_t.p.empty:
    discharging = n.storage_units_t.p.loc[start_date:end_date].clip(lower=0)
    discharging = discharging.T.groupby(n.storage_units.carrier).sum().T
    slice_gen = pd.concat([slice_gen, discharging], axis=1).fillna(0)

# Total Demand Line
slice_demand = n.loads_t.p_set.loc[start_date:end_date].sum(axis=1)

colors_stack = [tech_colors.get(c, 'gray') for c in slice_gen.columns]
ax2.stackplot(slice_gen.index, slice_gen.T, labels=slice_gen.columns, colors=colors_stack, alpha=0.8)
ax2.plot(slice_demand.index, slice_demand, color='black', linewidth=2, label="Total Demand", linestyle="--")

ax2.set_ylabel("Power (MW)", fontsize=12)
ax2.set_title("14-Day Hourly Dispatch (March)\nShows how storage and renewables balance", fontsize=14, fontweight='bold')
ax2.legend(loc='upper left', bbox_to_anchor=(1, 1))
plt.xticks(rotation=45)
fig2.tight_layout()

# --- Plot 3: Transmission Flows ---
# Combines AC lines and DC links between the two spatial nodes
fig3, ax3 = plt.subplots(figsize=(12, 4))
if not n.lines.empty:
    line_flow = n.lines_t.p0.loc[start_date:end_date].sum(axis=1)
    ax3.plot(line_flow.index, line_flow, label="AC Lines Flow", color='green')
if not n.links.empty:
    # Filter out internal H2/Battery links
    spatial_links = n.links[~n.links.index.str.contains("H2|battery")].index
    if len(spatial_links) > 0:
        link_flow = n.links_t.p0.loc[start_date:end_date, spatial_links].sum(axis=1)
        ax3.plot(link_flow.index, link_flow, label="DC/Other Links Flow", color='blue')

ax3.axhline(0, color='black', linewidth=1)
ax3.set_ylabel("Flow (MW) [Positive = Node 0 -> Node 1]")
ax3.set_title("Transmission Interconnect Flows", fontsize=14, fontweight='bold')
ax3.legend()
fig3.tight_layout()

# --- Plot 4: OpenStreetMap Grid Topology ---
fig4, ax4 = plt.subplots(figsize=(10, 10), subplot_kw={"projection": OSM().crs})
ax4.set_extent([32.5, 42.5, -5.0, 5.5], crs=ccrs.PlateCarree())
ax4.add_image(OSM(), 7)

# Draw spatial links/lines
for line in n.lines.index:
    b0, b1 = n.lines.loc[line, ["bus0", "bus1"]]
    if b0 in n.buses.index and b1 in n.buses.index:
        x0, y0 = n.buses.loc[b0, ["x", "y"]]
        x1, y1 = n.buses.loc[b1, ["x", "y"]]
        ax4.plot([x0, x1], [y0, y1], color='darkgreen', linewidth=4, transform=ccrs.PlateCarree())

for link in n.links.index:
    b0, b1 = n.links.loc[link, ["bus0", "bus1"]]
    if b0 in n.buses.index and b1 in n.buses.index and "H2" not in b0 and "battery" not in b0:
        x0, y0 = n.buses.loc[b0, ["x", "y"]]
        x1, y1 = n.buses.loc[b1, ["x", "y"]]
        ax4.plot([x0, x1], [y0, y1], color='darkblue', linewidth=3, linestyle='--', transform=ccrs.PlateCarree())

# Draw Hubs
for bus in n.buses.index:
    if "H2" not in str(bus) and "battery" not in str(bus):
        x, y = n.buses.loc[bus, ["x", "y"]]
        ax4.scatter(x, y, color='red', s=300, zorder=5, transform=ccrs.PlateCarree(), edgecolors='black')
        ax4.text(x + 0.15, y + 0.15, str(bus), fontsize=14, fontweight='bold', 
                bbox=dict(facecolor='white', alpha=0.9, edgecolor='black'), transform=ccrs.PlateCarree(), zorder=6)

ax4.set_title("Geospatial Topology & Upgraded Transmission", fontsize=16, fontweight='bold')

plt.show()
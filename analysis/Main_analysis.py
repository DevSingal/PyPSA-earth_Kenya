import pypsa
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
import warnings
warnings.filterwarnings('ignore')
import folium
from folium import plugins

# ============================================================================
# LOAD THE NETWORK
# ============================================================================
# Update the path to your final result file
network_file = r"../results/2030_scenenario/networks/elec_s_10_ec_lcopt_Co2L-3H.nc"
n = pypsa.Network(network_file)

print("="*80)
print("COMPREHENSIVE ENERGY SYSTEM ANALYSIS - PYPSA-EARTH RESULTS")
print("="*80)

# ============================================================================
# 1. FINAL INSTALLED POWER MIX IN MW
# ============================================================================
print("\n" + "="*80)
print("1. FINAL INSTALLED POWER MIX IN MW")
print("="*80)

# Get generators data
generators = n.generators.copy()
generators['Capacity_MW'] = generators['p_nom_opt']

# Group by technology type (filter out link-based assets for now)
tech_capacity = generators.groupby('carrier')['Capacity_MW'].sum().sort_values(ascending=False)

print("\n Total Final Capacity by Technology (MW):")
print("-" * 50)
for tech, capacity in tech_capacity.items():
    print(f"  {tech:.<40} {capacity:>12.2f} MW")
print("-" * 50)
print(f"  {'TOTAL':.<40} {tech_capacity.sum():>12.2f} MW")

# Store total installed capacity
total_installed_capacity = tech_capacity.sum()

# ============================================================================
# 2. INSTALLED STORAGE IN MW
# ============================================================================
print("\n" + "="*80)
print("2. INSTALLED STORAGE IN MW")
print("="*80)

# Storage from storage units
storage_units = n.storage_units.copy()
storage_capacity = storage_units[storage_units['p_nom_opt'] > 0].copy()

print("\nStorage Units by Type (Power Capacity in MW):")
print("-" * 50)
if len(storage_capacity) > 0:
    storage_by_type = storage_capacity.groupby('carrier')['p_nom'].sum().sort_values(ascending=False)
    for storage_type, capacity in storage_by_type.items():
        print(f"  {storage_type:.<40} {capacity:>12.2f} MW")
    print("-" * 50)
    print(f"  {'TOTAL STORAGE POWER':.<40} {storage_by_type.sum():>12.2f} MW")
else:
    print("  No storage units found in the network")

# Energy capacity (MWh)
print("\nStorage Energy Capacity (MWh):")
print("-" * 50)
if len(storage_capacity) > 0:
    storage_energy = storage_capacity[storage_capacity['max_hours'] > 0].copy()
    storage_energy['energy_MWh'] = storage_energy['p_nom'] * storage_energy['max_hours']
    energy_by_type = storage_energy.groupby('carrier')['energy_MWh'].sum().sort_values(ascending=False)
    for storage_type, energy in energy_by_type.items():
        print(f"  {storage_type:.<40} {energy:>12.2f} MWh")
    print("-" * 50)
    print(f"  {'TOTAL STORAGE ENERGY':.<40} {energy_by_type.sum():>12.2f} MWh")

# ============================================================================
# 3. SPATIAL MAP OF KENYA WITH FINAL CLUSTERS
# ============================================================================
print("\n" + "="*80)
print("3. SPATIAL MAP OF KENYA WITH FINAL CLUSTERS")
print("="*80)

buses = n.buses.copy()
buses_in_kenya = buses[buses.index.str.contains('KE', case=False, na=False)]

print(f"\nTotal Clusters/Buses in Kenya: {len(buses_in_kenya)}")
print("\nCluster Locations (Latitude, Longitude):")
print("-" * 70)
for idx, row in buses_in_kenya.iterrows():
    generator_count = len(generators[generators['bus'] == idx])
    print(f"  {idx:.<30} Lat: {row['y']:>8.3f}, Lon: {row['x']:>8.3f} | Generators: {generator_count}")

# Create OpenStreetMap visualization using Folium
if len(buses_in_kenya) > 0:
    # Calculate map center
    avg_lat = buses_in_kenya['y'].mean()
    avg_lon = buses_in_kenya['x'].mean()
    
    # Create base map
    m = folium.Map(
        location=[avg_lat, avg_lon],
        zoom_start=6,
        tiles='OpenStreetMap'
    )
    
    # Get max capacity for color scaling
    max_capacity = generators.groupby('bus')['Capacity_MW'].sum().max()
    
    # Add cluster markers
    for idx, row in buses_in_kenya.iterrows():
        bus_generators = generators[generators['bus'] == idx]
        bus_capacity = bus_generators['Capacity_MW'].sum()
        
        if bus_capacity > 0:
            # Color based on capacity (normalized)
            normalized_capacity = bus_capacity / max_capacity
            if normalized_capacity > 0.75:
                color = 'darkred'
            elif normalized_capacity > 0.5:
                color = 'red'
            elif normalized_capacity > 0.25:
                color = 'orange'
            else:
                color = 'yellow'
            
            # Create power mix details
            power_mix_details = bus_generators.groupby('carrier')['Capacity_MW'].sum().sort_values(ascending=False)
            
            # Build HTML popup with detailed power mix
            popup_html = f"""
            <div style="font-family: Arial; width: 320px; background-color: #f8f9fa; border-radius: 8px; padding: 12px;">
                <h3 style="margin: 0 0 10px 0; color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 8px;">{idx}</h3>
                <p style="margin: 8px 0;"><b>Total Capacity:</b> <span style="color: #e74c3c;">{bus_capacity:.2f} MW</span></p>
                <p style="margin: 8px 0;"><b>Number of Generators:</b> {len(bus_generators)}</p>
                <hr style="margin: 10px 0; border: none; border-top: 1px solid #ecf0f1;">
                <p style="margin: 8px 0; font-weight: bold; color: #34495e;">Power Mix Breakdown:</p>
                <table style="width: 100%; margin: 8px 0; border-collapse: collapse;">
            """
            
            # Add each technology with alternating row colors
            for idx_carrier, (carrier, capacity) in enumerate(power_mix_details.items()):
                percentage = (capacity / bus_capacity) * 100
                row_bg = '#ecf0f1' if idx_carrier % 2 == 0 else '#ffffff'
                popup_html += f"""
                    <tr style="background-color: {row_bg};">
                        <td style="padding: 6px 8px; text-align: left;">{carrier}</td>
                        <td style="padding: 6px 8px; text-align: right; font-weight: bold;">{capacity:.2f} MW</td>
                        <td style="padding: 6px 8px; text-align: right; color: #3498db;">{percentage:.1f}%</td>
                    </tr>
                """
            
            popup_html += """
                </table>
            </div>
            """
            
            # Create circle marker (no popup - popup moved to label)
            folium.CircleMarker(
                location=[row['y'], row['x']],
                radius=np.sqrt(bus_capacity / 20),
                color=color,
                fill=True,
                fillColor=color,
                fillOpacity=0.7,
                weight=2,
                opacity=0.8
            ).add_to(m)
            
            # Add clean cluster name label on top of circle (with popup on click)
            label_html = f"""
            <div style='font-size: 12px; 
                        font-weight: bold; 
                        color: black; 
                        text-align: center; 
                        text-shadow: 1px 1px 2px rgba(0,0,0,0.6);
                        pointer-events: auto;
                        cursor: pointer;
                        width: 60px;
                        margin-left: -30px;'>
                {idx}
            </div>
            """
            
            folium.Marker(
                location=[row['y'], row['x']],
                icon=folium.DivIcon(html=label_html),
                popup=folium.Popup(popup_html, max_width=350)
            ).add_to(m)
    
    # Add a title using HTML
    title_html = '''
                 <div style="position: fixed; 
                     top: 10px; left: 50px; width: 400px; height: 80px; 
                     background-color: white; border:2px solid grey; z-index:9999; 
                     font-size:16px; font-weight: bold; padding: 10px">
                 Kenya - Network Clusters and Installed Capacity Distribution
                 </div>
                 '''
    m.get_root().html.add_child(folium.Element(title_html))
    
    # Save map
    m.save('./outputs/network_clusters_map_osm.html')
    print("\n[Interactive map saved to ./outputs/network_clusters_map_osm.html]")
    print("  Open this file in a web browser to view the OpenStreetMap visualization")

# ============================================================================
# 4. POWER TRANSFER BETWEEN CLUSTERS - ALL ROUTES
# ============================================================================
print("\n" + "="*80)
print("4. POWER TRANSFER BETWEEN CLUSTERS - ALL ROUTES")
print("="*80)

# Get lines connecting buses
lines = n.lines.copy()
links = n.links.copy()

print(f"\nNumber of transmission lines: {len(lines)}")
print(f"Number of multi-vector links: {len(links)}")

# Calculate power flows if time-series data exists
if n.snapshots is not None and len(n.snapshots) > 0:
    print(f"\nAnalyzing all power transfer routes between clusters...")
    print("-" * 140)
    
    # Get line flows
    if hasattr(n.lines_t, 'p0') and len(n.lines_t.p0) > 0:
        avg_flows = n.lines_t.p0.mean()
        max_flows = n.lines_t.p0.max()
        min_flows = n.lines_t.p0.min()
        
        # Sort by absolute average flow (to show all active routes)
        sorted_flows = avg_flows.abs().sort_values(ascending=False)
        
        print(f"\nTotal Number of Transmission Lines: {len(lines)}")
        print(f"Active Transfer Routes (with non-zero flow): {len(sorted_flows[sorted_flows > 0])}")
        print("\n" + "-" * 140)
        print(f"  {'From':<10} {'To':<10} {'Avg Flow (MW)':>18} {'Min Flow (MW)':>18} {'Max Flow (MW)':>18} {'Capacity (MW)':>18} {'Util. %':>10}")
        print("-" * 140)
        
        total_avg_flow = 0
        total_max_flow = 0
        active_routes = 0
        
        for line_idx in sorted_flows.index:
            avg_flow = avg_flows[line_idx]
            max_flow = max_flows[line_idx]
            min_flow = min_flows[line_idx]
            
            from_bus = lines.loc[line_idx, 'bus0']
            to_bus = lines.loc[line_idx, 'bus1']
            capacity = lines.loc[line_idx, 's_nom']
            
            # Calculate utilization
            utilization = (abs(avg_flow) / capacity * 100) if capacity > 0 else 0
            
            # Only print lines with non-zero flow
            if abs(avg_flow) > 0.01:  # 0.01 MW threshold to filter noise
                print(f"  {from_bus:<10} {to_bus:<10} {avg_flow:>18.2f} {min_flow:>18.2f} {max_flow:>18.2f} {capacity:>18.2f} {utilization:>9.1f}%")
                total_avg_flow += abs(avg_flow)
                total_max_flow += abs(max_flow)
                active_routes += 1
        
        print("-" * 140)
        print(f"  {'TOTALS':<10} {'':<10} {total_avg_flow:>18.2f} {'':<18} {total_max_flow:>18.2f} {lines['s_nom'].sum():>18.2f}")
        print(f"\n  Total Active Routes: {active_routes}")
        if active_routes > 0:
            print(f"  Average Flow per Route: {total_avg_flow/active_routes:.2f} MW")
        print(f"  Total Transmission Capacity: {lines['s_nom'].sum():.2f} MW")
        if lines['s_nom'].sum() > 0:
            print(f"  Network Utilization: {(total_avg_flow / lines['s_nom'].sum() * 100):.2f}%")
        
        # Summary statistics by direction
        print("\n" + "-" * 140)
        print("\nFlow Direction Analysis:")
        print("-" * 70)
        positive_flows = avg_flows[avg_flows > 0]
        negative_flows = avg_flows[avg_flows < 0]
        
        print(f"  Routes with forward flow (bus0 → bus1):  {len(positive_flows):>4} routes | Total: {positive_flows.sum():>10.2f} MW")
        print(f"  Routes with reverse flow (bus1 → bus0):  {len(negative_flows):>4} routes | Total: {negative_flows.sum():>10.2f} MW")
    else:
        print("  No line flow data available in the network")
else:
    print("  No time-series data available for flow analysis")

# ============================================================================
# 5. POWER DISPATCH BY TIME SERIES
# ============================================================================
print("\n" + "="*80)
print("5. POWER DISPATCH BY TIME SERIES")
print("="*80)

if n.snapshots is not None and len(n.snapshots) > 0:
    print(f"\nTime series length: {len(n.snapshots)} snapshots")
    print(f"Time period: {n.snapshots[0]} to {n.snapshots[-1]}")
    
    # Get generation by carrier
    if hasattr(n.generators_t, 'p') and len(n.generators_t.p) > 0:
        dispatch_data = n.generators_t.p.copy()
        
        # Group by carrier
        dispatch_by_carrier = pd.DataFrame()
        for carrier in generators['carrier'].unique():
            gen_carrier = generators[generators['carrier'] == carrier].index
            dispatch_by_carrier[carrier] = dispatch_data[gen_carrier].sum(axis=1)
        
        print("\nTotal Generation Statistics by Carrier:")
        print("-" * 70)
        
        total_energy = {}
        for carrier in dispatch_by_carrier.columns:
            energy_gwh = dispatch_by_carrier[carrier].sum() / 1000
            avg_mw = dispatch_by_carrier[carrier].mean()
            max_mw = dispatch_by_carrier[carrier].max()
            total_energy[carrier] = energy_gwh
            
            print(f"  {carrier:.<35} Avg: {avg_mw:>8.2f} MW | Max: {max_mw:>10.2f} MW | Total: {energy_gwh:>10.2f} GWh")
        
        total_gwh = sum(total_energy.values())
        print("-" * 70)
        print(f"  {'TOTAL GENERATION':.<35} Total: {total_gwh:>35.2f} GWh")
        
        # Demand profile
        if 'load' in n.buses_t.keys() and len(n.buses_t.load) > 0:
            print("\n\nDemand Profile Statistics:")
            print("-" * 70)
            
            total_demand = n.buses_t.load.sum().sum() / 1000  # Convert to GWh
            avg_demand = n.buses_t.load.sum(axis=1).mean()
            max_demand = n.buses_t.load.sum(axis=1).max()
            min_demand = n.buses_t.load.sum(axis=1).min()
            
            print(f"  {'Average Demand':.<35} {avg_demand:>10.2f} MW")
            print(f"  {'Peak Demand':.<35} {max_demand:>10.2f} MW")
            print(f"  {'Minimum Demand':.<35} {min_demand:>10.2f} MW")
            print(f"  {'Total Annual Demand':.<35} {total_demand:>10.2f} GWh")
    else:
        print("  No time-series generation data available")
else:
    print("  No time-series data in network")

# ============================================================================
# 6. POWER MIX AND INSTALLED CAPACITY AT EACH CLUSTER
# ============================================================================
print("\n" + "="*80)
print("6. POWER MIX AND INSTALLED CAPACITY AT EACH CLUSTER (EXISTING vs NEW)")
print("="*80)

print(f"\nDetailed Breakdown by Cluster (with Existing vs New Capacity):")
print("-" * 120)

cluster_data = {}
for bus_idx in buses_in_kenya.index:
    bus_generators = generators[generators['bus'] == bus_idx]
    
    if len(bus_generators) > 0:
        total_capacity = bus_generators['Capacity_MW'].sum()
        cluster_data[bus_idx] = {
            'total': total_capacity,
            'mix': bus_generators.groupby('carrier')['Capacity_MW'].sum().to_dict()
        }
        
        # Only print clusters with capacity
        if total_capacity > 0:
            print(f"\n  {bus_idx} - TOTAL CLUSTER CAPACITY: {total_capacity:.2f} MW")
            print(f"  {'-'*115}")
            
            # Calculate overall existing and new for this cluster
            if 'p_nom_extendable' in bus_generators.columns:
                cluster_existing = bus_generators[bus_generators['p_nom_extendable'] == False]['p_nom'].sum()
                cluster_new = bus_generators[bus_generators['p_nom_extendable'] == True]['p_nom'].sum()
                print(f"    Existing Infrastructure: {cluster_existing:>10.2f} MW | New/Extendable: {cluster_new:>10.2f} MW")
            
            print(f"  {'-'*115}")
            print(f"  {'Technology':<30} {'Existing (MW)':>15} {'New (MW)':>15} {'Total (MW)':>15} {'% of Cluster':>15}")
            print(f"  {'-'*115}")
            
            for carrier in sorted(bus_generators['carrier'].unique()):
                carrier_gens = bus_generators[bus_generators['carrier'] == carrier]
                total_carrier = carrier_gens['p_nom'].sum()
                
                if 'p_nom_extendable' in carrier_gens.columns:
                    existing = carrier_gens[carrier_gens['p_nom_extendable'] == False]['p_nom'].sum()
                    new = carrier_gens[carrier_gens['p_nom_extendable'] == True]['p_nom'].sum()
                else:
                    existing = total_carrier
                    new = 0.0
                
                percentage = (total_carrier / total_capacity) * 100 if total_capacity > 0 else 0
                print(f"    {carrier:<28} {existing:>15.2f} {new:>15.2f} {total_carrier:>15.2f} {percentage:>14.1f}%")

# ============================================================================
# 7. TECHNOLOGY COMPARISON: EXISTING vs INSTALLED AFTER OPTIMIZATION
# ============================================================================
print("\n" + "="*80)
print("7. TECHNOLOGY COMPARISON: EXISTING vs INSTALLED (AFTER OPTIMIZATION)")
print("="*80)

print("\nGenerator Status Analysis:")
print("-" * 70)

# Check for existence attribute
if 'build_year' in generators.columns:
    print("\nGenerators by Build Year (indicating existing infrastructure):")
    generators_with_year = generators[generators['build_year'].notna()].copy()
    
    if len(generators_with_year) > 0:
        existing_year = generators_with_year['build_year'].min()
        print(f"  Year range available in data: {existing_year:.0f} onwards")

# Check p_nom_opt vs p_nom for new vs existing
if 'p_nom_extendable' in generators.columns:
    extendable = generators[generators['p_nom_extendable'] == True]
    non_extendable = generators[generators['p_nom_extendable'] == False]
    
    print(f"\nCapacity Breakdown by Flexibility:")
    print("-" * 70)
    print(f"  Existing (Non-extendable) Capacity: {non_extendable['p_nom'].sum():.2f} MW")
    print(f"  New/Extendable Capacity: {extendable['p_nom'].sum():.2f} MW")
    print(f"  Total Capacity: {generators['p_nom'].sum():.2f} MW")

print(f"\nInstalled Capacity by Technology Type:")
print("-" * 70)
generators_sorted = generators.groupby('carrier')['p_nom'].sum().sort_values(ascending=False)

for carrier, capacity in generators_sorted.items():
    carrier_gen = generators[generators['carrier'] == carrier]
    
    if 'p_nom_extendable' in carrier_gen.columns:
        existing = carrier_gen[carrier_gen['p_nom_extendable'] == False]['p_nom'].sum()
        new = carrier_gen[carrier_gen['p_nom_extendable'] == True]['p_nom'].sum()
        total = capacity
        
        if total > 0:
            print(f"  {carrier:.<30}")
            print(f"    Existing: {existing:>10.2f} MW | New: {new:>10.2f} MW | Total: {total:>10.2f} MW")
    else:
        print(f"  {carrier:.<30} {capacity:>10.2f} MW")

print(f"\n  {'TOTAL':.<30} {generators['p_nom'].sum():>10.2f} MW")

# ============================================================================
# SUMMARY AND KEY METRICS
# ============================================================================
print("\n" + "="*80)
print("SUMMARY AND KEY METRICS")
print("="*80)

print(f"\nNetwork Overview:")
print("-" * 70)
print(f"  Number of Buses: {len(buses)}")
print(f"  Number of Buses in Kenya: {len(buses_in_kenya)}")
print(f"  Total Generators: {len(generators)}")
print(f"  Total Storage Units: {len(storage_units)}")
print(f"  Total Lines: {len(lines)}")
print(f"  Total Links: {len(links)}")

print(f"\nCapacity Summary:")
print("-" * 70)
print(f"  Total Installed Generation Capacity: {generators['p_nom'].sum():.2f} MW")
if len(storage_units) > 0:
    print(f"  Total Energy Storage Capacity: {(storage_units['p_nom'] * storage_units['max_hours']).sum():.2f} MWh")
print(f"  Network Loss Allowed: {lines['x'].sum() * 100:.2f}% (total reactance)")

if n.snapshots is not None and len(n.snapshots) > 0:
    print(f"\nTime Series Summary:")
    print("-" * 70)
    print(f"  Number of Time Steps: {len(n.snapshots)}")
    print(f"  Resolution: {(n.snapshots[1] - n.snapshots[0]).total_seconds() / 3600:.1f} hours")

# ============================================================================
# STACKED BAR PLOT OF TOTAL ENERGY PRODUCTION THROUGH THE YEAR
# ============================================================================
print("\n" + "="*80)
print("CREATING STACKED BAR PLOT OF ENERGY PRODUCTION")
print("="*80)

if n.snapshots is not None and len(n.snapshots) > 0:
    if hasattr(n.generators_t, 'p') and len(n.generators_t.p) > 0:
        dispatch_data = n.generators_t.p.copy()
        
        # Create monthly aggregation
        dispatch_data.index = pd.to_datetime(dispatch_data.index)
        monthly_data = dispatch_data.resample('MS').sum() / 1e3  # Convert to GWh
        
        # Group by carrier
        monthly_by_carrier = pd.DataFrame()
        for carrier in generators['carrier'].unique():
            gen_carrier = generators[generators['carrier'] == carrier].index
            carrier_data = dispatch_data[gen_carrier].sum(axis=1)
            monthly_by_carrier[carrier] = carrier_data.resample('MS').sum() / 1e3  # GWh
        
        # Create stacked bar plot
        fig, ax = plt.subplots(figsize=(16, 8))
        
        # Define colors for each technology
        colors = {
            'solar': '#FDB462',
            'onwind': '#80B1D3',
            'offwind-ac': '#1F78B4',
            'offwind-dc': '#0066CC',
            'hydro': '#4DAF4A',
            'CCGT': '#FF7F00',
            'coal': '#2C2C2C',
            'biomass': '#8B4513',
            'geothermal': '#D62728',
            'nuclear': '#E377C2',
            'oil': '#FF0000',
            'ror': '#9467BD',
        }
        
        # Get unique carriers and sort them
        carriers = sorted(monthly_by_carrier.columns)
        
        # Create bottom for stacking
        bottom = np.zeros(len(monthly_by_carrier))
        
        # Plot each carrier
        for carrier in carriers:
            color = colors.get(carrier, '#CCCCCC')
            ax.bar(range(len(monthly_by_carrier)), monthly_by_carrier[carrier], 
                   bottom=bottom, label=carrier, color=color, alpha=0.85, edgecolor='black', linewidth=0.5)
            bottom += monthly_by_carrier[carrier].values
        
        # Formatting
        ax.set_xlabel('Month', fontsize=13, weight='bold')
        ax.set_ylabel('Energy Production (GWh)', fontsize=13, weight='bold')
        ax.set_title('Total Energy Production by Technology - Monthly Aggregation', fontsize=15, weight='bold', pad=20)
        ax.set_xticks(range(len(monthly_by_carrier)))
        ax.set_xticklabels([date.strftime('%b') for date in monthly_by_carrier.index], fontsize=11)
        ax.legend(loc='upper left', bbox_to_anchor=(1.02, 1), fontsize=10, frameon=True, fancybox=True)
        ax.grid(True, alpha=0.3, axis='y')
        
        # Add value labels on top of bars
        for i, month_total in enumerate(bottom):
            ax.text(i, month_total + month_total*0.02, f'{month_total:.0f}', 
                   ha='center', va='bottom', fontsize=9, weight='bold')
        
        plt.tight_layout()
        plt.savefig('./outputs/energy_production_stacked_bar.png', dpi=300, bbox_inches='tight')
        print("\n[Stacked bar plot saved to ./outputs/energy_production_stacked_bar.png]")
        plt.close()
        
        # Print monthly summary
        print("\nMonthly Energy Production Summary (GWh):")
        print("-" * 100)
        print(f"  {'Month':<10}", end='')
        for carrier in carriers:
            print(f"{carrier:>12}", end='')
        print(f"{'Total':>12}")
        print("-" * 100)
        
        for idx, month in enumerate(monthly_by_carrier.index):
            month_str = month.strftime('%B')
            print(f"  {month_str:<10}", end='')
            for carrier in carriers:
                print(f"{monthly_by_carrier[carrier].iloc[idx]:>12.2f}", end='')
            print(f"{bottom[idx]:>12.2f}")
        
        print("-" * 100)
        print(f"  {'TOTAL':<10}", end='')
        for carrier in carriers:
            print(f"{monthly_by_carrier[carrier].sum():>12.2f}", end='')
        print(f"{monthly_by_carrier.sum().sum():>12.2f}")
    else:
        print("  No time-series generation data available for plotting")
else:
    print("  No time-series data available for plotting")

# ============================================================================
# 14-DAY POWER DISPATCH VISUALIZATION
# ============================================================================
print("\n" + "="*80)
print("CREATING 14-DAY POWER DISPATCH GRAPH")
print("="*80)

if n.snapshots is not None and len(n.snapshots) > 0:
    if hasattr(n.generators_t, 'p') and len(n.generators_t.p) > 0:
        dispatch_data = n.generators_t.p.copy()
        dispatch_data.index = pd.to_datetime(dispatch_data.index)
        
        # Extract 14 days from middle of year (not from start)
        total_days = (dispatch_data.index[-1] - dispatch_data.index[0]).days
        start_day = max(total_days // 2 - 7, 0)  # Start from middle, then back 7 days
        start_date = dispatch_data.index[0] + pd.Timedelta(days=start_day)
        end_date = start_date + pd.Timedelta(days=14)
        dispatch_14d = dispatch_data[(dispatch_data.index >= start_date) & (dispatch_data.index < end_date)]
        
        # Group by carrier
        dispatch_14d_by_carrier = pd.DataFrame()
        for carrier in generators['carrier'].unique():
            gen_carrier = generators[generators['carrier'] == carrier].index
            dispatch_14d_by_carrier[carrier] = dispatch_data.loc[dispatch_14d.index, gen_carrier].sum(axis=1) / 1e3  # Convert to GW
        
        # Get 2030 projected demand from CSV file
        demand_csv_path = r"../resources/2030_scenenario/demand_profiles.csv"
        try:
            demand_df = pd.read_csv(demand_csv_path, index_col=0)
            demand_df.index = pd.to_datetime(demand_df.index)
            
            # Sum demand across all districts/regions and convert to GW
            demand_df['total'] = demand_df.sum(axis=1) / 1e3  # Convert MW to GW
            
            # Extract the 14-day window
            demand_14d = demand_df.loc[(demand_df.index >= start_date) & (demand_df.index < end_date), 'total']
        except Exception as e:
            print(f"  Warning: Could not load 2030 demand data ({e}). Demand line will not be shown.")
            demand_14d = None
        
        # Create stacked area plot
        fig, ax = plt.subplots(figsize=(18, 9))
        
        # Define colors for each technology
        colors_dispatch = {
            'solar': '#FDB462',
            'onwind': '#80B1D3',
            'offwind-ac': '#1F78B4',
            'offwind-dc': '#0066CC',
            'hydro': '#4DAF4A',
            'CCGT': '#FF7F00',
            'coal': '#2C2C2C',
            'biomass': '#8B4513',
            'geothermal': '#D62728',
            'nuclear': '#E377C2',
            'oil': '#FF0000',
            'ror': '#9467BD',
            'OCGT': '#FF8C00',
            'load shedding': '#FF0000',
            'battery': '#9467BD',
        }
        
        # Get unique carriers present in 14-day data
        carriers_14d = [col for col in sorted(dispatch_14d_by_carrier.columns) 
                        if dispatch_14d_by_carrier[col].sum() > 0]
        
        # Create stacked area plot
        ax.stackplot(dispatch_14d_by_carrier.index, 
                    [dispatch_14d_by_carrier[carrier] for carrier in carriers_14d],
                    labels=carriers_14d,
                    colors=[colors_dispatch.get(carrier, '#CCCCCC') for carrier in carriers_14d],
                    alpha=0.8, edgecolor='black', linewidth=0.5)
        
        # Add demand line as black dashed line
        if demand_14d is not None:
            ax.plot(demand_14d.index, demand_14d.values, 
                   color='black', linestyle='--', linewidth=2.5, label='Total Demand', zorder=10)
        
        # Formatting
        ax.set_xlabel('Time (Date and Hour)', fontsize=13, weight='bold')
        ax.set_ylabel('Power (GW)', fontsize=13, weight='bold')
        ax.set_title(f'Power Dispatch Over 14 Days - Hourly Resolution\n({start_date.strftime("%Y-%m-%d")} to {(end_date - pd.Timedelta(hours=1)).strftime("%Y-%m-%d")})', 
                    fontsize=15, weight='bold', pad=20)
        ax.legend(loc='upper left', bbox_to_anchor=(1.02, 1), fontsize=10, frameon=True, fancybox=True)
        ax.grid(True, alpha=0.3, axis='y')
        
        # Format x-axis
        import matplotlib.dates as mdates
        ax.xaxis.set_major_locator(mdates.DayLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        ax.xaxis.set_minor_locator(mdates.HourLocator(interval=6))
        plt.xticks(rotation=45, ha='right')
        
        plt.tight_layout()
        plt.savefig('./outputs/power_dispatch_14days.png', dpi=300, bbox_inches='tight')
        print("\n[14-day power dispatch graph saved to ./outputs/power_dispatch_14days.png]")
        print(f"  Graph includes: Technology stacks + Black dashed line for Total Demand")
        plt.close()
        
        # Print 14-day statistics
        print(f"\n14-Day Power Dispatch Summary (GW):")
        print(f"Period: {start_date.strftime('%Y-%m-%d %H:%M')} to {(end_date - pd.Timedelta(hours=1)).strftime('%Y-%m-%d %H:%M')}")
        print("-" * 120)
        print(f"  {'Technology':<20} {'Average (GW)':>18} {'Min (GW)':>18} {'Max (GW)':>18} {'Std Dev (GW)':>18}")
        print("-" * 120)
        
        for carrier in carriers_14d:
            avg = dispatch_14d_by_carrier[carrier].mean()
            min_val = dispatch_14d_by_carrier[carrier].min()
            max_val = dispatch_14d_by_carrier[carrier].max()
            std_val = dispatch_14d_by_carrier[carrier].std()
            print(f"  {carrier:<20} {avg:>18.3f} {min_val:>18.3f} {max_val:>18.3f} {std_val:>18.3f}")
        
        print("-" * 120)
        total_avg = dispatch_14d_by_carrier[carriers_14d].sum(axis=1).mean()
        total_min = dispatch_14d_by_carrier[carriers_14d].sum(axis=1).min()
        total_max = dispatch_14d_by_carrier[carriers_14d].sum(axis=1).max()
        print(f"  {'TOTAL SUPPLY':<20} {total_avg:>18.3f} {total_min:>18.3f} {total_max:>18.3f}")
        
        # Demand statistics
        if demand_14d is not None:
            print("\nDemand Statistics:")
            print("-" * 120)
            print(f"  {'TOTAL DEMAND':<20} {demand_14d.mean():>18.3f} {demand_14d.min():>18.3f} {demand_14d.max():>18.3f} {demand_14d.std():>18.3f}")
            print(f"\nSupply-Demand Balance:")
            print(f"  Average Supply: {total_avg:.3f} GW")
            print(f"  Average Demand: {demand_14d.mean():.3f} GW")
            print(f"  Balance (Supply - Demand): {(total_avg - demand_14d.mean()):+.3f} GW")
        
        # Daily average analysis
        print(f"\n\nDaily Average Power Dispatch (GW):")
        print("-" * 100)
        dispatch_14d_by_carrier['Date'] = dispatch_14d_by_carrier.index.date
        daily_avg = dispatch_14d_by_carrier.groupby('Date')[carriers_14d].mean()
        
        print(f"  {'Date':<15}", end='')
        for carrier in carriers_14d:
            print(f"{carrier:>12}", end='')
        print(f"{'Supply':>12} {'Demand':>12}")
        print("-" * 100)
        
        for date, row in daily_avg.iterrows():
            print(f"  {str(date):<15}", end='')
            for carrier in carriers_14d:
                print(f"{row[carrier]:>12.3f}", end='')
            
            # Get daily demand if available
            daily_demand = demand_14d[demand_14d.index.date == date].mean() if demand_14d is not None else 0
            print(f"{row[carriers_14d].sum():>12.3f} {daily_demand:>12.3f}")
    else:
        print("  No time-series generation data available for 14-day analysis")
else:
    print("  No time-series data available for 14-day analysis")

print("\n" + "="*80)
print("ANALYSIS COMPLETE")
print("="*80)


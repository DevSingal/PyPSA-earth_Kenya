import xarray as xr
import numpy as np
import pandas as pd

# Load all renewable profile datasets
technologies = {
    "Solar": "resources/2030_scenenario/renewable_profiles/profile_solar.nc",
    "Onshore Wind": "resources/2030_scenenario/renewable_profiles/profile_onwind.nc",
    "Offshore Wind AC": "resources/2030_scenenario/renewable_profiles/profile_offwind-ac.nc",
    "Offshore Wind DC": "resources/2030_scenenario/renewable_profiles/profile_offwind-dc.nc",
    "Hydro": "resources/2030_scenenario/renewable_profiles/profile_hydro.nc",
}

datasets = {}
for name, path in technologies.items():
    try:
        datasets[name] = xr.open_dataset(path)
    except Exception as e:
        print(f"Error loading {name}: {e}")

# Global IRENA/GWEC benchmarks (typical capacity factors by technology)
irena_benchmarks = {
    "Solar": 0.15,  # Typical: 12-18% depending on location
    "Onshore Wind": 0.35,  # Typical: 30-40%
    "Offshore Wind AC": 0.42,  # Typical: 40-45%
    "Offshore Wind DC": 0.42,  # Typical: 40-45%
    "Hydro": 0.40,  # Typical: 35-50% depending on hydrology
}

print("=" * 80)
print("RENEWABLE PROFILES ANALYSIS - 2030 SCENARIO")
print("=" * 80)
print()

# Collect statistics for comparison
stats_data = []

for tech_name, dataset in datasets.items():
    print(f"\n{'─' * 80}")
    print(f"TECHNOLOGY: {tech_name.upper()}")
    print(f"{'─' * 80}")
    
    # Special handling for hydro (different data structure)
    if tech_name == "Hydro":
        # Hydro uses inflow data, not capacity factors
        if "inflow" not in dataset.data_vars:
            print("⚠ Hydro data structure not as expected (no inflow data)")
            continue
        
        inflow_spatial = dataset.inflow.mean("time")
        inflow_min = float(inflow_spatial.min())
        inflow_mean = float(inflow_spatial.mean())
        inflow_max = float(inflow_spatial.max())
        inflow_std = float(inflow_spatial.std())
        overall_inflow = float(dataset.inflow.mean().values)
        
        print(f"Number of Hydro Plants: {len(dataset.plant)}")
        print(f"\nInflow Distribution (spatial variation):")
        print(f"  Min:    {inflow_min:.6f}")
        print(f"  Mean:   {inflow_mean:.6f}")
        print(f"  Median: {float(inflow_spatial.median()):.6f}")
        print(f"  Max:    {inflow_max:.6f}")
        print(f"  Std:    {inflow_std:.6f}")
        print(f"\nNote: Hydro uses inflow profiles (not capacity factors)")
        print(f"This represents water availability for generation")
        print(f"Average normalized inflow: {overall_inflow:.6f}")
        print(f"\nIRENA Benchmark (typical hydro CF): 40% (0.40)")
        print("(Actual CF depends on reservoir design and management strategy)")
        
        stats_data.append({
            "Technology": tech_name,
            "Total Capacity (GW)": None,
            "CF Mean (%)": None,
            "CF Min (%)": None,
            "CF Max (%)": None,
            "Annual Energy (TWh)": None,
            "IRENA Benchmark (%)": 40.0,
            "Variance": inflow_std,
        })
        continue
    
    # Total potential capacity
    p_nom_max = dataset.p_nom_max.sum().values / 1e3  # Convert MW to GW
    print(f"Total Installable Capacity: {p_nom_max:.2f} GW")
    
    # Capacity factor statistics
    cf_spatial = dataset.profile.mean("time")  # Mean across time for each location
    cf_temporal = dataset.profile.mean(dim=[dim for dim in dataset.profile.dims if dim != "time"])  # Mean across space for each time
    
    cf_min = float(cf_spatial.min())
    cf_mean = float(cf_spatial.mean())
    cf_max = float(cf_spatial.max())
    cf_std = float(cf_spatial.std())
    
    # Overall temporal mean
    overall_cf = float(dataset.profile.mean().values)
    
    print(f"\nCapacity Factor Distribution (spatial variation):")
    print(f"  Min:    {cf_min:.4f} ({cf_min*100:.2f}%)")
    print(f"  Mean:   {cf_mean:.4f} ({cf_mean*100:.2f}%)")
    print(f"  Median: {float(cf_spatial.median()):.4f} ({float(cf_spatial.median())*100:.2f}%)")
    print(f"  Max:    {cf_max:.4f} ({cf_max*100:.2f}%)")
    print(f"  Std:    {cf_std:.4f}")
    print(f"\nOverall Average Capacity Factor: {overall_cf:.4f} ({overall_cf*100:.2f}%)")
    
    # Skip if no capacity available
    if p_nom_max == 0:
        print(f"⚠ No capacity available for {tech_name} in this scenario")
        stats_data.append({
            "Technology": tech_name,
            "Total Capacity (GW)": 0,
            "CF Mean (%)": overall_cf * 100,
            "CF Min (%)": cf_min * 100,
            "CF Max (%)": cf_max * 100,
            "Annual Energy (TWh)": 0,
            "IRENA Benchmark (%)": irena_benchmarks[tech_name] * 100,
            "Variance": cf_std,
        })
        continue
    
    # Annual energy potential
    annual_gwh = p_nom_max * overall_cf * 8760 / 1000  # GW * CF * hours/year / 1000 = TWh
    print(f"Annual Energy Potential: {annual_gwh:.2f} TWh (assuming full build-out)")
    
    # Benchmark comparison
    benchmark = irena_benchmarks[tech_name]
    diff = overall_cf - benchmark
    diff_pct = (diff / benchmark) * 100
    benchmark_status = "✓ IN LINE" if abs(diff_pct) < 20 else ("⚠ HIGHER" if diff > benchmark else "↓ LOWER")
    
    print(f"\nIRENA Benchmark: {benchmark:.4f} ({benchmark*100:.2f}%)")
    print(f"Difference: {diff:+.4f} ({diff_pct:+.1f}%) [{benchmark_status}]")
    
    stats_data.append({
        "Technology": tech_name,
        "Total Capacity (GW)": p_nom_max,
        "CF Mean (%)": cf_mean * 100,
        "CF Min (%)": cf_min * 100,
        "CF Max (%)": cf_max * 100,
        "Annual Energy (TWh)": annual_gwh,
        "IRENA Benchmark (%)": benchmark * 100,
        "Variance": cf_std,
    })

# Summary table
print("\n" + "=" * 80)
print("SUMMARY COMPARISON TABLE")
print("=" * 80)
df_summary = pd.DataFrame(stats_data)
print(df_summary.to_string(index=False))

print("\n" + "=" * 80)
print("KEY INSIGHTS & INTERPRETATION")
print("=" * 80)
print("""
📊 CAPACITY FACTOR INTERPRETATION:

1. SOLAR ENERGY
   • Capacity Factor: Time-averaged efficiency of solar panels
   • What it means: If your solar farm has 100 MW capacity and CF=15%, 
     it produces 15 MW average power over the year (accounting for clouds, 
     seasonal variation, day/night cycles)
   • Realistic range: 10-20% globally; ~15% is typical

2. ONSHORE WIND
   • Capacity Factor: How often the wind blows hard enough to generate power
   • What it means: 35% CF = produces 35% of maximum rated capacity on average
   • Realistic range: 25-45% depending on location and wind resource
   • Better CF = better locations with consistent wind

3. OFFSHORE WIND
   • Capacity Factor: Consistently higher than onshore (more stable ocean winds)
   • AC vs DC: Both should be similar; difference reflects transmission losses
   • What it means: Offshore wind "runs" more hours at full capacity
   • Realistic range: 40-50% in good locations

4. HYDROPOWER
   • Capacity Factor: Depends on rainfall and reservoir management
   • Variable: Can range from 30-50% depending on hydrological year
   • What it means: More predictable than wind/solar; can be changed seasonally
   • Realistic range: 35-50% for run-of-river or reservoir systems

5. GEOGRAPHIC VARIATION
   • High CF spatial variation = uneven distribution of renewable resources
   • Some locations ideal for solar, others for wind
   • Planning decision: Where to site new capacity for maximum efficiency

6. POTENTIAL VS INSTALLED
   • "Total Installable Capacity" = what COULD be built
   • With given CF and annual hours = actual energy available
   • Formula: Annual Energy (TWh) = Capacity (GW) × CF × 8.76 hours

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🌍 COMPARISON WITH GLOBAL BENCHMARKS:

The IRENA/GWEC benchmarks represent global averages:
• Values matching benchmarks: Your model is realistic ✓
• Values higher: Excellent resource location (sunny/windy area)
• Values lower: Conservative estimation or marginal sites included

A difference of ±20% from benchmarks is normal due to:
  - Regional climate differences
  - Technology mix variations
  - Spatial resolution of modeling
  - Seasonal hydrology patterns
""")

print("\n💡 NEXT STEPS:")
print("1. Compare annual potential (TWh) against national electricity demand")
print("2. Identify which technologies are most viable in your region")
print("3. Use CF variance to plan grid storage/balancing needs")
print("4. Cross-check with actual country statistics from IEA/IRENA databases")
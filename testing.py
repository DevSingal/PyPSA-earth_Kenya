import pypsa

# 1. Load your solved network
n = pypsa.Network("results/2030_scenenario/networks/elec_s_15_ec_lcopt_Co2L0.5-3h.nc")

# 2. Isolate the solar generators
solar = n.generators[n.generators.carrier == "solar"]

# 3. Calculate the average capacity factor (weather quality) for each node
cf = n.generators_t.p_max_pu[solar.index].mean()

# 4. Build the diagnostic table
diagnostics = solar[['p_nom_max', 'p_nom_opt', 'p_nom']].copy()
diagnostics['Capacity_Factor'] = cf

# 5. Sort by optimized capacity to put the "Winner" at the top
diagnostics = diagnostics.sort_values(by='p_nom_opt', ascending=False)

print(diagnostics)
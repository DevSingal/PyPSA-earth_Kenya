import pypsa

n = pypsa.Network("resources/2030_scenenario/demand_profile.csv")

# Annual demand in TWh
annual_twh = (
    n.loads_t.p_set
     .multiply(n.snapshot_weightings.generators, axis=0)
     .sum()
     .sum() / 1e6
)
peak_gw = n.loads_t.p_set.sum(axis=1).max() / 1e3

print(f"Annual demand: {annual_twh:.1f} TWh")
print(f"Peak demand:   {peak_gw:.1f} GW")
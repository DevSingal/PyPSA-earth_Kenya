import pypsa
import numpy as np


def main():
    n = pypsa.Network("networks/2030_scenenario/elec.nc")

    # Snapshots / time
    snaps = n.snapshots
    hours_total = float(n.snapshot_weightings.generators.sum())

    print("NETWORK SUMMARY")
    print("-" * 60)
    print(f"Network name: {n.name}")
    print(f"Snapshots: {len(snaps)}  ({snaps[0]} ... {snaps[-1]})")
    print(f"Total weighting hours: {hours_total:.1f}")

    # Components
    print("\nCOMPONENT COUNTS")
    print(f"  Buses:           {len(n.buses)}")
    print(f"  Generators:      {len(n.generators)}")
    print(f"  Lines:           {len(n.lines)}")
    print(f"  Links:           {len(n.links)}")
    print(f"  Loads:           {len(n.loads)}")
    print(f"  StorageUnits:    {len(n.storage_units)}")

    # Generator capacities by carrier
    print("\nGENERATION CAPACITIES (MW) by carrier")
    try:
        gen_cap = n.generators.groupby('carrier').p_nom.sum().sort_values(ascending=False)
        print(gen_cap.to_string())
        print(f"  Total installed capacity (MW): {gen_cap.sum():.1f}")
    except Exception:
        print("  No generator capacity data available")

    # Top generators
    if not n.generators.empty:
        print("\nTOP GENERATORS (by p_nom)")
        top = n.generators.nlargest(10, 'p_nom')[['bus', 'carrier', 'p_nom']]
        print(top.to_string())

    # Demand / Loads
    print("\nDEMAND STATISTICS")
    try:
        loads_t = n.loads_t.p_set
        # Annual demand in TWh
        annual_twh = (loads_t.multiply(n.snapshot_weightings.generators, axis=0).sum().sum() / 1e6)
        peak_gw = loads_t.sum(axis=1).max() / 1e3
        avg_gw = loads_t.sum(axis=1).mean() / 1e3
        print(f"  Annual demand: {annual_twh:.2f} TWh")
        print(f"  Peak demand:   {peak_gw:.2f} GW")
        print(f"  Average demand: {avg_gw:.2f} GW")
    except Exception:
        print("  No load time-series found")

    # Capacity factors by carrier from dispatch
    print("\nESTIMATED CAPACITY FACTORS (by carrier)")
    try:
        # Energy produced (MWh) per generator over period
        gen_energy = n.generators_t.p.multiply(n.snapshot_weightings.generators, axis=0).sum()
        energy_by_carrier = gen_energy.groupby(n.generators.carrier).sum()  # MW*h
        p_nom_by_carrier = n.generators.groupby('carrier').p_nom.sum()
        cf = (energy_by_carrier / (p_nom_by_carrier * hours_total)).fillna(0)
        # express as fraction
        for carrier, val in cf.sort_values(ascending=False).items():
            print(f"  {carrier:15s}: {val:.3f} ({val*100:.1f}%)")
    except Exception:
        print("  Could not compute capacity factors (missing time series)")

    # Transmission summary
    print("\nTRANSMISSION SUMMARY")
    try:
        if not n.lines.empty:
            print(f"  AC lines: {len(n.lines)} total")
            print(n.lines[['bus0','bus1','length','s_nom']].head(10).to_string())
        else:
            print("  No AC lines in network")
        if not n.links.empty:
            print(f"  Links: {len(n.links)}")
            print(n.links[['bus0','bus1','carrier','s_nom']].head(10).to_string())
    except Exception:
        print("  No transmission data available")

    # Quick comparison to Kenya (benchmarks)
    print("\nCOMPARISON TO KENYA 2023 STATS (benchmarks)")
    kenya_annual_twh = 52.0
    kenya_peak_gw = 7.5
    try:
        print(f"  Model annual demand: {annual_twh:.2f} TWh (Kenya: {kenya_annual_twh} TWh)")
        print(f"  Model peak demand:   {peak_gw:.2f} GW (Kenya: {kenya_peak_gw} GW)")
    except Exception:
        print("  Demand comparison not available")


if __name__ == '__main__':
    main()

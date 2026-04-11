import pypsa

n = pypsa.Network("networks/2030_scenenario/elec.nc")
print("Network name:", n.name)

print("\n--- Generators ---")
print("Count:", len(n.generators))
print("Columns:", list(n.generators.columns))
if 'p_nom' in n.generators.columns:
    print("Sum p_nom (MW):", float(n.generators.p_nom.sum()))
print("Has p_nom_opt?:", 'p_nom_opt' in n.generators.columns)
if 'p_nom_opt' in n.generators.columns:
    print("Sum p_nom_opt (MW):", float(n.generators.p_nom_opt.sum()))

print("\n--- Generator time-series ---")
if hasattr(n, 'generators_t') and hasattr(n.generators_t, 'p'):
    gtp = n.generators_t.p
    print("generators_t.p shape:", gtp.shape)
    try:
        print("generators_t.p total energy (MWh):", float(gtp.sum().sum()))
    except Exception as e:
        print("Error summing generators_t.p:", e)
    try:
        print("generators_t.p max value:", float(gtp.max().max()))
    except Exception:
        print("generators_t.p max value: None or not applicable")
    print("generators_t.p sum per generator (first 10):")
    print(gtp.sum().head(10))
else:
    print("No generators_t.p time-series present")

print("\n--- Loads ---")
print("Loads count:", len(n.loads))
if hasattr(n, 'loads_t') and hasattr(n.loads_t, 'p_set'):
    print("loads_t.p_set shape:", n.loads_t.p_set.shape)
    print("loads_t.p_set total energy (MWh):", float(n.loads_t.p_set.multiply(n.snapshot_weightings.generators, axis=0).sum().sum()))
    print("loads_t peak (MW):", float(n.loads_t.p_set.sum(axis=1).max()))
else:
    print("No loads_t.p_set present")

print("\n--- StorageUnits ---")
print("StorageUnits count:", len(n.storage_units))
if hasattr(n, 'storage_units_t') and hasattr(n.storage_units_t, 'p'):
    print("storage_units_t.p total energy:", float(n.storage_units_t.p.sum().sum()))
else:
    print("No storage_units_t.p present or empty")

print("\n--- Lines / Flows ---")
if hasattr(n, 'lines_t') and hasattr(n.lines_t, 'p0'):
    try:
        print("lines_t.p0 total:", float(n.lines_t.p0.sum().sum()))
    except Exception:
        print("lines_t.p0 present but could not sum")
else:
    print("No lines_t.p0 present")

print("\nSnapshot weighting hours sum:", float(n.snapshot_weightings.generators.sum()))

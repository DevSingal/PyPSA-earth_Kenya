<!--
SPDX-FileCopyrightText:  PyPSA-Earth and PyPSA-Eur Authors

SPDX-License-Identifier: AGPL-3.0-or-later
-->

# PyPSA-Kenya

This repository is a Kenya-focused PyPSA-Earth model. It keeps the PyPSA-Earth
workflow structure, but the active configuration is tailored to a single-country
Kenya electricity system study for 2030.

The current model is still exploratory. It is being used to test Kenya grid
clustering, domestic generation expansion, storage, transmission expansion, and
simplified electricity imports from neighbouring countries.

## Current Model Snapshot

- Country: Kenya (`KE`)
- Planning horizon: 2030
- Weather year / snapshots: 2013, sampled every 3 hours through the `Co2L-3h`
  option
- Active run folder: `kenya_test_runs`
- Current clustering experiment: 9 clustered buses
- CO2 baseline: 8 MtCO2/year for the Kenya power sector
- Main extendable technologies: solar, onshore wind, geothermal, AC/DC lines,
  and batteries
- Existing renewable capacities are estimated from IRENA statistics
- Operational reserves are enabled

The model uses the standard PyPSA-Earth workflow and data structure. Key
settings live in [config.yaml](config.yaml).

## Import Representation

Two simplified import technologies are currently represented through
[data/custom_powerplants.csv](data/custom_powerplants.csv):

| Import source | Capacity | Marginal cost |
| --- | ---: | ---: |
| Uganda | 50 MW | 75.32 EUR/MWh |
| Ethiopia | 400 MW | 48.958 EUR/MWh |

These are modelled as custom generators with zero capital cost and fixed import
capacity. This is a simplified representation, not a full neighbouring-country
interconnector model.

## Grid And Clustering Notes

The workflow uses OpenStreetMap-derived grid data through PyPSA-Earth. A recent
issue was that one clustered region around Nairobi appeared as an isolated
network island, preventing imports from affecting that part of the system.

The current configuration uses:

```yaml
cluster_options:
  simplify_network:
    s_threshold_fetch_isolated: 0.35
```

This fetches isolated network fragments back into the main grid before final
clustering. The current clustering setup is being tuned to balance:

- compact geographic regions,
- a distinct Nairobi/load-centre cluster,
- representation of high wind resource areas in northern Kenya,
- preservation of the Ethiopia DC import connection.

## Useful Commands

Build the current clustered network without solving:

```powershell
snakemake -j 1 networks/kenya_test_runs/elec_s_9.nc --forcerun cluster_network
```

Solve the current configured scenario:

```powershell
snakemake -j 1 results/kenya_test_runs/networks/elec_s_9_ec_lcopt_Co2L-3h.nc
```

Plot a solved run:

```powershell
python scripts/plot_kenya_run_results.py `
  --network results/kenya_test_runs/networks/elec_s_9_ec_lcopt_Co2L-3h.nc `
  --output-dir analysis/outputs/test_run_9clusters `
  --shapes-dir resources/kenya_test_runs/shapes `
  --bus-regions resources/kenya_test_runs/bus_regions/regions_onshore_elec_s_9.geojson
```

Plot only a clustered, unsolved network:

```powershell
python scripts/plot_kenya_run_results.py `
  --network networks/kenya_test_runs/elec_s_9.nc `
  --output-dir analysis/outputs/test_clustering_9 `
  --shapes-dir resources/kenya_test_runs/shapes `
  --bus-regions resources/kenya_test_runs/bus_regions/regions_onshore_elec_s_9.geojson
```

## Key Files

- [config.yaml](config.yaml): main model and scenario configuration
- [data/custom_powerplants.csv](data/custom_powerplants.csv): custom Uganda and
  Ethiopia import generators
- [scripts/add_electricity.py](scripts/add_electricity.py): electricity
  component construction and cost loading
- [scripts/simplify_network.py](scripts/simplify_network.py): network
  simplification and isolated-grid handling
- [scripts/plot_kenya_run_results.py](scripts/plot_kenya_run_results.py):
  Kenya-specific result and cluster plotting
- `analysis/outputs/`: generated plots and summaries

## Upstream

This project is based on
[PyPSA-Earth](https://github.com/pypsa-meets-earth/pypsa-earth), an open-source
global energy system modelling workflow built on
[PyPSA](https://github.com/PyPSA/PyPSA).

For installation, environment setup, and general workflow documentation, refer
to the upstream PyPSA-Earth documentation:

https://pypsa-earth.readthedocs.io/

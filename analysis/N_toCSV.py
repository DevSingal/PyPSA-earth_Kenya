#!/usr/bin/env python3
"""
Minimal helper: hard-code a PyPSA network path and load it.

Edit `NETWORK_PATH` below to point to your network file.
"""

from pathlib import Path
import logging
import pypsa

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def load_network(path: Path) -> pypsa.Network:
	logging.info("Loading PyPSA network from: %s", path)
	net = pypsa.Network(str(path))
	logging.info("Loaded network with %d snapshots and %d buses",
				 len(getattr(net, "snapshots", [])),
				 len(getattr(net, "buses", [])))
	return net



net_path = "../results/2030_scenenario/networks/elec_s_10_ec_lcopt_Co2L-3h.nc"


net = load_network(net_path)
    
print("Network generators time series data: ", net.generators_t.p)  # Example: print generator time series data

print("Network buses: ", net.buses)  # Example: print bus information

print("Exporting to CSV...")  # Inform the user that the export is starting
net.export_to_csv_folder("Network_CSV")  # Exports the network to a folder named "Network_CSV"
print("Export completed. CSV files are located in the 'Network_CSV' folder.")  # Inform the user that the export is complete


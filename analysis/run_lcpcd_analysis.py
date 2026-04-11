import os
import argparse
import warnings
warnings.filterwarnings('ignore')

import pypsa
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
from cartopy.io.img_tiles import OSM


def safe_groupby_sum(df, mapper):
    """Group columns of df by mapper (Series indexed by column names) and sum."""
    try:
        return df.groupby(mapper, axis=1).sum()
    except Exception:
        # fallback to transpose/groupby/transpose
        return df.T.groupby(mapper).sum().T


def main():
    parser = argparse.ArgumentParser(description="Headless LCPCD analysis runner saves CSVs/PNGs")
    default_net = os.path.join(os.path.dirname(__file__), '..', 'results', '2030_scenenario', 'networks', 'elec_s_4_ec_lcopt_Co2L-3h.nc')
    parser.add_argument('--network', default=default_net, help='Path to pypsa network .nc file')
    parser.add_argument('--outdir', default=os.path.join(os.path.dirname(__file__), 'outputs'), help='Directory to save outputs')
    args = parser.parse_args()

    network_path = os.path.abspath(args.network)
    outdir = os.path.abspath(args.outdir)
    os.makedirs(outdir, exist_ok=True)

    if not os.path.exists(network_path):
        print(f"Network file not found: {network_path}\nPlease provide the .nc network file path with --network or place it at the default location.")
        raise SystemExit(2)

    print(f"Loading network: {network_path}")
    n = pypsa.Network(network_path)

    # Fix PyPSA string bug for pandas/plotting compatibility
    for comp_name, comp in n.components.items():
        df = comp.static
        for col in df.select_dtypes(include=["string"]).columns:
            df[col] = df[col].astype(object)

    # Snapshot weightings (works for common PyPSA builds)
    try:
        weightings = n.snapshot_weightings.generators
    except Exception:
        weightings = n.snapshot_weightings

    # -------------------- INSTALLED CAPACITIES --------------------
    gen_col = 'p_nom_opt' if 'p_nom_opt' in n.generators.columns else 'p_nom'
    stor_col = 'p_nom_opt' if 'p_nom_opt' in n.storage_units.columns else 'p_nom'

    installed_generators = n.generators.groupby('carrier')[gen_col].sum().rename('capacity_MW')
    installed_storage = n.storage_units.groupby('carrier')[stor_col].sum().rename('capacity_MW')

    installed_generators.to_csv(os.path.join(outdir, 'installed_generators_MW.csv'))
    installed_storage.to_csv(os.path.join(outdir, 'installed_storage_MW.csv'))

    print(f"Saved installed capacities to {outdir}")

    # -------------------- DISPATCH PROFILE --------------------
    if hasattr(n, 'generators_t') and hasattr(n.generators_t, 'p'):
        gen_t = n.generators_t.p.copy()
        dispatch_by_carrier = safe_groupby_sum(gen_t, n.generators.carrier)
        dispatch_by_carrier.to_csv(os.path.join(outdir, 'dispatch_by_carrier_MW_timeseries.csv'))

        # Total demand
        if hasattr(n, 'loads_t') and hasattr(n.loads_t, 'p_set'):
            demand = n.loads_t.p_set.sum(axis=1)
            demand.to_frame('demand_MW').to_csv(os.path.join(outdir, 'demand_MW_timeseries.csv'))
        else:
            demand = None

        # 14-day slice from start
        try:
            start = dispatch_by_carrier.index.min()
            end = start + pd.Timedelta(days=14)
            slice_dispatch = dispatch_by_carrier.loc[start:end]
            slice_demand = demand.loc[start:end] if demand is not None else None
        except Exception:
            # fallback take first N rows (14 days worth depends on snapshot resolution); take first 14*8 snapshots (if 3h -> 8 per day)
            n_per_day = int(round(24.0 / ( (dispatch_by_carrier.index[1] - dispatch_by_carrier.index[0]).total_seconds() / 3600.0 ))) if len(dispatch_by_carrier.index)>1 else 8
            rows = min(len(dispatch_by_carrier.index), 14 * max(1, n_per_day))
            slice_dispatch = dispatch_by_carrier.iloc[:rows]
            slice_demand = demand.iloc[:rows] if demand is not None else None

        # Plot stackplot
        if not slice_dispatch.empty:
            fig, ax = plt.subplots(figsize=(14, 6))
            cols = slice_dispatch.columns.tolist()
            colors = plt.get_cmap('tab20')(np.linspace(0, 1, max(1, len(cols))))
            ax.stackplot(slice_dispatch.index, [slice_dispatch[c].values for c in cols], labels=cols, colors=colors, alpha=0.85)
            if slice_demand is not None:
                ax.plot(slice_demand.index, slice_demand.values, color='black', linewidth=2, linestyle='--', label='Total Demand')
            ax.set_ylabel('Power (MW)')
            ax.set_title('Dispatch: 14-day slice')
            ax.legend(loc='upper left', bbox_to_anchor=(1, 1))
            fig.savefig(os.path.join(outdir, 'dispatch_14day_stack.png'), bbox_inches='tight', dpi=150)
            plt.close(fig)

        print(f"Saved dispatch timeseries and 14-day plot to {outdir}")
    else:
        print('No generator time-series found in network (generators_t.p). Skipping dispatch output.')

    # -------------------- POWER MIX (ANNUAL) --------------------
    try:
        energy_by_gen = (n.generators_t.p.multiply(weightings, axis=0)).sum()
        generation_twh = energy_by_gen.groupby(n.generators.carrier).sum() / 1e6
        generation_twh.to_csv(os.path.join(outdir, 'annual_generation_by_carrier_TWh.csv'))

        # Pie chart
        gen_pie = generation_twh[generation_twh > 0.01]
        if not gen_pie.empty:
            fig, ax = plt.subplots(figsize=(8, 8))
            ax.pie(gen_pie, labels=gen_pie.index, autopct='%1.1f%%', startangle=140)
            ax.set_title('Annual Generation Mix (TWh)')
            fig.savefig(os.path.join(outdir, 'power_mix_pie.png'), bbox_inches='tight', dpi=150)
            plt.close(fig)

        print(f"Saved annual generation mix to {outdir}")
    except Exception as e:
        print('Failed to compute annual generation mix:', e)

    # -------------------- SPATIAL MAP (KENYA) --------------------
    try:
        fig4, ax4 = plt.subplots(figsize=(10, 10), subplot_kw={"projection": OSM().crs})
        ax4.set_extent([32.5, 42.5, -5.0, 5.5], crs=ccrs.PlateCarree())
        ax4.add_image(OSM(), 7)

        # Draw AC lines
        if hasattr(n, 'lines') and not n.lines.empty:
            for line in n.lines.index:
                try:
                    b0, b1 = n.lines.loc[line, ['bus0', 'bus1']]
                    if b0 in n.buses.index and b1 in n.buses.index:
                        x0, y0 = n.buses.loc[b0, ['x', 'y']]
                        x1, y1 = n.buses.loc[b1, ['x', 'y']]
                        if not (pd.isna(x0) or pd.isna(y0) or pd.isna(x1) or pd.isna(y1)):
                            ax4.plot([x0, x1], [y0, y1], color='darkgreen', linewidth=2, transform=ccrs.PlateCarree())
                except Exception:
                    continue

        # Draw links
        if hasattr(n, 'links') and not n.links.empty:
            for link in n.links.index:
                try:
                    b0, b1 = n.links.loc[link, ['bus0', 'bus1']]
                    if b0 in n.buses.index and b1 in n.buses.index:
                        x0, y0 = n.buses.loc[b0, ['x', 'y']]
                        x1, y1 = n.buses.loc[b1, ['x', 'y']]
                        if not (pd.isna(x0) or pd.isna(y0) or pd.isna(x1) or pd.isna(y1)):
                            ax4.plot([x0, x1], [y0, y1], color='darkblue', linewidth=2, linestyle='--', transform=ccrs.PlateCarree())
                except Exception:
                    continue

        # Draw buses
        for bus in n.buses.index:
            try:
                if 'H2' in str(bus) or 'battery' in str(bus):
                    continue
                x, y = n.buses.loc[bus, ['x', 'y']]
                if pd.isna(x) or pd.isna(y):
                    continue
                ax4.scatter(x, y, color='red', s=80, zorder=5, transform=ccrs.PlateCarree(), edgecolors='black')
                ax4.text(x + 0.15, y + 0.15, str(bus), fontsize=9, fontweight='bold', bbox=dict(facecolor='white', alpha=0.8, edgecolor='black'), transform=ccrs.PlateCarree(), zorder=6)
            except Exception:
                continue

        ax4.set_title('Geospatial Topology (Kenya extent)')
        fig4.savefig(os.path.join(outdir, 'kenya_spatial_map.png'), bbox_inches='tight', dpi=200)
        plt.close(fig4)
        print(f"Saved spatial map to {outdir}/kenya_spatial_map.png")
    except Exception as e:
        print('Failed to create spatial map (cartopy/osm tiles may require internet):', e)

    print('\nAnalysis complete. Outputs saved in:', outdir)


if __name__ == '__main__':
    main()

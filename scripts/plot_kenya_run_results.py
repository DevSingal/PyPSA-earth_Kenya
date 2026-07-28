"""Create quick diagnostic plots for a solved Kenya PyPSA-earth run.

The script reads a solved PyPSA network and writes five plots:

1. Cluster map with capacity, load, storage, and average line flow.
2. Installed generation capacity by cluster and carrier.
3. Annual generation by carrier.
4. Representative 14-day dispatch stack with demand.
5. Transmission flow duration curve.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import geopandas as gpd
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pypsa
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Wedge


DEFAULT_NETWORK = Path(
    "results/kenya_laptop_first_run/networks/elec_s_4_ec_lcopt_Co2L-3h.nc"
)
DEFAULT_OUTPUT_DIR = Path("analysis/outputs/kenya_laptop_first_run")
DEFAULT_SHAPES_DIR = Path("resources/kenya_laptop_first_run/shapes")
DEFAULT_BUS_REGIONS = Path(
    "resources/kenya_laptop_first_run/bus_regions/regions_onshore_elec_s_4.geojson"
)

TECH_COLORS = {
    "solar": "#E69F00",
    "onwind": "#56B4E9",
    "ror": "#009E73",
    "hydro": "#0072B2",
    "geothermal": "#D55E00",
    "oil": "#4D4D4D",
    "import_uganda": "#7B3294",
    "import_ethiopia": "#008837",
    "battery": "#CC79A7",
    "battery discharge": "#CC79A7",
    "hydro discharge": "#0072B2",
}

CLUSTER_COLORS = {
    "KE0 0": "#4E79A7",
    "KE0 1": "#F28E2B",
    "KE1 0": "#59A14F",
    "KE2 0": "#E15759",
}


def carrier_color(carrier: str) -> str:
    return TECH_COLORS.get(carrier, "#9aa0a6")


def cluster_color_map(names: pd.Series | list[str]) -> dict[str, str]:
    names = sorted(pd.Index(names).dropna().astype(str).unique())
    palette = list(plt.get_cmap("tab10").colors) + list(plt.get_cmap("Set2").colors)
    colors = {
        name: matplotlib.colors.to_hex(palette[i % len(palette)])
        for i, name in enumerate(names)
    }
    colors.update({name: color for name, color in CLUSTER_COLORS.items() if name in colors})
    return colors


def callout_offset(
    x: float,
    y: float,
    bounds: tuple[float, float, float, float],
    scale_x: float = 1.35,
    scale_y: float = 0.85,
) -> tuple[float, float]:
    xmin, xmax, ymin, ymax = bounds
    cx = (xmin + xmax) / 2
    cy = (ymin + ymax) / 2
    dx = scale_x if x >= cx else -scale_x
    dy = scale_y if y >= cy else -scale_y
    return dx, dy


def optimal_capacity(frame: pd.DataFrame, nominal_col: str = "p_nom") -> pd.Series:
    opt_col = f"{nominal_col}_opt"
    if opt_col in frame.columns:
        values = frame[opt_col].copy()
        if values.notna().any() and values.sum() > 0:
            return values.fillna(0)
    return frame[nominal_col].fillna(0)


def output_path(output_dir: Path, stem: str) -> Path:
    return output_dir / f"{stem}.png"


def save(fig: plt.Figure, path: Path) -> None:
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(path)


def set_nature_style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": "#222222",
            "axes.linewidth": 0.8,
            "axes.titlesize": 10,
            "axes.labelsize": 8,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "legend.fontsize": 7,
            "font.family": "DejaVu Sans",
            "savefig.dpi": 300,
        }
    )


def load_by_bus(n: pypsa.Network) -> pd.Series:
    if n.loads.empty or n.loads_t.p_set.empty:
        return pd.Series(dtype=float)
    return n.loads_t.p_set.sum().groupby(n.loads.bus).sum() / 1e3


def generation_capacity_by_bus(n: pypsa.Network) -> pd.DataFrame:
    if n.generators.empty:
        return pd.DataFrame()
    generators = n.generators.copy()
    generators["capacity"] = optimal_capacity(generators)
    return (
        generators.groupby(["bus", "carrier"])["capacity"]
        .sum()
        .unstack(fill_value=0)
        .sort_index()
    )


def storage_capacity_by_bus(n: pypsa.Network) -> pd.DataFrame:
    if n.storage_units.empty:
        return pd.DataFrame()
    storage_units = n.storage_units.copy()
    storage_units["capacity"] = optimal_capacity(storage_units)
    return (
        storage_units.groupby(["bus", "carrier"])["capacity"]
        .sum()
        .unstack(fill_value=0)
        .sort_index()
    )


def generation_by_carrier(n: pypsa.Network) -> pd.Series:
    if n.generators.empty or n.generators_t.p.empty:
        return pd.Series(dtype=float)
    return (n.generators_t.p.sum().groupby(n.generators.carrier).sum() / 1e3).sort_values(
        ascending=False
    )


def transmission_links(n: pypsa.Network) -> pd.DataFrame:
    if n.links.empty or "carrier" not in n.links.columns:
        return pd.DataFrame(index=n.links.index)
    carriers = n.links.carrier.fillna("").astype(str).str.lower()
    mask = carriers.isin({"dc", "b2b", "converter ac-dc", "hvdc"})
    return n.links.loc[mask]


def read_geodata(shapes_dir: Path, bus_regions_path: Path) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame]:
    country = gpd.read_file(shapes_dir / "country_shapes.geojson").to_crs("EPSG:4326")
    gadm = gpd.read_file(shapes_dir / "gadm_shapes.geojson").to_crs("EPSG:4326")
    regions = gpd.read_file(bus_regions_path).to_crs("EPSG:4326")
    return country, gadm, regions


def map_bounds(gdf: gpd.GeoDataFrame, pad: float = 0.35) -> tuple[float, float, float, float]:
    xmin, ymin, xmax, ymax = gdf.total_bounds
    return xmin - pad, xmax + pad, ymin - pad, ymax + pad


def add_scalebar(ax: plt.Axes, x: float, y: float, length_km: float = 200) -> None:
    length_deg = length_km / 111.32
    ax.plot([x, x + length_deg], [y, y], color="#222222", linewidth=1.2)
    ax.plot([x, x], [y - 0.045, y + 0.045], color="#222222", linewidth=1.0)
    ax.plot(
        [x + length_deg, x + length_deg],
        [y - 0.045, y + 0.045],
        color="#222222",
        linewidth=1.0,
    )
    ax.text(x + length_deg / 2, y + 0.08, f"{length_km:.0f} km", ha="center", va="bottom", fontsize=7)


def add_north_arrow(ax: plt.Axes, x: float, y: float) -> None:
    ax.annotate(
        "N",
        xy=(x, y + 0.55),
        xytext=(x, y),
        ha="center",
        va="center",
        fontsize=8,
        arrowprops={"arrowstyle": "-|>", "lw": 0.9, "color": "#222222"},
    )


def draw_pie_marker(
    ax: plt.Axes,
    x: float,
    y: float,
    values: pd.Series,
    radius: float,
    edgecolor: str,
    zorder: int = 7,
) -> None:
    values = values[values > 0]
    if values.empty:
        ax.add_patch(
            Circle((x, y), radius, facecolor="white", edgecolor=edgecolor, linewidth=1.0, zorder=zorder)
        )
        return

    start = 90.0
    total = float(values.sum())
    for carrier, value in values.items():
        theta = 360.0 * float(value) / total
        wedge = Wedge(
            (x, y),
            radius,
            start,
            start + theta,
            facecolor=carrier_color(carrier),
            edgecolor="white",
            linewidth=0.45,
            zorder=zorder,
        )
        ax.add_patch(wedge)
        start += theta
    ax.add_patch(
        Circle((x, y), radius, facecolor="none", edgecolor=edgecolor, linewidth=0.8, zorder=zorder + 1)
    )


def plot_cluster_map(
    n: pypsa.Network,
    output_dir: Path,
    shapes_dir: Path,
    bus_regions_path: Path,
) -> None:
    cap = generation_capacity_by_bus(n)
    storage = storage_capacity_by_bus(n)
    load = load_by_bus(n)
    country, gadm, regions = read_geodata(shapes_dir, bus_regions_path)
    bounds = map_bounds(country, pad=0.32)
    cluster_colors = cluster_color_map(regions["name"])
    cluster_count = len(regions)

    fig, ax = plt.subplots(figsize=(7.2, 7.2))
    country.plot(ax=ax, facecolor="#F7F7F4", edgecolor="#252525", linewidth=0.8, zorder=1)
    gadm.boundary.plot(ax=ax, color="#D6D6D0", linewidth=0.28, zorder=2)
    regions.boundary.plot(ax=ax, color="#9A9A93", linewidth=0.65, linestyle="-", zorder=3)

    if not n.lines.empty:
        line_flows = (
            n.lines_t.p0.abs().mean() if not n.lines_t.p0.empty else pd.Series(0, index=n.lines.index)
        )
        max_flow = max(float(line_flows.max()), 1.0)
        for line_name, line in n.lines.iterrows():
            b0 = n.buses.loc[line.bus0]
            b1 = n.buses.loc[line.bus1]
            flow = float(line_flows.get(line_name, 0.0))
            width = 0.8 + 3.8 * flow / max_flow
            ax.plot(
                [b0.x, b1.x],
                [b0.y, b1.y],
                color="#2F2F2F",
                linewidth=width,
                alpha=0.75,
                zorder=4,
            )
            ax.text(
                (b0.x + b1.x) / 2,
                (b0.y + b1.y) / 2,
                f"{flow:.0f} MW avg",
                fontsize=6.5,
                color="#222222",
                ha="center",
                va="bottom",
                bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.75, "pad": 1.0},
                zorder=9,
            )

    links = transmission_links(n)
    if not links.empty:
        link_flows = (
            n.links_t.p0[links.index].abs().mean()
            if not n.links_t.p0.empty
            else pd.Series(0, index=links.index)
        )
        max_link_flow = max(float(link_flows.max()), 1.0)
        for link_name, link in links.iterrows():
            b0 = n.buses.loc[link.bus0]
            b1 = n.buses.loc[link.bus1]
            flow = float(link_flows.get(link_name, 0.0))
            width = 1.0 + 4.2 * flow / max_link_flow
            ax.plot(
                [b0.x, b1.x],
                [b0.y, b1.y],
                color="#6A3D9A",
                linewidth=width,
                alpha=0.9,
                linestyle=(0, (5, 2)),
                zorder=5,
            )
            ax.text(
                (b0.x + b1.x) / 2,
                (b0.y + b1.y) / 2,
                f"{link.carrier} {flow:.0f} MW avg",
                fontsize=6.5,
                color="#4A235A",
                ha="center",
                va="top",
                bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.78, "pad": 1.0},
                zorder=9,
            )

    bus_totals = cap.sum(axis=1) if not cap.empty else pd.Series(dtype=float)
    carriers = list(cap.columns)

    fixed_label_offsets = {
        "KE0 0": (-2.65, -1.35),
        "KE1 0": (1.75, -1.45),
        "KE0 1": (1.25, 0.35),
        "KE2 0": (1.05, 0.95),
        "KE0 4": (2.15, 0.85),
    }
    marker_radius = {
        bus: 0.12 + 0.24 * np.sqrt(float(bus_totals.get(bus, 0.0)) / max(float(bus_totals.max()), 1.0))
        for bus in n.buses.index
    }

    for bus_name, bus in n.buses.iterrows():
        bus_capacity = float(bus_totals.get(bus_name, 0.0))
        values = cap.loc[bus_name] if bus_name in cap.index else pd.Series(dtype=float)

        ax.scatter(bus.x, bus.y, s=18, color="#111111", zorder=8)
        draw_pie_marker(
            ax,
            bus.x,
            bus.y,
            values,
            marker_radius[bus_name],
            edgecolor=cluster_colors.get(bus_name, "#222222"),
            zorder=6,
        )

        storage_text = "storage 0 MW"
        if not storage.empty and bus_name in storage.index:
            active_storage = storage.loc[bus_name]
            active_storage = active_storage[active_storage > 0]
            if not active_storage.empty:
                storage_text = "storage " + ", ".join(
                    f"{carrier}: {value:.0f} MW"
                    for carrier, value in active_storage.sort_values(ascending=False).items()
                )

        dx, dy = fixed_label_offsets.get(
            bus_name,
            callout_offset(float(bus.x), float(bus.y), bounds, scale_x=1.2, scale_y=0.75),
        )
        ax.annotate(
            f"{bus_name}\nload {load.get(bus_name, 0):.0f} GWh/a\ncapacity {bus_capacity:.0f} MW\n{storage_text}",
            xy=(bus.x, bus.y),
            xytext=(bus.x + dx, bus.y + dy),
            fontsize=7,
            ha="left" if dx > 0 else "right",
            va="center",
            linespacing=1.2,
            bbox={
                "boxstyle": "round,pad=0.28",
                "facecolor": "white",
                "edgecolor": cluster_colors.get(bus_name, "#222222"),
                "linewidth": 0.75,
                "alpha": 0.94,
            },
            arrowprops={
                "arrowstyle": "-",
                "lw": 0.65,
                "color": cluster_colors.get(bus_name, "#222222"),
                "shrinkA": 3,
                "shrinkB": 3,
            },
            zorder=10,
        )

    handles = [
        Line2D(
            [0],
            [0],
            marker="o",
            linestyle="",
            color=carrier_color(carrier),
            label=carrier,
            markersize=6,
        )
        for carrier in carriers
    ]
    line_handle = Line2D([0], [0], color="#2F2F2F", linewidth=1.8, label="AC line")
    region_handle = Line2D([0], [0], color="#9A9A93", linewidth=0.8, label="cluster boundary")
    link_handle = Line2D(
        [0],
        [0],
        color="#6A3D9A",
        linewidth=2.2,
        linestyle=(0, (5, 2)),
        label="DC/link",
    )
    if not links.empty:
        handles.append(link_handle)
    handles.extend([line_handle, region_handle])

    ax.legend(handles=handles, loc="lower left", frameon=False, ncol=2, title="Installed capacity")
    xmin, xmax, ymin, ymax = bounds
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    add_scalebar(ax, xmax - 2.25, ymin + 0.38, length_km=200)
    add_north_arrow(ax, xmax - 0.55, ymax - 1.05)
    ax.set_title(f"Kenya {cluster_count}-cluster electricity model")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_aspect("equal", adjustable="box")
    ax.tick_params(length=2.5, width=0.6)
    ax.spines[["top", "right"]].set_visible(False)

    fig.text(
        0.12,
        0.035,
        "Pie size is proportional to installed generation capacity. Labels show annual load, generation capacity, and storage power.",
        fontsize=6.5,
        color="#333333",
    )

    save(fig, output_path(output_dir, "01_cluster_map_capacity_load_flow"))


def plot_cluster_regions_map(
    n: pypsa.Network,
    output_dir: Path,
    shapes_dir: Path,
    bus_regions_path: Path,
) -> None:
    country, gadm, regions = read_geodata(shapes_dir, bus_regions_path)
    cap = generation_capacity_by_bus(n).sum(axis=1)
    load = load_by_bus(n)
    bounds = map_bounds(country, pad=0.32)
    cluster_colors = cluster_color_map(regions["name"])
    cluster_count = len(regions)

    fig, ax = plt.subplots(figsize=(7.2, 7.2))
    region_colors = [cluster_colors.get(name, "#999999") for name in regions["name"]]
    regions.plot(
        ax=ax,
        color=region_colors,
        alpha=0.34,
        edgecolor="white",
        linewidth=0.8,
        zorder=2,
    )
    country.boundary.plot(ax=ax, color="#222222", linewidth=0.9, zorder=4)
    gadm.boundary.plot(ax=ax, color="#6F6F6F", linewidth=0.18, alpha=0.35, zorder=3)

    fixed_label_offsets = {
        "KE0 0": (-2.0, -0.45),
        "KE1 0": (1.65, -0.55),
        "KE0 1": (1.25, 0.35),
        "KE2 0": (1.15, 0.65),
        "KE0 4": (1.85, 0.65),
    }

    for _, region in regions.iterrows():
        name = region["name"]
        x = float(region.get("x", region.geometry.representative_point().x))
        y = float(region.get("y", region.geometry.representative_point().y))
        ax.scatter(x, y, s=24, color="#111111", zorder=6)
        dx, dy = fixed_label_offsets.get(
            name,
            callout_offset(x, y, bounds, scale_x=1.15, scale_y=0.75),
        )
        ax.annotate(
            f"{name}\n{cap.get(name, 0):.0f} MW\n{load.get(name, 0):.0f} GWh/a",
            xy=(x, y),
            xytext=(x + dx, y + dy),
            ha="left" if dx > 0 else "right",
            va="center",
            fontsize=7,
            bbox={
                "facecolor": "white",
                "edgecolor": cluster_colors.get(name, "#222222"),
                "linewidth": 0.55,
                "alpha": 0.92,
                "pad": 2,
            },
            arrowprops={
                "arrowstyle": "-",
                "lw": 0.6,
                "color": cluster_colors.get(name, "#222222"),
                "shrinkA": 3,
                "shrinkB": 3,
            },
            zorder=7,
        )

    handles = [
        Line2D([0], [0], marker="s", linestyle="", color=color, label=name, markersize=7)
        for name, color in cluster_colors.items()
    ]
    ax.legend(handles=handles, title="Cluster region", frameon=False, loc="lower left")
    xmin, xmax, ymin, ymax = bounds
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    add_scalebar(ax, xmax - 2.25, ymin + 0.38, length_km=200)
    add_north_arrow(ax, xmax - 0.55, ymax - 1.05)
    ax.set_title(f"Onshore areas assigned to each of the {cluster_count} clusters")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_aspect("equal", adjustable="box")
    ax.tick_params(length=2.5, width=0.6)
    ax.spines[["top", "right"]].set_visible(False)
    fig.text(
        0.12,
        0.035,
        f"Regions are the PyPSA-earth clustered onshore bus regions from {bus_regions_path.name}.",
        fontsize=6.5,
        color="#333333",
    )

    save(fig, output_path(output_dir, "06_cluster_regions_map"))

def plot_capacity_by_cluster(n: pypsa.Network, output_dir: Path) -> None:
    cap = generation_capacity_by_bus(n)
    fig, ax = plt.subplots(figsize=(10, 6))

    if cap.empty:
        ax.text(0.5, 0.5, "No generation capacity data", ha="center", va="center")
    else:
        cap = cap.loc[:, cap.sum().sort_values(ascending=False).index]
        cap.plot(
            kind="bar",
            stacked=True,
            ax=ax,
            color=[carrier_color(c) for c in cap.columns],
            width=0.72,
        )
        ax.set_ylabel("Installed generation capacity [MW]")
        ax.set_xlabel("Cluster")
        ax.legend(title="Carrier", ncols=3, frameon=True)
        ax.grid(axis="y", alpha=0.25)

    ax.set_title("Installed Generation Capacity by Cluster")
    fig.tight_layout()
    save(fig, output_path(output_dir, "02_capacity_by_cluster"))


def plot_annual_generation(n: pypsa.Network, output_dir: Path) -> None:
    gen = generation_by_carrier(n)
    fig, ax = plt.subplots(figsize=(9, 5.5))

    if gen.empty:
        ax.text(0.5, 0.5, "No generation dispatch data", ha="center", va="center")
    else:
        gen.plot(
            kind="bar",
            ax=ax,
            color=[carrier_color(c) for c in gen.index],
            width=0.7,
        )
        ax.set_ylabel("Annual generation [GWh]")
        ax.set_xlabel("Carrier")
        ax.grid(axis="y", alpha=0.25)
        ax.bar_label(ax.containers[0], fmt="%.0f", padding=3, fontsize=8)

    ax.set_title("Annual Generation by Carrier")
    fig.tight_layout()
    save(fig, output_path(output_dir, "03_annual_generation_by_carrier"))


def dispatch_by_carrier(n: pypsa.Network) -> pd.DataFrame:
    parts = []

    if not n.generators.empty and not n.generators_t.p.empty:
        gen = pd.DataFrame(index=n.snapshots)
        for carrier, generators in n.generators.groupby("carrier").groups.items():
            gen[carrier] = n.generators_t.p.loc[:, list(generators)].sum(axis=1)
        parts.append(gen)

    if not n.storage_units.empty and not n.storage_units_t.p.empty:
        storage = pd.DataFrame(index=n.snapshots)
        for carrier, units in n.storage_units.groupby("carrier").groups.items():
            discharge = n.storage_units_t.p.loc[:, list(units)].clip(lower=0).sum(axis=1)
            if discharge.sum() > 0:
                storage[f"{carrier} discharge"] = discharge
        if not storage.empty:
            parts.append(storage)

    if not parts:
        return pd.DataFrame(index=n.snapshots)

    df = pd.concat(parts, axis=1)
    return df.loc[:, df.sum().sort_values(ascending=False).index]


def plot_dispatch_14day(n: pypsa.Network, output_dir: Path, start_date: str | None) -> None:
    dispatch = dispatch_by_carrier(n)
    demand = n.loads_t.p_set.sum(axis=1) if not n.loads_t.p_set.empty else pd.Series(dtype=float)

    fig, ax = plt.subplots(figsize=(14, 6.5))
    if dispatch.empty:
        ax.text(0.5, 0.5, "No dispatch data", ha="center", va="center")
    else:
        dispatch.index = pd.to_datetime(dispatch.index)
        demand.index = pd.to_datetime(demand.index)

        if start_date is None:
            first = dispatch.index.min()
            last = dispatch.index.max()
            start = first + (last - first) / 2 - pd.Timedelta(days=7)
        else:
            start = pd.Timestamp(start_date)
        end = start + pd.Timedelta(days=14)

        dispatch_window = dispatch.loc[(dispatch.index >= start) & (dispatch.index < end)]
        demand_window = demand.loc[(demand.index >= start) & (demand.index < end)]
        active = dispatch_window.loc[:, dispatch_window.sum() > 0]

        if active.empty:
            ax.text(0.5, 0.5, "No positive dispatch in selected window", ha="center", va="center")
        else:
            ax.stackplot(
                active.index,
                [active[c].values / 1e3 for c in active.columns],
                labels=active.columns,
                colors=[carrier_color(c) for c in active.columns],
                alpha=0.86,
                linewidth=0.2,
            )
            if not demand_window.empty:
                ax.plot(
                    demand_window.index,
                    demand_window.values / 1e3,
                    color="#111111",
                    linewidth=2.2,
                    linestyle="--",
                    label="demand",
                )
            ax.set_ylabel("Power [GW]")
            ax.set_xlabel("Date")
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
            ax.xaxis.set_minor_locator(mdates.HourLocator(interval=12))
            ax.legend(ncols=4, loc="upper left", frameon=True, fontsize=8)
            ax.grid(axis="y", alpha=0.25)
            fig.autofmt_xdate()

    ax.set_title("Representative 14-Day Dispatch and Demand")
    fig.tight_layout()
    save(fig, output_path(output_dir, "04_dispatch_14day"))


def plot_flow_duration(n: pypsa.Network, output_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 5.5))

    if n.lines.empty or n.lines_t.p0.empty:
        ax.text(0.5, 0.5, "No line flow data", ha="center", va="center")
    else:
        for line_name in n.lines.index:
            flow = n.lines_t.p0[line_name].abs().sort_values(ascending=False).reset_index(
                drop=True
            )
            duration = np.arange(1, len(flow) + 1) / len(flow) * 100
            capacity = float(n.lines.loc[line_name].get("s_nom_opt", n.lines.loc[line_name].s_nom))
            label = (
                f"{line_name}: {n.lines.loc[line_name].bus0} to "
                f"{n.lines.loc[line_name].bus1}"
            )
            ax.plot(duration, flow.values, label=label, linewidth=2)
            ax.axhline(capacity, color="#777777", linestyle=":", linewidth=1)

        ax.set_xlabel("Share of snapshots with at least this flow [%]")
        ax.set_ylabel("Absolute flow [MW]")
        ax.grid(True, alpha=0.25)
        ax.legend(frameon=True, fontsize=8)

    ax.set_title("Transmission Flow Duration Curve")
    fig.tight_layout()
    save(fig, output_path(output_dir, "05_transmission_flow_duration"))


def write_summary(n: pypsa.Network, output_dir: Path) -> None:
    lines = [
        "# Kenya laptop run quick summary",
        "",
        f"Network: {n.name or 'unnamed'}",
        f"Snapshots: {len(n.snapshots)}",
        f"Buses: {len(n.buses)}",
        f"Lines: {len(n.lines)}",
        f"Generators: {len(n.generators)}",
        f"Storage units: {len(n.storage_units)}",
        "",
        "## Installed generation capacity [MW]",
        generation_capacity_by_bus(n).sum().sort_values(ascending=False).round(3).to_string(),
        "",
        "## Annual generation [GWh]",
        generation_by_carrier(n).round(3).to_string(),
    ]
    summary_path = output_dir / "summary.md"
    summary_path.write_text("\n".join(lines), encoding="utf-8")
    print(summary_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--network",
        type=Path,
        default=DEFAULT_NETWORK,
        help=f"Solved network NetCDF path. Default: {DEFAULT_NETWORK}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for generated plots. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--shapes-dir",
        type=Path,
        default=DEFAULT_SHAPES_DIR,
        help=f"Directory containing country_shapes.geojson and gadm_shapes.geojson. Default: {DEFAULT_SHAPES_DIR}",
    )
    parser.add_argument(
        "--bus-regions",
        type=Path,
        default=DEFAULT_BUS_REGIONS,
        help=f"Cluster region GeoJSON path. Default: {DEFAULT_BUS_REGIONS}",
    )
    parser.add_argument(
        "--dispatch-start",
        default=None,
        help="Optional start date for the 14-day dispatch plot, e.g. 2013-07-01.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    n = pypsa.Network(args.network)

    set_nature_style()

    plot_cluster_map(n, args.output_dir, args.shapes_dir, args.bus_regions)
    plot_capacity_by_cluster(n, args.output_dir)
    plot_annual_generation(n, args.output_dir)
    plot_dispatch_14day(n, args.output_dir, args.dispatch_start)
    plot_flow_duration(n, args.output_dir)
    plot_cluster_regions_map(n, args.output_dir, args.shapes_dir, args.bus_regions)
    write_summary(n, args.output_dir)


if __name__ == "__main__":
    main()

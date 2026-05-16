"""
Busmap & Pre-Clustering Network Analysis
=========================================
Loads the busmap CSV and the pre-clustering simplified network (elec_s.nc)
to show every original node, what cluster it maps to, and its load/generation.

FILES USED  (adjust RUN_NAME and SIMPL/CLUSTERS to match your run)
------------------------------------------------------------------
  resources/<RUN_NAME>/bus_regions/busmap_elec_s<SIMPL>_<CLUSTERS>.csv
  networks/<RUN_NAME>/elec_s<SIMPL>.nc          ← pre-clustering network
  networks/<RUN_NAME>/elec_s<SIMPL>_<CLUSTERS>.nc  ← post-clustering network
"""

import pandas as pd
import pypsa
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import os

# ─────────────────────────────────────────────
# CONFIG  –  edit these three lines only
# ─────────────────────────────────────────────
RUN_NAME = "2030_scenenario"   # value of run: name in config.yaml
SIMPL    = ""                  # simpl wildcard (usually empty string "")
CLUSTERS = "10"                # clusters wildcard

BASE = "."                     # repo root; change if running from elsewhere
# ─────────────────────────────────────────────

RDIR        = f"{RUN_NAME}/" if RUN_NAME else ""
BUSMAP_PATH = f"../resources/{RDIR}bus_regions/busmap_elec_s{SIMPL}_{CLUSTERS}.csv"
PRE_NET     = f"../networks/{RDIR}elec_s{SIMPL}.nc"
POST_NET    = f"../networks/{RDIR}elec_s{SIMPL}_{CLUSTERS}.nc"
REGIONS     = f"../resources/{RDIR}bus_regions/regions_onshore_elec_s{SIMPL}_{CLUSTERS}.geojson"
OUT_DIR     = "analysis/outputs/busmap_analysis"

os.makedirs(OUT_DIR, exist_ok=True)

# ══════════════════════════════════════════════════════════════════════════════
# 1. LOAD FILES
# ══════════════════════════════════════════════════════════════════════════════
print("=" * 70)
print("BUSMAP ANALYSIS")
print("=" * 70)

missing = [p for p in [BUSMAP_PATH, PRE_NET, POST_NET] if not os.path.exists(p)]
if missing:
    print("\n⚠  The following files were not found:")
    for p in missing:
        print(f"   {p}")
    print("\nCheck that RUN_NAME / SIMPL / CLUSTERS match your run wildcards.")
    print("Common path pattern if no 'results/' subfolder is used:")
    print("  resources/bus_regions/busmap_elec_s_10.csv")
    raise SystemExit(1)

print(f"\nLoading busmap  : {BUSMAP_PATH}")
busmap = pd.read_csv(BUSMAP_PATH, index_col=0).squeeze("columns")
busmap.index = busmap.index.astype(str)
busmap.name   = "cluster"

print(f"Loading pre-clustering network : {PRE_NET}")
n_pre = pypsa.Network(PRE_NET)

print(f"Loading post-clustering network: {POST_NET}")
n_post = pypsa.Network(POST_NET)

n = pypsa.Network("../networks/2030_scenenario/elec_s_10.nc")  # post-clustering

gen = n.generators[["bus", "carrier", "p_nom", "p_nom_opt",
                     "p_nom_extendable", "p_nom_min"]].copy()

# Existing = non-extendable (fixed infrastructure) OR extendable with p_nom_min > 0
gen["existing_MW"] = gen.apply(
    lambda r: r["p_nom"] if not r["p_nom_extendable"] else r["p_nom_min"], axis=1
)

# New capacity added by optimiser
gen["new_MW"] = gen.apply(
    lambda r: 0 if not r["p_nom_extendable"] else max(0, r["p_nom_opt"] - r["p_nom_min"]),
    axis=1
)

gen["total_opt_MW"] = gen.apply(
    lambda r: r["p_nom"] if not r["p_nom_extendable"] else r["p_nom_opt"], axis=1
)

# ── Per cluster × carrier breakdown ──────────────────────────────────
pivot_existing = gen.pivot_table(values="existing_MW", index="bus",
                                  columns="carrier", aggfunc="sum", fill_value=0)
pivot_new      = gen.pivot_table(values="new_MW",      index="bus",
                                  columns="carrier", aggfunc="sum", fill_value=0)
pivot_total    = gen.pivot_table(values="total_opt_MW", index="bus",
                                  columns="carrier", aggfunc="sum", fill_value=0)

print("=== EXISTING CAPACITY BY CLUSTER (MW) ===")
print(pivot_existing.round(1).to_string())

print("\n=== NEW CAPACITY ADDED BY OPTIMISER (MW) ===")
print(pivot_new.round(1).to_string())

print("\n=== TOTAL OPTIMISED CAPACITY (MW) ===")
print(pivot_total.round(1).to_string())

# Save
pivot_existing.to_csv("analysis/outputs/busmap_analysis/existing_capacity.csv")
pivot_new.to_csv("analysis/outputs/busmap_analysis/new_capacity.csv")
pivot_total.to_csv("analysis/outputs/busmap_analysis/total_optimised_capacity.csv")

# ══════════════════════════════════════════════════════════════════════════════
# 2. BUSMAP OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("1. BUSMAP OVERVIEW")
print("=" * 70)

n_orig    = len(busmap)
n_clusters = busmap.nunique()
print(f"\n  Original buses (pre-clustering) : {n_orig}")
print(f"  Resulting clusters              : {n_clusters}")
print(f"\n  Buses per cluster:")
counts = busmap.value_counts().sort_index()
for cluster, cnt in counts.items():
    print(f"    {cluster:<25}  →  {cnt:>4} original buses")

# ══════════════════════════════════════════════════════════════════════════════
# 3. FULL NODE TABLE  –  every original bus with its cluster + load + generation
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("2. EVERY ORIGINAL NODE  →  CLUSTER + LOAD + GENERATION")
print("=" * 70)

buses = n_pre.buses[["x", "y", "country", "carrier"]].copy()
buses.index = buses.index.astype(str)
buses["cluster"] = busmap.reindex(buses.index)

# Average load at each original bus (MW)
if not n_pre.loads_t.p_set.empty:
    avg_load = (
        n_pre.loads_t.p_set.mean()
        .rename_axis("load")
        .to_frame("avg_load_MW")
    )
    load_bus = n_pre.loads[["bus"]].join(avg_load)
    load_by_bus = load_bus.groupby("bus")["avg_load_MW"].sum()
else:
    load_by_bus = pd.Series(0.0, index=buses.index)

buses["avg_load_MW"] = load_by_bus.reindex(buses.index, fill_value=0.0)

# Installed p_nom at each original bus, by carrier
gen = n_pre.generators[["bus", "carrier", "p_nom", "p_nom_extendable"]].copy()
gen["bus"] = gen["bus"].astype(str)
p_nom_by_bus = gen.groupby("bus")["p_nom"].sum().rename("total_p_nom_MW")
buses["total_gen_MW"] = p_nom_by_bus.reindex(buses.index, fill_value=0.0)

# Dominant carrier
dominant = gen.groupby("bus").apply(
    lambda g: g.loc[g["p_nom"].idxmax(), "carrier"] if g["p_nom"].sum() > 0 else "none"
)
buses["dominant_carrier"] = dominant.reindex(buses.index, fill_value="none")

print(f"\n{'Bus':<30} {'Cluster':<25} {'Lat':>7} {'Lon':>7} "
      f"{'Load(MW)':>10} {'Gen(MW)':>10} {'Dom. Carrier':<18}")
print("-" * 110)
for bus, row in buses.sort_values("cluster").iterrows():
    print(f"  {bus:<28} {str(row['cluster']):<25} {row['y']:>7.3f} {row['x']:>7.3f} "
          f"{row['avg_load_MW']:>10.2f} {row['total_gen_MW']:>10.2f} {row['dominant_carrier']:<18}")

# Save full table
node_table_path = f"{OUT_DIR}/all_nodes_with_clusters.csv"
buses.to_csv(node_table_path)
print(f"\n  ✓ Full node table saved to: {node_table_path}")

# ══════════════════════════════════════════════════════════════════════════════
# 4. PER-CLUSTER SUMMARY  –  load, generation, carriers, bus count
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("3. PER-CLUSTER SUMMARY")
print("=" * 70)

cluster_summary = (
    buses.groupby("cluster")
    .agg(
        n_buses       =("avg_load_MW", "count"),
        total_load_MW =("avg_load_MW", "sum"),
        total_gen_MW  =("total_gen_MW", "sum"),
        centroid_lat  =("y", "mean"),
        centroid_lon  =("x", "mean"),
    )
)

# Carriers present in each cluster
gen["cluster"] = busmap.reindex(gen["bus"]).values
carriers_by_cluster = (
    gen[gen["p_nom"] > 0]
    .groupby("cluster")["carrier"]
    .apply(lambda s: ", ".join(sorted(s.unique())))
)
cluster_summary["carriers"] = carriers_by_cluster

# Post-clustering p_nom_opt (optimised capacity)
if not n_post.generators.empty and "p_nom_opt" in n_post.generators.columns:
    post_opt = n_post.generators.groupby("bus")["p_nom_opt"].sum().rename("p_nom_opt_MW")
    cluster_summary["p_nom_opt_MW"] = post_opt.reindex(cluster_summary.index, fill_value=0.0)

print(f"\n{'Cluster':<25} {'#Buses':>7} {'Load(MW)':>10} "
      f"{'PreGen(MW)':>11} {'OptGen(MW)':>11} {'Lat':>7} {'Lon':>7}  Carriers")
print("-" * 110)
for cl, row in cluster_summary.iterrows():
    opt = f"{row.get('p_nom_opt_MW', 0.0):>11.1f}" if "p_nom_opt_MW" in row else "        N/A"
    print(f"  {str(cl):<23} {row['n_buses']:>7} {row['total_load_MW']:>10.2f} "
          f"{row['total_gen_MW']:>11.2f} {opt} "
          f"{row['centroid_lat']:>7.3f} {row['centroid_lon']:>7.3f}  {row.get('carriers','')}")

cluster_path = f"{OUT_DIR}/cluster_summary.csv"
cluster_summary.to_csv(cluster_path)
print(f"\n  ✓ Cluster summary saved to: {cluster_path}")

# ══════════════════════════════════════════════════════════════════════════════
# 5. CARRIER BREAKDOWN PER CLUSTER
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("4. CARRIER BREAKDOWN PER CLUSTER  (p_nom in MW)")
print("=" * 70)

carrier_pivot = (
    gen[gen["p_nom"] > 0]
    .groupby(["cluster", "carrier"])["p_nom"]
    .sum()
    .unstack(fill_value=0.0)
)
print("\n" + carrier_pivot.round(2).to_string())

carrier_path = f"{OUT_DIR}/carrier_by_cluster.csv"
carrier_pivot.to_csv(carrier_path)
print(f"\n  ✓ Carrier pivot saved to: {carrier_path}")

# ══════════════════════════════════════════════════════════════════════════════
# 6. SPATIAL COVERAGE CHECK  –  bounding boxes per cluster
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("5. SPATIAL COVERAGE PER CLUSTER  (lat/lon range of member buses)")
print("=" * 70)

spatial = (
    buses.groupby("cluster")
    .agg(lat_min=("y","min"), lat_max=("y","max"),
         lon_min=("x","min"), lon_max=("x","max"))
)
spatial["lat_span"] = (spatial["lat_max"] - spatial["lat_min"]).round(3)
spatial["lon_span"] = (spatial["lon_max"] - spatial["lon_min"]).round(3)
print("\n" + spatial.round(3).to_string())

# Flag if any cluster has no coverage above lat 1° (northern Kenya starts ~1°N)
north_buses = buses[buses["y"] > 1.0]
if north_buses.empty:
    print("\n  ⚠  WARNING: No original buses found above latitude 1.0°N")
    print("     Northern Kenya is likely not represented in the pre-clustering network.")
    print("     → Check your OSM network data and p_threshold_merge_isolated setting.")
else:
    north_clusters = north_buses["cluster"].unique()
    print(f"\n  Buses above lat 1°N belong to clusters: {list(north_clusters)}")

# ══════════════════════════════════════════════════════════════════════════════
# 7. VISUALISATIONS
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("6. GENERATING PLOTS")
print("=" * 70)

COLORS = plt.cm.tab20.colors

cluster_ids  = sorted(busmap.unique())
color_map    = {c: COLORS[i % len(COLORS)] for i, c in enumerate(cluster_ids)}

# ── Plot A: Original buses coloured by cluster ──────────────────────────────
fig, ax = plt.subplots(figsize=(10, 11))
for cluster in cluster_ids:
    mask = buses["cluster"] == cluster
    ax.scatter(
        buses.loc[mask, "x"], buses.loc[mask, "y"],
        s=buses.loc[mask, "avg_load_MW"].clip(lower=5) * 0.4 + 10,
        color=color_map[cluster], alpha=0.8, label=str(cluster), zorder=3,
    )
    # Mark cluster centroid with a star
    cx = buses.loc[mask, "x"].mean()
    cy = buses.loc[mask, "y"].mean()
    ax.scatter(cx, cy, marker="*", s=200, color=color_map[cluster],
               edgecolors="black", linewidths=0.5, zorder=5)

ax.set_title(
    f"Original buses coloured by cluster assignment\n"
    f"(circle size ∝ avg load; ★ = cluster centroid)",
    fontsize=11
)
ax.set_xlabel("Longitude"); ax.set_ylabel("Latitude")
ax.legend(title="Cluster", bbox_to_anchor=(1.01, 1), loc="upper left",
          fontsize=7, ncol=1)
ax.grid(True, alpha=0.3)
plt.tight_layout()
plot_a = f"{OUT_DIR}/buses_by_cluster.png"
fig.savefig(plot_a, dpi=150, bbox_inches="tight")
plt.close()
print(f"  ✓ Saved: {plot_a}")

# ── Plot B: Load and generation per cluster (bar chart) ─────────────────────
fig, axes = plt.subplots(1, 2, figsize=(14, 6))
cl_labels = [str(c) for c in cluster_summary.index]
x = np.arange(len(cl_labels))
w = 0.35

axes[0].bar(x, cluster_summary["total_load_MW"], width=w*2,
            color="steelblue", alpha=0.8)
axes[0].set_xticks(x); axes[0].set_xticklabels(cl_labels, rotation=45, ha="right", fontsize=7)
axes[0].set_title("Average Load per Cluster (MW)"); axes[0].set_ylabel("MW"); axes[0].grid(axis="y", alpha=0.3)

axes[1].bar(x - w/2, cluster_summary["total_gen_MW"], width=w,
            color="darkorange", alpha=0.8, label="Pre-opt p_nom")
if "p_nom_opt_MW" in cluster_summary.columns:
    axes[1].bar(x + w/2, cluster_summary["p_nom_opt_MW"], width=w,
                color="forestgreen", alpha=0.8, label="Optimised p_nom_opt")
    axes[1].legend()
axes[1].set_xticks(x); axes[1].set_xticklabels(cl_labels, rotation=45, ha="right", fontsize=7)
axes[1].set_title("Generation Capacity per Cluster (MW)"); axes[1].set_ylabel("MW"); axes[1].grid(axis="y", alpha=0.3)

plt.suptitle("Load and Generation by Cluster", fontsize=13, y=1.01)
plt.tight_layout()
plot_b = f"{OUT_DIR}/load_gen_by_cluster.png"
fig.savefig(plot_b, dpi=150, bbox_inches="tight")
plt.close()
print(f"  ✓ Saved: {plot_b}")

# ── Plot C: Carrier stacked bar per cluster ──────────────────────────────────
if not carrier_pivot.empty:
    fig, ax = plt.subplots(figsize=(14, 6))
    carrier_pivot.plot(kind="bar", stacked=True, ax=ax, colormap="tab20", width=0.7)
    ax.set_title("Installed Capacity by Carrier per Cluster (pre-opt, MW)")
    ax.set_ylabel("MW"); ax.set_xlabel("Cluster")
    ax.tick_params(axis="x", rotation=45, labelsize=7)
    ax.legend(title="Carrier", bbox_to_anchor=(1.01, 1), loc="upper left", fontsize=8)
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plot_c = f"{OUT_DIR}/carrier_by_cluster_stacked.png"
    fig.savefig(plot_c, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  ✓ Saved: {plot_c}")

# ══════════════════════════════════════════════════════════════════════════════
# DONE
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("ANALYSIS COMPLETE")
print("=" * 70)
print(f"\nAll outputs written to: {OUT_DIR}/")
print(f"  all_nodes_with_clusters.csv   – every original bus with cluster + lat/lon + load + gen")
print(f"  cluster_summary.csv           – aggregated stats per cluster")
print(f"  carrier_by_cluster.csv        – p_nom by carrier × cluster pivot table")
print(f"  buses_by_cluster.png          – map: original buses coloured by cluster")
print(f"  load_gen_by_cluster.png       – bar: load and generation per cluster")
print(f"  carrier_by_cluster_stacked.png – stacked bar: capacity mix per cluster")
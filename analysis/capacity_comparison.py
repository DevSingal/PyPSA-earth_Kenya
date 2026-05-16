"""
Existing vs New Renewable Capacity Comparison
==============================================
Loads the SOLVED network and breaks down each cluster's capacity into:
  - Existing  : fixed infrastructure (p_nom_extendable=False) OR IRENA floor (p_nom_min)
  - New       : capacity added by the optimiser above the floor
  - Total     : final optimised installed capacity

USAGE
-----
  1. Set SOLVED_NET path below to your results network file
  2. Run:  python renewable_capacity_comparison.py
"""

import os
import pypsa
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

# ─────────────────────────────────────────────────────────────────────
# CONFIG  –  edit this path
# ─────────────────────────────────────────────────────────────────────
SOLVED_NET = "../results/2030_scenenario/networks/elec_s_10_ec_lcopt_Co2L-3H.nc"
OUT_DIR    = "analysis/outputs/capacity_comparison"
# ─────────────────────────────────────────────────────────────────────

os.makedirs(OUT_DIR, exist_ok=True)

RENEWABLE_CARRIERS = ["solar", "onwind", "offwind-ac", "offwind-dc",
                      "ror", "geothermal", "hydro"]
ALL_CARRIERS       = RENEWABLE_CARRIERS + ["oil", "CCGT", "OCGT", "coal", "nuclear"]

# colour palette (carrier → hex)
CARRIER_COLORS = {
    "solar"      : "#f9d71c",
    "onwind"     : "#235ebc",
    "offwind-ac" : "#6895dd",
    "offwind-dc" : "#74c6f2",
    "ror"        : "#298c81",
    "geothermal" : "#ba2626",
    "hydro"      : "#3dbfb0",
    "oil"        : "#808080",
    "CCGT"       : "#b35c00",
    "OCGT"       : "#e66c00",
    "coal"       : "#333333",
    "nuclear"    : "#ff8c00",
}

# ═════════════════════════════════════════════════════════════════════
# 1. LOAD NETWORK & SANITY CHECK
# ═════════════════════════════════════════════════════════════════════
print("=" * 70)
print("EXISTING vs NEW RENEWABLE CAPACITY — POST-SOLVE ANALYSIS")
print("=" * 70)

if not os.path.exists(SOLVED_NET):
    raise FileNotFoundError(
        f"\nFile not found: {SOLVED_NET}\n"
        "Make sure SOLVED_NET points to the file under results/networks/, "
        "NOT the pre-solve file under networks/."
    )

print(f"\nLoading solved network: {SOLVED_NET}")
n = pypsa.Network(SOLVED_NET)

# Confirm this is actually a solved network
obj = getattr(n, "objective", None)
if obj is None or (isinstance(obj, float) and np.isnan(obj)):
    print("\n⚠  WARNING: n.objective is NaN — this may be the pre-solve network.")
    print("   p_nom_opt values will be unreliable. Check your file path.\n")
else:
    print(f"   Objective value: {obj:,.0f}  ✓ (network is solved)")

# ═════════════════════════════════════════════════════════════════════
# 2. BUILD CAPACITY TABLE
# ═════════════════════════════════════════════════════════════════════
gen = n.generators[["bus", "carrier", "p_nom", "p_nom_opt",
                     "p_nom_min", "p_nom_extendable"]].copy()

def classify(row):
    if not row["p_nom_extendable"]:
        # Fixed plant — all existing, optimiser cannot change it
        return row["p_nom"], 0.0, row["p_nom"]
    else:
        existing = row["p_nom_min"]                          # IRENA floor (may be 0)
        new      = max(0.0, row["p_nom_opt"] - row["p_nom_min"])
        total    = row["p_nom_opt"]
        return existing, new, total

gen[["existing_MW", "new_MW", "total_MW"]] = gen.apply(
    classify, axis=1, result_type="expand"
)

# ═════════════════════════════════════════════════════════════════════
# 3. CONSOLE REPORT
# ═════════════════════════════════════════════════════════════════════

def pivot_table(value_col, carriers=None):
    df = gen.copy()
    if carriers:
        df = df[df["carrier"].isin(carriers)]
    return (
        df.pivot_table(values=value_col, index="bus",
                       columns="carrier", aggfunc="sum", fill_value=0.0)
          .round(1)
    )

# ── 3a. Renewables only ───────────────────────────────────────────────
ren_existing = pivot_table("existing_MW", RENEWABLE_CARRIERS)
ren_new      = pivot_table("new_MW",      RENEWABLE_CARRIERS)
ren_total    = pivot_table("total_MW",    RENEWABLE_CARRIERS)

print("\n" + "=" * 70)
print("RENEWABLE CARRIERS ONLY")
print("=" * 70)

print("\n── EXISTING capacity (MW) ──────────────────────────────────────────")
print(ren_existing.to_string())

print("\n── NEW capacity added by optimiser (MW) ────────────────────────────")
print(ren_new.to_string())

print("\n── TOTAL optimised capacity (MW) ───────────────────────────────────")
print(ren_total.to_string())

# ── 3b. All carriers ─────────────────────────────────────────────────
all_existing = pivot_table("existing_MW")
all_new      = pivot_table("new_MW")
all_total    = pivot_table("total_MW")

print("\n" + "=" * 70)
print("ALL CARRIERS (including fossil)")
print("=" * 70)

print("\n── EXISTING capacity (MW) ──────────────────────────────────────────")
print(all_existing.to_string())

print("\n── NEW capacity added by optimiser (MW) ────────────────────────────")
print(all_new.to_string())

print("\n── TOTAL optimised capacity (MW) ───────────────────────────────────")
print(all_total.to_string())

# ── 3c. System-wide summary ───────────────────────────────────────────
print("\n" + "=" * 70)
print("SYSTEM-WIDE SUMMARY")
print("=" * 70)

summary_carriers = [c for c in gen["carrier"].unique()
                    if gen.loc[gen["carrier"] == c, "total_MW"].sum() > 0]

print(f"\n{'Carrier':<18} {'Existing (MW)':>15} {'New (MW)':>13} "
      f"{'Total (MW)':>12} {'% New':>8}")
print("-" * 70)
for c in sorted(summary_carriers):
    row = gen[gen["carrier"] == c]
    ex  = row["existing_MW"].sum()
    nw  = row["new_MW"].sum()
    tot = row["total_MW"].sum()
    pct = (nw / tot * 100) if tot > 0 else 0
    flag = " ★" if c in RENEWABLE_CARRIERS else ""
    print(f"  {c+flag:<16} {ex:>15.1f} {nw:>13.1f} {tot:>12.1f} {pct:>7.1f}%")

print("-" * 70)
total_ex  = gen["existing_MW"].sum()
total_new = gen["new_MW"].sum()
total_tot = gen["total_MW"].sum()
print(f"  {'TOTAL':<16} {total_ex:>15.1f} {total_new:>13.1f} "
      f"{total_tot:>12.1f} {total_new/total_tot*100 if total_tot else 0:>7.1f}%")
print("  ★ = renewable")

ren_ex  = gen.loc[gen["carrier"].isin(RENEWABLE_CARRIERS), "existing_MW"].sum()
ren_nw  = gen.loc[gen["carrier"].isin(RENEWABLE_CARRIERS), "new_MW"].sum()
ren_tot = gen.loc[gen["carrier"].isin(RENEWABLE_CARRIERS), "total_MW"].sum()
print(f"\n  Renewable share of total optimised capacity: "
      f"{ren_tot/total_tot*100 if total_tot else 0:.1f}%")
print(f"  New capacity as share of total renewable:    "
      f"{ren_nw/ren_tot*100 if ren_tot else 0:.1f}%")

# Check if optimiser actually built anything
if total_new < 1.0:
    print("\n  ⚠  WARNING: Total new capacity < 1 MW.")
    print("     Either the solver built nothing new, or you loaded the pre-solve file.")
    print("     Verify n.objective is not NaN (see top of output).")

# ═════════════════════════════════════════════════════════════════════
# 5. PLOTS
# ═════════════════════════════════════════════════════════════════════
clusters = sorted(gen["bus"].unique())

def get_color(carrier):
    return CARRIER_COLORS.get(carrier, "#aaaaaa")

# ── Plot A: Stacked bar — existing vs new per cluster (renewables) ────
fig, axes = plt.subplots(1, 2, figsize=(16, 7), sharey=False)

for ax, (df, label) in zip(axes, [(ren_existing, "Existing"), (ren_new, "New (Optimiser)")]):
    carriers_present = [c for c in df.columns if df[c].sum() > 0]
    bottoms = np.zeros(len(df))
    for carrier in carriers_present:
        vals = df[carrier].values
        ax.bar(df.index, vals, bottom=bottoms,
               color=get_color(carrier), label=carrier,
               edgecolor="white", linewidth=0.5)
        # label bars > 10 MW
        for i, (v, b) in enumerate(zip(vals, bottoms)):
            if v > 10:
                ax.text(i, b + v / 2, f"{v:.0f}", ha="center",
                        va="center", fontsize=7, color="white", fontweight="bold")
        bottoms += vals
    ax.set_title(f"{label} Renewable Capacity by Cluster", fontsize=12)
    ax.set_ylabel("Capacity (MW)")
    ax.set_xlabel("Cluster")
    ax.tick_params(axis="x", rotation=45, labelsize=8)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    ax.grid(axis="y", alpha=0.3)
    ax.legend(title="Carrier", bbox_to_anchor=(1.01, 1), loc="upper left",
              fontsize=8, framealpha=0.8)

plt.suptitle("Renewable Capacity: Existing vs New by Cluster", fontsize=14, y=1.02)
plt.tight_layout()
path_a = f"{OUT_DIR}/plot_existing_vs_new_by_cluster.png"
fig.savefig(path_a, dpi=150, bbox_inches="tight")
plt.close()
print(f"✓ Saved: {path_a}")

# ── Plot B: Grouped bar — existing / new / total per carrier ──────────
carriers_plot = [c for c in summary_carriers if
                 gen.loc[gen["carrier"] == c, "total_MW"].sum() > 0]
x   = np.arange(len(carriers_plot))
w   = 0.26

fig, ax = plt.subplots(figsize=(14, 6))
ex_vals  = [gen.loc[gen["carrier"] == c, "existing_MW"].sum() for c in carriers_plot]
new_vals = [gen.loc[gen["carrier"] == c, "new_MW"].sum()      for c in carriers_plot]
tot_vals = [gen.loc[gen["carrier"] == c, "total_MW"].sum()    for c in carriers_plot]

ax.bar(x - w, ex_vals,  width=w, label="Existing", color="steelblue",   alpha=0.85)
ax.bar(x,     new_vals, width=w, label="New",      color="forestgreen",  alpha=0.85)
ax.bar(x + w, tot_vals, width=w, label="Total",    color="darkorange",   alpha=0.85)

for xi, (e, nw, t) in enumerate(zip(ex_vals, new_vals, tot_vals)):
    for offset, val in [(-w, e), (0, nw), (w, t)]:
        if val > 5:
            ax.text(xi + offset, val + 5, f"{val:.0f}", ha="center",
                    va="bottom", fontsize=7, rotation=90)

ren_patch = [c for c in carriers_plot if c in RENEWABLE_CARRIERS]
ax.set_xticks(x)
ax.set_xticklabels(
    [f"{c}\n★" if c in RENEWABLE_CARRIERS else c for c in carriers_plot],
    rotation=30, ha="right", fontsize=9
)
ax.set_ylabel("Capacity (MW)")
ax.set_title("Existing vs New vs Total Optimised Capacity by Carrier  (★ = renewable)",
             fontsize=12)
ax.legend(fontsize=10)
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
ax.grid(axis="y", alpha=0.3)
plt.tight_layout()
path_b = f"{OUT_DIR}/plot_existing_vs_new_by_carrier.png"
fig.savefig(path_b, dpi=150, bbox_inches="tight")
plt.close()
print(f"✓ Saved: {path_b}")

# ── Plot C: Heatmap — total optimised MW, cluster × carrier ───────────
heat_data = all_total.copy()
heat_data = heat_data[[c for c in heat_data.columns if heat_data[c].sum() > 0]]

fig, ax = plt.subplots(figsize=(max(10, len(heat_data.columns) * 1.2),
                                max(5,  len(heat_data) * 0.6)))
im = ax.imshow(heat_data.values, aspect="auto", cmap="YlOrRd")

ax.set_xticks(range(len(heat_data.columns)))
ax.set_xticklabels(heat_data.columns, rotation=45, ha="right", fontsize=9)
ax.set_yticks(range(len(heat_data.index)))
ax.set_yticklabels(heat_data.index, fontsize=9)

for i in range(len(heat_data.index)):
    for j in range(len(heat_data.columns)):
        val = heat_data.values[i, j]
        if val > 0:
            ax.text(j, i, f"{val:.0f}", ha="center", va="center",
                    fontsize=8,
                    color="white" if val > heat_data.values.max() * 0.6 else "black")

plt.colorbar(im, ax=ax, label="Optimised Capacity (MW)")
ax.set_title("Total Optimised Capacity Heatmap  (MW, cluster × carrier)", fontsize=12)
plt.tight_layout()
path_c = f"{OUT_DIR}/plot_heatmap_cluster_carrier.png"
fig.savefig(path_c, dpi=150, bbox_inches="tight")
plt.close()
print(f"✓ Saved: {path_c}")

# ── Plot D: Pie — system-wide existing vs new split ───────────────────
fig, axes = plt.subplots(1, 2, figsize=(13, 6))

# Left pie: existing capacity mix by carrier
ex_by_carrier = {c: gen.loc[gen["carrier"] == c, "existing_MW"].sum()
                 for c in summary_carriers}
ex_by_carrier = {k: v for k, v in ex_by_carrier.items() if v > 0}
axes[0].pie(
    ex_by_carrier.values(),
    labels=ex_by_carrier.keys(),
    colors=[get_color(c) for c in ex_by_carrier],
    autopct=lambda p: f"{p:.1f}%" if p > 2 else "",
    startangle=140, pctdistance=0.75,
)
axes[0].set_title("Existing Capacity Mix\n(system-wide)", fontsize=11)

# Right pie: new capacity mix by carrier
nw_by_carrier = {c: gen.loc[gen["carrier"] == c, "new_MW"].sum()
                 for c in summary_carriers}
nw_by_carrier = {k: v for k, v in nw_by_carrier.items() if v > 0}
if nw_by_carrier:
    axes[1].pie(
        nw_by_carrier.values(),
        labels=nw_by_carrier.keys(),
        colors=[get_color(c) for c in nw_by_carrier],
        autopct=lambda p: f"{p:.1f}%" if p > 2 else "",
        startangle=140, pctdistance=0.75,
    )
    axes[1].set_title("New Capacity Mix (added by optimiser)\n(system-wide)", fontsize=11)
else:
    axes[1].text(0.5, 0.5, "No new capacity built\n(check file path — may be pre-solve)",
                 ha="center", va="center", transform=axes[1].transAxes,
                 fontsize=11, color="red")
    axes[1].set_title("New Capacity Mix", fontsize=11)

plt.suptitle("System-Wide Capacity Mix: Existing vs New", fontsize=13, y=1.02)
plt.tight_layout()
path_d = f"{OUT_DIR}/plot_pie_existing_vs_new.png"
fig.savefig(path_d, dpi=150, bbox_inches="tight")
plt.close()
print(f"✓ Saved: {path_d}")

# ═════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("DONE — all outputs in:", OUT_DIR)
print("=" * 70)
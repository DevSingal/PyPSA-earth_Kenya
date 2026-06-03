#!/usr/bin/env python3
"""
fix_simplify_network.py
-----------------------
Fixes the KeyError: 'p' crash in simplify_network.py caused by a
PyPSA >= 0.26 API change.

HOW TO USE:
  1. Copy this file into your pypsa-earth root directory
  2. Run:  python fix_simplify_network.py
  3. Then: snakemake --rerun-incomplete -j4
"""

import sys, shutil, argparse
from pathlib import Path


def apply_fix(filepath):
    path = Path(filepath)
    if not path.exists():
        print(f"ERROR: File not found: {path}")
        print("Run from your pypsa-earth root, or pass --path scripts/simplify_network.py")
        sys.exit(1)

    original = path.read_text(encoding="utf-8")
    patched  = original
    fixes    = 0
    comment  = "  # PATCHED: StorageUnit removed — PyPSA>=0.26 renamed 'p' to 'p_dispatch'"

    # Fix 1: set-literal default argument
    old1 = 'aggregate_one_ports={"Load", "StorageUnit"}'
    new1 = 'aggregate_one_ports={"Load"}' + comment
    if old1 in patched:
        patched = patched.replace(old1, new1)
        fixes += 1
        print("  [OK] Fix 1 — default arg in _aggregate_and_move_components()")
    else:
        print("  [--] Fix 1 — not found (may already be patched)")

    # Fix 2+3: list-literal in aggregate_to_substations + merge_isolated_networks
    old2 = 'aggregate_one_ports=["Load", "StorageUnit"]'
    new2 = 'aggregate_one_ports=["Load"]' + comment
    count2 = patched.count(old2)
    if count2 > 0:
        patched = patched.replace(old2, new2)
        fixes += count2
        print(f"  [OK] Fix 2+3 — {count2} list-literal occurrence(s) patched")
    else:
        print("  [--] Fix 2+3 — not found (may already be patched)")

    if fixes == 0:
        print("\nNo changes applied — already patched or unexpected version.")
        print("Manually check: grep -n 'StorageUnit' scripts/simplify_network.py")
        return

    # Backup original
    backup = path.with_suffix(".py.bak")
    shutil.copy2(path, backup)
    print(f"\n  Backup saved  : {backup}")
    path.write_text(patched, encoding="utf-8")
    print(f"  Patched file  : {path}")

    # Verify: any ACTIVE (non-comment) line still has the old pattern?
    bad = [
        (i+1, line.rstrip())
        for i, line in enumerate(patched.splitlines())
        if (('aggregate_one_ports={"Load", "StorageUnit"}' in line or
             'aggregate_one_ports=["Load", "StorageUnit"]' in line)
            and not line.lstrip().startswith("#"))
    ]
    if bad:
        print(f"\n  WARNING — {len(bad)} line(s) still need manual fixing:")
        for lineno, text in bad:
            print(f"    line {lineno}: {text.strip()}")
    else:
        print("\n  Verification PASSED — all active occurrences removed.")

    print(f"\nDone. {fixes} fix(es) applied.")
    print("Run:  snakemake --rerun-incomplete -j4")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--path",
        default="scripts/simplify_network.py",
        help="Path to simplify_network.py (default: scripts/simplify_network.py)"
    )
    args = parser.parse_args()
    print(f"\nTarget file: {Path(args.path).resolve()}\n")
    apply_fix(args.path)

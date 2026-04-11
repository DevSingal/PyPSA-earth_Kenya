import subprocess
import re

# --- CONFIGURATION ---
# Change this to whatever rule you want to graph (e.g., "networks/elec.nc" or "solve_all_networks")
TARGET_RULE = "solve_all_networks" 
OUTPUT_IMAGE = "dag_clean.png"
# ---------------------

def generate_clean_dag():
    print(f"Generating DAG for '{TARGET_RULE}'...")
    
    # Run Snakemake and capture the output (including the Gurobi garbage)
    result = subprocess.run(
        ["snakemake", "--dag", TARGET_RULE], 
        capture_output=True, 
        text=True, 
        encoding='utf-8'
    )

    # Split the output into lines
    lines = result.stdout.splitlines()
    
    # Find where the actual Graphviz code starts (look for "digraph")
    start_index = -1
    for i, line in enumerate(lines):
        if line.strip().startswith("digraph"):
            start_index = i
            break
            
    if start_index == -1:
        print("Error: Could not find DAG data in Snakemake output.")
        print("Raw output start:", lines[:5]) # Debugging aid
        return

    # Keep only the clean graph code
    clean_dot_code = "\n".join(lines[start_index:])
    
    # Save to a temporary file
    with open("temp_dag.dot", "w") as f:
        f.write(clean_dot_code)
        
    print("Garbage removed. Generating image...")

    # Run Graphviz (dot) on the clean file
    subprocess.run(["dot", "-Tpng", "temp_dag.dot", "-o", OUTPUT_IMAGE])
    
    print(f"Success! Graph saved to {OUTPUT_IMAGE}")

if __name__ == "__main__":
    generate_clean_dag()
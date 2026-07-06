#!/bin/bash

echo "Checking and downloading databundle..."
mkdir -p data/hydrobasins
cd data/hydrobasins

# wget with aggressive auto-resume and infinite retries
wget -c --retry-connrefused --tries=0 --timeout=15 https://zenodo.org/records/10850029/files/data.tar.gz

# Extract the downloaded file
tar -xzf data.tar.gz
cd ../../

echo "Download complete. Starting Snakemake..."
# Ensure retrieve_databundle is set to 'false' in config.yaml before this runs
snakemake -j 1
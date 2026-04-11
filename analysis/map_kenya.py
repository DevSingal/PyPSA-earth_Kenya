import pypsa
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
from cartopy.io.img_tiles import OSM

# 1. Load the network
network_path = "../results/networks/elec_s_2_ec_lcopt_Co2L.nc"
n = pypsa.Network(network_path)

# 2. Set up the OpenStreetMap tile provider
osm_tiles = OSM()

# 3. Set up the map projection
# Crucial change: The map MUST use the OSM coordinate reference system (Web Mercator)
fig, ax = plt.subplots(figsize=(12, 12), subplot_kw={"projection": osm_tiles.crs})

# 4. Force the camera to show all of Kenya
# We still feed it standard GPS coordinates, but tell it to convert them (PlateCarree)
ax.set_extent([32.5, 42.5, -5.0, 5.5], crs=ccrs.PlateCarree())

# 5. Add the OSM basemap
# The number '7' is the zoom level. 7 is perfect for a whole country. 
# (Don't set this higher than 8 or it will try to download street-level data for all of Kenya and freeze!)
ax.add_image(osm_tiles, 7)

# =========================================================
# 6. Extract and Plot Transmission Lines
# =========================================================
for line in n.lines.index:
    bus0, bus1 = n.lines.loc[line, ["bus0", "bus1"]]
    if bus0 in n.buses.index and bus1 in n.buses.index:
        x0, y0 = n.buses.loc[bus0, ["x", "y"]]
        x1, y1 = n.buses.loc[bus1, ["x", "y"]]
        
        # Draw a thick dark green line
        # transform=ccrs.PlateCarree() translates our GPS coordinates to the OSM map projection
        ax.plot([x0, x1], [y0, y1], color='darkgreen', linewidth=5, transform=ccrs.PlateCarree(), zorder=4)

# =========================================================
# 7. Extract coordinates and manually plot the nodes
# =========================================================
for bus in n.buses.index:
    # Filter out the internal storage buses
    if "H2" not in str(bus) and "battery" not in str(bus):
        x = n.buses.loc[bus, "x"]
        y = n.buses.loc[bus, "y"]
        
        # Draw the red node dot with a black edge for contrast
        ax.scatter(x, y, color='red', s=250, zorder=5, transform=ccrs.PlateCarree(), edgecolors='black')
        
        # Add the label box
        ax.text(x + 0.15, y + 0.15, str(bus), fontsize=14, fontweight='bold', 
                bbox=dict(facecolor='white', alpha=0.9, edgecolor='black'),
                transform=ccrs.PlateCarree(), zorder=6)

plt.title("OpenStreetMap View of Kenya's 2 Grid Clusters & Transmission", fontsize=16, fontweight='bold')
plt.show()
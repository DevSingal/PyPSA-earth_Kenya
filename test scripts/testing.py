import pypsa, networkx as nx

n = pypsa.Network("networks/2030_scenenario/base.nc")
G = n.graph()
n_components = nx.number_connected_components(G.to_undirected())
print(f"Connected components: {n_components}")  # must be 1

if n_components > 1:
    for i, comp in enumerate(nx.connected_components(G.to_undirected())):
        print(f"Component {i}: {len(comp)} buses — {list(comp)[:5]}")
import pypsa

n = pypsa.Network('networks/2030_scenenario/base.nc')

print(n.buses[['x','y','v_nom']].sort_values('y'))

print('Northernmost bus:', n.buses['y'].max(), 'degrees lat')
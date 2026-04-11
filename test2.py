import pandas as pd

costs = pd.read_csv(
    "resources/2030_scenenario/costs_2030.csv",
    index_col=[0,1]
)

# Check specific technologies
techs = ["solar", "onwind", "CCGT", "battery storage", "electrolysis"]
for tech in techs:
    if tech in costs.index.get_level_values(0):
        row = costs.loc[tech]
        print(f"{tech}")
        print(row[["value","unit","source"]].to_string())
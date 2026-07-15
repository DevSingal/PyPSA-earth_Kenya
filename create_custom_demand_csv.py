import pandas as pd

# 1. Load the existing PyPSA-Earth demand profiles
# Make sure the path matches your resources folder path
existing_profiles_path = "resources/2020_baseline/demand_profiles.csv" 
df_existing = pd.read_csv(existing_profiles_path, index_col="time", parse_dates=True)

# 2. Calculate the hourly total of the existing synthetic load
total_existing_hourly = df_existing.sum(axis=1)

# 3. Calculate the weight/proportion of each bus for every hour
# This divides each bus's load by the total load for that specific row (hour)
df_proportions = df_existing.div(total_existing_hourly, axis=0)

# 4. Load your ACTUAL total hourly load data
# Assuming your custom CSV has a 'time' column and a 'total_load' column
actual_load_path = "data/demand_profile_data_2020.csv"
# Try latin1 first, as it covers most western European/Windows Excel characters
df_actual = pd.read_csv(
    actual_load_path, 
    index_col="time", 
    parse_dates=["time"], 
    date_format="%d-%m-%Y %H:%M"
)
# Ensure the time indices align perfectly (critical for PyPSA!)
# If your actual data is for a different year, you may need to map the dates to match PyPSA's config year.
df_actual = df_actual.reindex(df_existing.index) 
print("Pandas sees these columns:", df_actual.columns.tolist())
# 5. Multiply the proportions by your actual hourly load
df_custom_bus_load = df_proportions.multiply(df_actual['total_load'], axis=0)

# 6. Save the new custom demand profiles
df_custom_bus_load.to_csv("custom_demand_profiles.csv")
print("Custom demand profiles successfully generated!")
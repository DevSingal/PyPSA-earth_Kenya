import pandas as pd
import logging

logger = logging.getLogger(__name__)

def extra_functionality(n, snapshots, snakemake):
    """
    This function is automatically called by PyPSA right before the solver.
    'n' is the PyPSA network object containing the 59 buses.
    """
    logger.info("Intercepting pipeline: Injecting actual total load data...")

    # 1. Access the default synthetic demand already built by PyPSA
    synthetic_demand = n.loads_t.p_set

    # 2. Calculate the hourly total and the bus proportions dynamically
    total_synthetic_hourly = synthetic_demand.sum(axis=1)
    proportions = synthetic_demand.div(total_synthetic_hourly, axis=0)

    # 3. Load your actual custom total load (using our date fix!)
    # Update this path if your file lives somewhere else in the directory
    actual_load_path = "data/demand_profile_data_2020.csv" 
    
    df_actual = pd.read_csv(
        actual_load_path, 
        index_col="time", 
        parse_dates=True, 
        dayfirst=True 
    )

    # 4. Multiply proportions by the actual load 
    # Using .values strips the index to guarantee it aligns with the network's snapshots
    custom_bus_load = proportions.multiply(df_actual.iloc[:, 0].values, axis=0)

    # 5. Overwrite the PyPSA network demand in memory
    n.loads_t.p_set = custom_bus_load

    logger.info("Custom demand successfully scaled and applied to all buses!")
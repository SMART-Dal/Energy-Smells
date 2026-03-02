import pandas as pd
import json
import numpy as np
import random

random.seed(42)
np.random.seed(42)



TOP_K = 3000
SAMPLING_COUNT = 1000


with open("energy_results.jsonl", "r") as f:
    lines = f.readlines()

existing_lines = []
for i, line in enumerate(lines):
    obj = json.loads(line)
    obj.update({"unique_index": i})
    if "result_energy_v0" in obj and "result_energy_v1" in obj:
        existing_lines.append(obj)

df = pd.DataFrame(existing_lines)

sorted_energy_diff = (df["result_energy_v1"] - df["result_energy_v0"]).abs().sort_values(ascending=False)


remaining_indexes = sorted_energy_diff[:TOP_K].index

# sample with sampling count out of TOP_K
# remaining_indexes = np.random.choice(remaining_indexes, SAMPLING_COUNT, replace=False)

# keep the rows in main df that are in the remaining indexes
remaining_df = df.loc[remaining_indexes]

# write the remaining df to a new jsonl file
jsonl_signifcant_energy_file = "significant_energy_diff.jsonl"
with open(jsonl_signifcant_energy_file, "w") as f: 
    for _, row in remaining_df.iterrows():
        f.write(json.dumps(row.to_dict()) + "\n")



    


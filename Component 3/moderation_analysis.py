import pandas as pd
from moderation import get_moderation_decision

DATA_PATH = "predictions.csv"
OUTPUT_PATH = "moderation_stats.csv"

"""
Expected predictions.csv columns:
text,prediction,HATE,DISINFO,NORMAL
"""

df = pd.read_csv(DATA_PATH)

def row_to_probs(row):
    return {
        "HATE": float(row.get("HATE", 0)),
        "DISINFO": float(row.get("DISINFO", 0)),
        "NORMAL": float(row.get("NORMAL", 0)),
    }

df["moderation_action"] = df.apply(
    lambda row: get_moderation_decision(row["prediction"], row_to_probs(row))["action"],
    axis=1
)

df["moderation_severity"] = df.apply(
    lambda row: get_moderation_decision(row["prediction"], row_to_probs(row))["severity"],
    axis=1
)

stats = df["moderation_action"].value_counts().reset_index()
stats.columns = ["action", "count"]
stats.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

print(stats)
print(f"Saved: {OUTPUT_PATH}")
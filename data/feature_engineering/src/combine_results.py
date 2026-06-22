import pandas as pd

aave = pd.read_csv("data/aave/daily_features.csv")
morpho = pd.read_csv("data/morpho/daily_features.csv")

combined = pd.concat([aave, morpho], ignore_index=True)

token_cols = [c for c in combined.columns if c.startswith("coll_") or c.startswith("debt_")]
combined[token_cols] = combined[token_cols].fillna(0).astype(int)

combined = combined.sort_values(["whale_id", "date"]).reset_index(drop=True)
combined.to_csv("data/daily_features_all.csv", index=False)
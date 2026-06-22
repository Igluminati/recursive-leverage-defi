import requests
import pandas as pd

GRAPHQL_URL = "https://api.morpho.org/graphql"

MARKETS = [
    "0x88a18b2f4d94e7ad27a381b15531c06abf05a7c99dd5d3c3679875fed6f7e742",
    "0x3274643db77a064abd3bc851de77556a4ad2e2f502f4f0c80845fa8f909ecf0b",
    "0x90ef0c5a0dc7c4de4ad4585002d44e9d411d212d2f6258e94948beecf8b4c0d5",
    "0xc9629945524f3fde56c7e8854a6c3d48e76b9d97236abbe73c750fcc7aeb8501",
]

QUERY = """
query GetMarketHistory($marketId: String!, $options: TimeseriesOptions) {
  marketById(marketId: $marketId, chainId: 1) {
    historicalState {
      supplyApy(options: $options) {
        x
        y
      }
    }
  }
}
"""

NOVEMBER_2023 = 1700000000
OPTIONS = {
    "startTimestamp": NOVEMBER_2023,
    "interval": "DAY"
}

rows = []
for market_id in MARKETS:
    response = requests.post(
        GRAPHQL_URL,
        json={"query": QUERY, "variables": {"marketId": market_id, "options": OPTIONS}},
    )
    print(f"market {market_id[:10]}... status: {response.status_code}")
    data = response.json()

    if "errors" in data:
        print(data["errors"])
        continue

    for point in data["data"]["marketById"]["historicalState"]["supplyApy"]:
        rows.append({
            "date": pd.to_datetime(point["x"], unit="s").date(),
            "market_id": market_id,
            "supply_apy_pct": round(point["y"] * 100, 4),
        })

df = pd.DataFrame(rows)
df = df.sort_values(["market_id", "date"]).drop_duplicates(subset=["market_id", "date"], keep="last")
df.to_csv("data/morpho/morpho_supply_rates.csv", index=False)
print(df.tail(20))
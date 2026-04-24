import os
import json
import requests
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from dune_client.client import DuneClient
from dune_client.query import QueryBase

load_dotenv()

with open("ybt_metadata.json") as f:
    TOKENS = json.load(f)

DEFILLAMA_YIELDS_API = "https://yields.llama.fi/pools"

DUNE_QUERIES = {
    "prices": 7359293,
    "aave_sUSDe_events": 7359302,
    "morpho_events": 7359324,
    "spark_sUSDS_events": 7368610,
}



def fetch_defillama_yields() -> dict:
    print("Fetching DeFiLlama yields...")
    resp = requests.get(DEFILLAMA_YIELDS_API, timeout=30)
    resp.raise_for_status()
    pools = resp.json().get("data", [])

    symbol_map = {"SUSDE": "sUSDe", "SUSDS": "sUSDS", "SYRUPUSDC": "syrupUSDC"}
    yields = {}

    for pool in pools:
        symbol = pool.get("symbol", "").upper()
        if symbol in symbol_map:
            key = symbol_map[symbol]
            tvl = pool.get("tvlUsd") or 0
            if key not in yields or tvl > (yields[key].get("tvl_usd") or 0):
                yields[key] = {
                    "tvl_usd": pool.get("tvlUsd"),
                    "apy_percent": pool.get("apy"),
                    "apy_base": pool.get("apyBase"),
                    "apy_reward": pool.get("apyReward"),
                }
    return yields


def build_metadata(yields: dict) -> dict:
    scraped_at = datetime.utcnow().isoformat() + "Z"
    metadata = {}

    for symbol, cfg in TOKENS.items():
        print(f"Processing {symbol}...")
        yl = yields.get(symbol, {})
        metadata[symbol] = {**cfg, **yl, "scraped_at": scraped_at}
    return metadata


def save_metadata(metadata: dict) -> None:
    with open("ybt_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
    print("Saved ybt_metadata.json")


def fetch_dune_data(dune: DuneClient, name: str, query_id: int) -> pd.DataFrame:
    print(f"Fetching {name} from Dune (query_id={query_id})...")
    query = QueryBase(query_id=query_id)
    result = dune.run_query(query=query)
    df = pd.DataFrame(result.result.rows)
    print(f"  → {len(df)} rows fetched")
    return df


def main():
    yields = fetch_defillama_yields()
    metadata = build_metadata(yields)
    save_metadata(metadata)

    dune = DuneClient(api_key=os.getenv("DUNE_API_KEY"), base_url="https://api.dune.com", request_timeout=300)

    prices_df = fetch_dune_data(dune, "prices", DUNE_QUERIES["prices"])
    prices_df.to_csv("ybt_prices.csv", index=False)
    print("Saved ybt_prices.csv")

    aave_df = fetch_dune_data(dune, "Aave sUSDe events", DUNE_QUERIES["aave_sUSDe_events"])
    aave_df.to_csv("aave_events.csv", index=False)
    print("Saved aave_events.csv")

    morpho_df = fetch_dune_data(dune, "Morpho events", DUNE_QUERIES["morpho_events"])
    morpho_df.to_csv("morpho_events.csv", index=False)
    print("Saved morpho_events.csv")

    spark_df = fetch_dune_data(dune, "Spark sUSDS events", DUNE_QUERIES["spark_sUSDS_events"])
    spark_df.to_csv("spark_events.csv", index=False)
    print("Saved spark_events.csv")


if __name__ == "__main__":
    main()

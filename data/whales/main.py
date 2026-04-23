import os
import pandas as pd
from dotenv import load_dotenv
from dune_client.client import DuneClient
from dune_client.query import QueryBase
from web3 import Web3

load_dotenv()

dune = DuneClient(api_key=os.getenv("DUNE_API_KEY"), base_url="https://api.dune.com", request_timeout=300)
w3 = Web3(Web3.HTTPProvider(os.getenv("RPC_URL")))



TOKENS = {
    "sUSDe": {
        "address": "0x9D39A5DE30e57443BfF2A8307A4256c8797A3497",
        "decimals": 18,
        "morpho_query_id": 7344848,
        "aave_query_id": 7349560,
    },
    # "sUSDS":     {...},
    # "syrupUSDC": {...},
}



def get_top_holders(token_name: str, query_id: int, protocol: str) -> pd.DataFrame:
    print(f"Querying {protocol} holders for {token_name} (query_id={query_id})...")
    query = QueryBase(query_id=query_id)
    result = dune.run_query(query=query)
    df = pd.DataFrame(result.result.rows)
    df["current_balance"] = df["current_balance"].astype(float).map("{:,.2f}".format)
    df["total_received"] = df["total_received"].astype(float).map("{:,.2f}".format)
    df["token"] = token_name
    df["protocol"] = protocol
    return df


def is_eoa(address: str) -> bool:
    code = w3.eth.get_code(Web3.to_checksum_address(address))
    return code == b""


def filter_eoas(df: pd.DataFrame) -> pd.DataFrame:
    print(f"Checking {len(df)} addresses...")
    df = df.copy()
    df["is_eoa"] = df["address"].apply(is_eoa)
    return df.reset_index(drop=True)


def save_whales(whales: dict) -> None:
    for token_name, df in whales.items():
        output = df[["rank", "address", "current_balance", "total_received", "is_eoa", "is_looper", "is_flashloaner", "strategy_type", "protocol"]].copy()
        output["sort_key"] = output["total_received"].str.replace(",", "").astype(float)
        output["rank"] = output.groupby("protocol")["sort_key"].rank(ascending=False, method="first").astype(int)
        output = output.sort_values(["protocol", "rank"]).reset_index(drop=True)
        output = output.drop(columns=["sort_key"])
        filename = f"{token_name}_whales.csv"
        output.to_csv(filename, index=False)
        print(f"Saved {filename}")



def main():
    print(f"Connected: {w3.is_connected()}\n")

    # fetch holders from Dune
    results = {}
    for token_name, meta in TOKENS.items():
        morpho_df = get_top_holders(token_name, meta["morpho_query_id"], "Morpho")
        aave_df = get_top_holders(token_name, meta["aave_query_id"], "Aave")
        results[token_name] = pd.concat([morpho_df, aave_df], ignore_index=True)
        print(f"  → {len(results[token_name])} total holders fetched\n")

    # flag EOAs vs contracts
    whales = {}
    for token_name, df in results.items():
        whales[token_name] = filter_eoas(df)
        print(f"{len(whales[token_name])} addresses checked")

    save_whales(whales)


if __name__ == "__main__":
    main()
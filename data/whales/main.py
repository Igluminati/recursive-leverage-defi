import os
import pandas as pd
from dotenv import load_dotenv
from dune_client.client import DuneClient
from dune_client.query import QueryBase
from web3 import Web3

load_dotenv()

dune = DuneClient(
    api_key=os.getenv("DUNE_API_KEY"),
    base_url="https://api.dune.com",
    request_timeout=300,
)
w3 = Web3(Web3.HTTPProvider(os.getenv("RPC_URL")))

TOKENS = {
    "sUSDe": {
        "address": "0x9D39A5DE30e57443BfF2A8307A4256c8797A3497",
        "decimals": 18,
        "protocols": {
            "Morpho": 7344848,
            "Aave":   7349560,
        },
    },
    "sUSDS": {
        "address": "0xa3931d71877C0E7a3148CB7Eb4463524FEc27fbD",
        "decimals": 18,
        "protocols": {
            "Morpho": 7367663,
            "Spark":  7368059,
        },
    },
    "syrupUSDC": {
        "address": "0x80ac24aA929EAF5013f6436CDa2a7BA190f5Cc0B",
        "decimals": 6,
        "protocols": {
            "Morpho": 7367806,
        },
    },
}


def get_top_holders(token_name: str, query_id: int, protocol: str) -> pd.DataFrame:
    print(f"  Querying {protocol} for {token_name} (query_id={query_id})...")
    result = dune.run_query(query=QueryBase(query_id=query_id))
    df = pd.DataFrame(result.result.rows)
    if df.empty:
        print(f"  Warning: no rows returned for {token_name}/{protocol}")
        return df
    df["current_balance"] = df["current_balance"].astype(float).map("{:,.6f}".format)
    df["total_received"] = df["total_received"].astype(float).map("{:,.6f}".format)
    df["token"] = token_name
    df["protocol"] = protocol
    return df


def is_eoa(address: str) -> bool:
    code = w3.eth.get_code(Web3.to_checksum_address(address))
    return code == b""


def flag_eoas(df: pd.DataFrame) -> pd.DataFrame:
    print(f"  Checking {len(df)} addresses via RPC...")
    df = df.copy()
    df["is_eoa"] = df["address"].apply(is_eoa)
    return df.reset_index(drop=True)


def save_whales(token_name: str, df: pd.DataFrame) -> None:
    cols = [
        "rank", "address", "current_balance", "total_received",
        "is_eoa", "is_looper", "is_flashloaner", "strategy_type", "protocol",
    ]
    output = df[cols].copy()

    output["_sort"] = output["total_received"].str.replace(",", "").astype(float)
    output["rank"] = (
        output.groupby("protocol")["_sort"]
        .rank(ascending=False, method="first")
        .astype(int)
    )
    output = (
        output.drop(columns=["_sort"])
        .sort_values(["protocol", "rank"])
        .reset_index(drop=True)
    )

    filename = f"{token_name}_whales.csv"
    output.to_csv(filename, index=False)
    print(f"  Saved {filename} ({len(output)} rows)")


def main():
    if not w3.is_connected():
        raise RuntimeError("Cannot connect to RPC — check RPC_URL in .env")
    print(f"RPC connected: {w3.is_connected()}\n")

    for token_name, meta in TOKENS.items():
        print(f"=== {token_name} ===")
        frames = []

        for protocol, query_id in meta["protocols"].items():
            df = get_top_holders(token_name, query_id, protocol)
            if not df.empty:
                frames.append(df)

        if not frames:
            print(f"  No data for {token_name}, skipping.\n")
            continue

        combined = pd.concat(frames, ignore_index=True)
        print(f"  {len(combined)} rows fetched across {len(frames)} protocol(s)")

        combined = flag_eoas(combined)
        save_whales(token_name, combined)
        print()


if __name__ == "__main__":
    main()
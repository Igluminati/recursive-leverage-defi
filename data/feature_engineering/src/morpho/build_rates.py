import pandas as pd
import requests

INPUT = "data/morpho/daily_features.csv"
BORROW_RATES = "data/morpho/from_dune/morpho_borrow_rates.csv"
SUPPLY_RATES = "data/morpho/morpho_supply_rates.csv"
RATE_COLUMNS = ["ybt_apy", "supply_rate", "borrow_rate", "carry_spread", "carry_spread_levered"]

APY_POOLS = {
    "sUSDe": "66985a81-9c51-46ca-9977-42b4fe7bc6df",
    "sUSDS": "d8c4eff5-c8a9-46fc-a888-057c4c668e72",
    "syrupUSDC": "43641cf5-a92e-416b-bce9-27113d3c0db6",
}

WHALE_MARKETS = {
    "W-1": "0x88a18b2f4d94e7ad27a381b15531c06abf05a7c99dd5d3c3679875fed6f7e742",
    "W-2": "0x3274643db77a064abd3bc851de77556a4ad2e2f502f4f0c80845fa8f909ecf0b",
    "W-3": "0x3274643db77a064abd3bc851de77556a4ad2e2f502f4f0c80845fa8f909ecf0b",
    "W-4": "0x90ef0c5a0dc7c4de4ad4585002d44e9d411d212d2f6258e94948beecf8b4c0d5",
    "W-5": "0xc9629945524f3fde56c7e8854a6c3d48e76b9d97236abbe73c750fcc7aeb8501",
    "W-6": "0x3274643db77a064abd3bc851de77556a4ad2e2f502f4f0c80845fa8f909ecf0b",
    "W-7": "0x90ef0c5a0dc7c4de4ad4585002d44e9d411d212d2f6258e94948beecf8b4c0d5",
    "W-8": "0x1247f1c237eceae0602eab1470a5061a6dd8f734ba88c7cdc5d6109fb0026b28",
    "W-9": "0x1247f1c237eceae0602eab1470a5061a6dd8f734ba88c7cdc5d6109fb0026b28",
    "W-10": "0x1247f1c237eceae0602eab1470a5061a6dd8f734ba88c7cdc5d6109fb0026b28",
    "W-11": "0x39d11026eae1c6ec02aa4c0910778664089cdd97c3fd23f68f7cd05e2e95af48",
}


def fetch_pool_apy(pool_id):
    response = requests.get(f"https://yields.llama.fi/chart/{pool_id}", timeout=30)
    response.raise_for_status()
    apy = pd.DataFrame(response.json()["data"])
    apy["date"] = pd.to_datetime(apy["timestamp"], utc=True).dt.normalize().dt.tz_localize(None)
    return apy.drop_duplicates("date").set_index("date")["apy"]


def compute_ybt_apy(df):
    df["ybt_apy"] = float("nan")
    for token in df["collateral_token"].unique():
        mask = df["collateral_token"] == token
        df.loc[mask, "ybt_apy"] = df.loc[mask, "date"].map(fetch_pool_apy(APY_POOLS[token]))
    return df


def main():
    df = pd.read_csv(INPUT, parse_dates=["date"])
    df = df.drop(columns=[c for c in RATE_COLUMNS if c in df.columns])
    df = compute_ybt_apy(df)

    rates = pd.read_csv(BORROW_RATES, parse_dates=["date"])[["date", "market_id", "borrow_rate"]]
    df["market_id"] = df["whale_id"].map(WHALE_MARKETS)
    df = df.merge(rates, on=["date", "market_id"], how="left")

    supply = pd.read_csv(SUPPLY_RATES, parse_dates=["date"])[["date", "market_id", "supply_apy_pct"]]
    supply = supply.rename(columns={"supply_apy_pct": "supply_rate"})

    df = df.merge(supply, on=["date", "market_id"], how="left")

    df = df.drop(columns=["market_id"])

    keys = ["whale_id", "collateral_token", "borrow_token"]
    df = df.sort_values(keys + ["date"])

    df[["ybt_apy", "borrow_rate", "supply_rate"]] = (
        df.groupby(keys)[["ybt_apy", "borrow_rate", "supply_rate"]].ffill()
    )
    df["supply_rate"] = df["supply_rate"].fillna(0.0)

    df["carry_spread"] = df["ybt_apy"] + df["supply_rate"] - df["borrow_rate"]
    df["carry_spread_levered"] = df["carry_spread"] * df["loop_depth"]
    df = df.sort_values(["whale_id", "date"]).reset_index(drop=True)

    df.to_csv(INPUT, index=False)
    print(f"Saved {len(df)} rows to {INPUT}")
    print(df.groupby("whale_id")[["ybt_apy", "supply_rate", "borrow_rate", "carry_spread"]].mean().round(3).to_string())


if __name__ == "__main__":
    main()
import pandas as pd
import requests

INPUT = "data/aave/daily_features.csv"
RATE_COLUMNS = ["ybt_apy", "borrow_rate", "carry_spread", "carry_spread_levered"]

APY_POOLS = {
    "sUSDe": "66985a81-9c51-46ca-9977-42b4fe7bc6df",
}

BORROW_RATES = {
    "USDT": "data/aave/from_dune/aave_borrow_rates.csv",
    "USDe": "data/aave/from_dune/aave_usde_borrow_rates.csv",
    "USDC": "data/aave/from_dune/aave_usdc_borrow_rates.csv",

}


def fetch_pool_apy(pool_id):
    response = requests.get(f"https://yields.llama.fi/chart/{pool_id}", timeout=30)
    response.raise_for_status()
    apy = pd.DataFrame(response.json()["data"])
    apy["date"] = pd.to_datetime(apy["timestamp"], utc=True).dt.normalize().dt.tz_localize(None)
    return apy.drop_duplicates("date").set_index("date")["apy"]


def load_rates(files, rate_col, token_col):
    frames = []
    for token, path in files.items():
        rates = pd.read_csv(path, parse_dates=["date"])[["date", rate_col]]
        rates[token_col] = token
        frames.append(rates)
    return pd.concat(frames, ignore_index=True)


def compute_ybt_apy(df):
    df["ybt_apy"] = df["date"].map(fetch_pool_apy(APY_POOLS["sUSDe"]))
    return df


def main():
    df = pd.read_csv(INPUT, parse_dates=["date"])
    df = df.drop(columns=[c for c in RATE_COLUMNS + ["supply_rate"] if c in df.columns])
    df = compute_ybt_apy(df)

    borrow = load_rates(BORROW_RATES, "borrow_rate", "borrow_token")
    df = df.merge(borrow, on=["date", "borrow_token"], how="left")

    keys = ["whale_id", "collateral_token", "borrow_token"]
    df = df.sort_values(keys + ["date"])
    df[["ybt_apy", "borrow_rate"]] = df.groupby(keys)[["ybt_apy", "borrow_rate"]].ffill()

    # A looper deposits sUSDe as collateral. The Aave v3 supply rate for sUSDe
    # is effectively zero, so the carry spread is the YBS yield minus borrow cost.
    df["carry_spread"] = df["ybt_apy"] - df["borrow_rate"]
    df["carry_spread_levered"] = df["carry_spread"] * df["loop_depth"]
    df = df.sort_values(["whale_id", "date"]).reset_index(drop=True)

    df.to_csv(INPUT, index=False)
    print(f"Saved {len(df)} rows to {INPUT}")
    print(df.groupby("whale_id")[["ybt_apy", "borrow_rate", "carry_spread"]].mean().round(3).to_string())


if __name__ == "__main__":
    main()

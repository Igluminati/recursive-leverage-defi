import pandas as pd

INPUT = "data/morpho/daily_panel_usd.csv"
OUTPUT = "data/morpho/daily_features.csv"

LIQUIDATION_THRESHOLD = {
    "W-1": 0.915,
    "W-4": 0.915,
    "W-5": 0.915
}


def compute_health_factor(df):
    df["liquidation_threshold"] = df["whale_id"].map(LIQUIDATION_THRESHOLD)
    df["health_factor"] = ((df["collateral_balance_usd"] * df["liquidation_threshold"]) / df["borrow_balance_usd"])
    df.loc[df["borrow_balance_usd"] < 1, "health_factor"] = pd.NA
    return df


def compute_ltv(df):
    df["ltv"] = df["borrow_balance_usd"] / df["collateral_balance_usd"]
    df.loc[df["collateral_balance_usd"] < 1, "ltv"] = pd.NA
    return df


def main():
    df = pd.read_csv(INPUT, parse_dates=["date"])

    df = compute_ltv(df)
    df = compute_health_factor(df)
    df = df.sort_values(["whale_id", "date"]).reset_index(drop=True)

    df.to_csv(OUTPUT, index=False)
    print(f"Saved {len(df)} rows to {OUTPUT}")


if __name__ == "__main__":
    main()

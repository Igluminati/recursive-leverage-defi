import pandas as pd

INPUT = "data/aave/daily_panel_usd.csv"
OUTPUT = "data/aave/daily_features.csv"
EVENTS = "data/aave/panel_raw_events.csv"

LIQUIDATION_THRESHOLD = {
    "W-6": 0.92,
}


def compute_health_factor(df):
    df["liquidation_threshold"] = df["whale_id"].map(LIQUIDATION_THRESHOLD)
    df["health_factor"] = (
        (df["collateral_balance_usd"] * df["liquidation_threshold"]) / df["borrow_balance_usd"]
    )
    df.loc[df["borrow_balance_usd"] < 1, "health_factor"] = pd.NA
    return df


def compute_ltv(df):
    df["ltv"] = df["borrow_balance_usd"] / df["collateral_balance_usd"]
    df.loc[df["collateral_balance_usd"] < 1, "ltv"] = pd.NA
    return df


def compute_distance_to_liquidation(df):
    df["distance_to_liq"] = df["liquidation_threshold"] - df["ltv"]
    df.loc[df["ltv"].isna(), "distance_to_liq"] = pd.NA
    return df


def compute_rebalancing(df, events):
    events["date"] = pd.to_datetime(events["timestamp"], utc=True).dt.normalize().dt.tz_localize(None)
    rebalance_days = (
        events[events["event_type"].isin(["supply", "withdraw", "borrow", "repay"])]
        .groupby(["whale_id", "date"])
        .size()
        .reset_index(name="event_count")
        .assign(rebalancing=1)
        [["whale_id", "date", "rebalancing"]]
    )
    df = df.merge(rebalance_days, on=["whale_id", "date"], how="left")
    df["rebalancing"] = df["rebalancing"].fillna(0).astype(int)
    return df


def main():
    df = pd.read_csv(INPUT, parse_dates=["date"])
    events = pd.read_csv(EVENTS)

    df = compute_ltv(df)
    df = compute_health_factor(df)
    df = compute_distance_to_liquidation(df)
    df = compute_rebalancing(df, events)
    df = df.sort_values(["whale_id", "date"]).reset_index(drop=True)

    df.to_csv(OUTPUT, index=False)
    print(f"Saved {len(df)} rows to {OUTPUT}")

    print("\nRebalancing days per whale:")
    print(df.groupby("whale_id")["rebalancing"].sum().astype(int).to_string())


if __name__ == "__main__":
    main()

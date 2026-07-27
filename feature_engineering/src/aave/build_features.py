import pandas as pd

INPUT = "data/aave/daily_panel_usd.csv"
OUTPUT = "data/aave/daily_features.csv"
EVENTS = "data/aave/panel_raw_events.csv"

LIQUIDATION_THRESHOLD = {
    "W-17": 0.92,
    "W-18": 0.92,
    "W-19": 0.92,
    "W-20": 0.92,
    "W-21": 0.92,
    "W-22": 0.92,
    "W-23": 0.92,
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


def compute_leverage(df):
    """
    Leverage = 1 / (1 - LTV), the continuous gearing of the position.

    A position at 90% LTV is 10x levered; at 80% LTV it is 5x. We report the
    continuous value rather than a rounded loop count because leverage is a
    property of the position, not of how it was assembled: a single flashloan
    can reach 10x in one transaction, whereas several manual loops may reach
    only 2x. Days with no debt (or no open position) are 0.

    Example:
        LTV 0.50 -> 1 / (1 - 0.50) = 2.00x
        LTV 0.80 -> 1 / (1 - 0.80) = 5.00x
        LTV 0.90 -> 1 / (1 - 0.90) = 10.00x
    """
    df["leverage"] = 1 / (1 - df["ltv"]).clip(lower=0.01)
    df.loc[df["ltv"].isna() | (df["borrow_balance_usd"] < 1), "leverage"] = 0.0
    return df


def compute_ltv_volatility(df):
    grouped = df.groupby(["whale_id", "collateral_token", "borrow_token"])["ltv"]
    df["ltv_vol_7d"] = grouped.transform(lambda s: s.rolling(7, min_periods=2).std())
    df["ltv_vol_14d"] = grouped.transform(lambda s: s.rolling(14, min_periods=2).std())
    return df


def compute_rebalancing_frequency(df):
    grouped = df.groupby(["whale_id", "collateral_token", "borrow_token"])["rebalancing"]
    df["rebal_freq_7d"] = grouped.transform(lambda s: s.rolling(7, min_periods=1).sum())
    df["rebal_freq_30d"] = grouped.transform(lambda s: s.rolling(30, min_periods=1).sum())
    return df


def compute_days_since_rebalance(df):
    position = ["whale_id", "collateral_token", "borrow_token"]
    rebalance_date = df["date"].where(df["rebalancing"] == 1)
    last_rebalance = rebalance_date.groupby([df[key] for key in position]).ffill()
    df["days_since_rebalance"] = (df["date"] - last_rebalance).dt.days
    return df


def compute_lagged_ltv(df):
    """
    Purpose: give the RQ3 classifier yesterday's (t-1), 3-day (t-3) and 7-day (t-7) LTV
    so it sees the recent trend, not just today's snapshot, when predicting stressed states.
    """
    grouped = df.groupby(["whale_id", "collateral_token", "borrow_token"])["ltv"]
    df["ltv_lag_1"] = grouped.shift(1)
    df["ltv_lag_3"] = grouped.shift(3)
    df["ltv_lag_7"] = grouped.shift(7)
    return df


def compute_token_identity(df):
    """
    Purpose: one-hot flags marking which market the whale is in (collateral and borrow
    token). Liquidation thresholds differ per market, so clustering can pick up
    market-specific behaviour rather than treating all positions alike.
    """
    collateral = pd.get_dummies(df["collateral_token"], prefix="coll").astype(int)
    borrow = pd.get_dummies(df["borrow_token"], prefix="debt").astype(int)
    return pd.concat([df, collateral, borrow], axis=1)


def main():
    df = pd.read_csv(INPUT, parse_dates=["date"])
    events = pd.read_csv(EVENTS)

    df = df.sort_values(["whale_id", "collateral_token", "borrow_token", "date"]).reset_index(drop=True)

    df = compute_ltv(df)
    df = compute_health_factor(df)
    df = compute_distance_to_liquidation(df)
    df = compute_rebalancing(df, events)
    df = compute_leverage(df)
    df = compute_ltv_volatility(df)
    df = compute_rebalancing_frequency(df)
    df = compute_days_since_rebalance(df)
    df = compute_lagged_ltv(df)
    df = compute_token_identity(df)
    df = df.sort_values(["whale_id", "date"]).reset_index(drop=True)

    df.to_csv(OUTPUT, index=False)
    print(f"Saved {len(df)} rows to {OUTPUT}")

    print("\nRebalancing days per whale:")
    print(df.groupby("whale_id")["rebalancing"].sum().astype(int).to_string())


if __name__ == "__main__":
    main()

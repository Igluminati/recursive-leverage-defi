import pandas as pd

INPUT = "data/morpho/daily_panel_usd.csv"
OUTPUT = "data/morpho/daily_features.csv"
EVENTS = "data/morpho/panel_raw_events.csv"

POSITION_KEYS = ["whale_id", "collateral_token", "borrow_token"]
EVENT_TYPES = ["supply", "withdraw", "borrow", "repay"]

# A change counts as real management only if it is material relative to the
# position, never in absolute terms: equity across these whales spans $5k to
# $12m, and one point of LTV is a 4% leverage move at LTV 0.50 but a 29% move at
# LTV 0.965. On days with no events the measured action is exactly zero, so
# these thresholds encode materiality rather than a noise floor.
LEVERAGE_MATERIAL = 0.02
EQUITY_MATERIAL = 0.02
EQUITY_DUST_USD = 1_000

LIQUIDATION_THRESHOLD = {
    "W-1": 0.915,
    "W-2": 0.965,
    "W-3": 0.965,
    "W-4": 0.915,
    "W-5": 0.915,
    "W-6": 0.965,
    "W-7": 0.915,
    "W-8": 0.915,
    "W-9": 0.915,
    "W-10": 0.915,
    "W-11": 0.86,
    "W-12": 0.965,
    "W-13": 0.965,
    "W-14": 0.965,
    "W-15": 0.915,
    "W-16": 0.915,
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


def compute_distance_to_liquidation(df):
    df["distance_to_liq"] = df["liquidation_threshold"] - df["ltv"]
    df.loc[df["ltv"].isna(), "distance_to_liq"] = pd.NA
    return df


def compute_position_activity(df, events):
    """
    Flag days on which the whale touched the position at all.

    An event row carries only the token it moved (supply/withdraw name the
    collateral, borrow/repay name the debt), so each side is attributed to the
    markets in the panel that use that token rather than joined on whale and
    date alone, which would mark every market a whale holds.
    """
    events = events.copy()
    events["date"] = pd.to_datetime(events["timestamp"], utc=True).dt.normalize().dt.tz_localize(None)
    events = events[events["event_type"].isin(EVENT_TYPES)]

    markets = df[POSITION_KEYS].drop_duplicates()
    collateral_side = events[events["event_type"].isin(["supply", "withdraw"])]
    debt_side = events[events["event_type"].isin(["borrow", "repay"])]

    activity = pd.concat(
        [
            collateral_side[["whale_id", "collateral_token", "date"]].merge(
                markets, on=["whale_id", "collateral_token"]
            ),
            debt_side[["whale_id", "borrow_token", "date"]].merge(
                markets, on=["whale_id", "borrow_token"]
            ),
        ]
    )[POSITION_KEYS + ["date"]].drop_duplicates()
    activity["position_activity"] = 1

    df = df.merge(activity, on=POSITION_KEYS + ["date"], how="left")
    df["position_activity"] = df["position_activity"].fillna(0).astype(int)
    return df


def leverage_from_ltv(ltv):
    """
    Leverage on a 1x-is-unlevered scale, for use inside ratios only.

    The published `leverage` column reports 0 on days with no debt, which would
    read a full repayment as a -100% move instead of a return to unlevered.
    """
    return 1 / (1 - ltv.fillna(0)).clip(lower=0.01)


def compute_action_deltas(df):
    """
    Separate what the whale did from what prices did.

    Yesterday's token balances marked at today's prices give the position the
    whale would have held had they done nothing, so whatever differs from that
    counterfactual is their action. Measured this way, days without events move
    by exactly zero.

    The two coordinates are equity and leverage, which reparameterise the
    position completely (collateral = equity x leverage, debt = equity x
    (leverage - 1)) and so isolate a change in size from a change in risk.
    Collateral cannot serve as the size axis: it moves whenever leverage moves.
    """
    grouped = df.groupby(POSITION_KEYS)
    collateral_prev = grouped["collateral_balance"].shift(1)
    debt_prev = grouped["borrow_balance"].shift(1)

    df["ltv_cf"] = (debt_prev * df["borrow_price"]) / (collateral_prev * df["collateral_price"])
    df["ltv_cf"] = df["ltv_cf"].replace([float("inf"), float("-inf")], float("nan"))

    leverage_cf = leverage_from_ltv(df["ltv_cf"])
    df["delta_leverage_rel"] = (leverage_from_ltv(df["ltv"]) - leverage_cf) / leverage_cf

    equity_prev = collateral_prev * df["collateral_price"] - debt_prev * df["borrow_price"]
    df["delta_equity_usd"] = (
        (df["collateral_balance"] - collateral_prev) * df["collateral_price"]
        - (df["borrow_balance"] - debt_prev) * df["borrow_price"]
    )
    # A position running at the top of its market's LTV holds almost no equity,
    # and dividing by that would report an ordinary deposit as a change of many
    # million percent, so the denominator stops at the dust threshold.
    df["delta_equity_rel"] = df["delta_equity_usd"] / equity_prev.abs().clip(lower=EQUITY_DUST_USD)

    unmeasurable = collateral_prev.isna() | df["ltv_cf"].isna()
    df.loc[unmeasurable, ["delta_leverage_rel", "delta_equity_rel", "delta_equity_usd"]] = float("nan")
    return df


def compute_activity_class(df):
    """
    Sort each active day into one of four mutually exclusive classes.

    `risk_rebalance` is the union of the two classes that move leverage and is
    the signal to use wherever risk management is the question; the broad
    `position_activity` flag counts capital moves and dust alongside it.

    The first observed day of a position has no counterfactual to compare
    against, so it is classified from what was opened: a levered position is a
    loop being built, a collateral-only deposit is capital arriving.
    """
    active = df["position_activity"] == 1
    leverage_moved = df["delta_leverage_rel"].abs() >= LEVERAGE_MATERIAL
    capital_moved = (df["delta_equity_rel"].abs() >= EQUITY_MATERIAL) & (
        df["delta_equity_usd"].abs() >= EQUITY_DUST_USD
    )

    opening = active & df["delta_leverage_rel"].isna()
    levered_open = opening & (df["borrow_balance_usd"] >= 1)

    df["leverage_adjust"] = (active & leverage_moved & ~capital_moved).astype(int)
    df["capital_flow"] = ((active & capital_moved & ~leverage_moved) | (opening & ~levered_open)).astype(int)
    df["levered_scaling"] = ((active & leverage_moved & capital_moved) | levered_open).astype(int)
    df["minor_activity"] = (active & ~opening & ~leverage_moved & ~capital_moved).astype(int)
    df["risk_rebalance"] = (df["leverage_adjust"] | df["levered_scaling"]).astype(int)
    return df


def compute_leverage(df):
    """
    Leverage = 1 / (1 - LTV), the continuous leverage of the position.

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


def compute_activity_frequency(df):
    for column, prefix in [
        ("position_activity", "activity"),
        ("risk_rebalance", "risk_rebal"),
        ("capital_flow", "capital_flow"),
    ]:
        grouped = df.groupby(POSITION_KEYS)[column]
        df[f"{prefix}_freq_7d"] = grouped.transform(lambda s: s.rolling(7, min_periods=1).sum())
        df[f"{prefix}_freq_30d"] = grouped.transform(lambda s: s.rolling(30, min_periods=1).sum())
    return df


def compute_days_since_activity(df):
    for column, name in [
        ("position_activity", "days_since_activity"),
        ("risk_rebalance", "days_since_risk_rebalance"),
    ]:
        event_date = df["date"].where(df[column] == 1)
        last_event = event_date.groupby([df[key] for key in POSITION_KEYS]).ffill()
        df[name] = (df["date"] - last_event).dt.days
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
    df = compute_leverage(df)
    df = compute_position_activity(df, events)
    df = df.sort_values(POSITION_KEYS + ["date"]).reset_index(drop=True)
    df = compute_action_deltas(df)
    df = compute_activity_class(df)
    df = compute_ltv_volatility(df)
    df = compute_activity_frequency(df)
    df = compute_days_since_activity(df)
    df = compute_lagged_ltv(df)
    df = compute_token_identity(df)
    df = df.sort_values(["whale_id", "date"]).reset_index(drop=True)

    df.to_csv(OUTPUT, index=False)
    print(f"Saved {len(df)} rows to {OUTPUT}")

    classes = ["leverage_adjust", "capital_flow", "levered_scaling", "minor_activity"]
    print("\nActivity days per whale:")
    print(df.groupby("whale_id")[["position_activity"] + classes + ["risk_rebalance"]].sum().astype(int).to_string())
    print("\nShare of whale-days:")
    print((100 * df[["position_activity"] + classes + ["risk_rebalance"]].mean()).round(2).to_string())


if __name__ == "__main__":
    main()
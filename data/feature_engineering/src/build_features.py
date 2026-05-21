import os

import pandas as pd

INPUT = "data/daily_panel_usd.csv"
OUTPUT = "data/daily_features.csv"
HF_PATH = "data/w3_aave_health_factor.csv"


def load_panel():
    df = pd.read_csv(INPUT)
    df["date"] = pd.to_datetime(df["date"])
    return df


def aggregate(df):
    collateral = (
        df.groupby(["whale_id", "protocol", "date", "collateral_token"])
        .agg(collateral_balance_usd=("collateral_balance_usd", "first"))
        .groupby(["whale_id", "protocol", "date"])
        .agg(collateral_balance_usd=("collateral_balance_usd", "sum"))
        .reset_index()
    )

    borrow = (
        df.groupby(["whale_id", "protocol", "date", "borrow_token"])
        .agg(borrow_balance_usd=("borrow_balance_usd", "first"))
        .groupby(["whale_id", "protocol", "date"])
        .agg(borrow_balance_usd=("borrow_balance_usd", "sum"))
        .reset_index()
    )

    return collateral.merge(borrow, on=["whale_id", "protocol", "date"])


def compute_ltv(df):
    df["ltv"] = df["borrow_balance_usd"] / df["collateral_balance_usd"]
    df["ltv"] = df["ltv"].replace([float("inf"), float("-inf")], pd.NA)
    df.loc[df["collateral_balance_usd"] < 1, "ltv"] = pd.NA
    return df


def merge_aave_health_factor(df):
    """Attach on-chain HF for W-3 when w3_aave_health_factor.csv exists."""
    if not os.path.exists(HF_PATH):
        return df

    hf = pd.read_csv(HF_PATH)
    hf["date"] = pd.to_datetime(hf["date"])
    hf = hf[["date", "health_factor", "total_collateral_usd", "total_debt_usd"]].rename(
        columns={
            "total_collateral_usd": "collateral_balance_usd_aave",
            "total_debt_usd": "borrow_balance_usd_aave",
        }
    )

    out = df.merge(hf, on=["date"], how="left")
    out.loc[out["whale_id"] != "W-3", ["health_factor", "collateral_balance_usd_aave", "borrow_balance_usd_aave"]] = pd.NA
    return out


def main():
    panel = load_panel()
    df = aggregate(panel)
    df = compute_ltv(df)
    df = merge_aave_health_factor(df)

    df = df.sort_values(["whale_id", "date"]).reset_index(drop=True)
    df.to_csv(OUTPUT, index=False)
    print(f"Saved {len(df)} rows to {OUTPUT}")
    print()

    for whale_id, group in df.groupby("whale_id"):
        active = group.dropna(subset=["ltv"])
        print(f"{whale_id}: {len(active)} active days, "
              f"ltv_mean={active['ltv'].mean():.3f}, "
              f"ltv_max={active['ltv'].max():.3f}, "
              f"ltv_min={active['ltv'].min():.3f}")


if __name__ == "__main__":
    main()
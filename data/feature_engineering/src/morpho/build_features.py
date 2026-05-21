import pandas as pd

INPUT = "data/morpho/daily_panel_usd.csv"
OUTPUT = "data/morpho/daily_features.csv"


def compute_ltv(df):
    df["ltv"] = df["borrow_balance_usd"] / df["collateral_balance_usd"]
    df.loc[df["collateral_balance_usd"] < 1, "ltv"] = pd.NA
    return df


def main():
    df = pd.read_csv(INPUT, parse_dates=["date"])

    df = compute_ltv(df)
    df = df.sort_values(["whale_id", "date"]).reset_index(drop=True)
    df.to_csv(OUTPUT, index=False)
    print(f"Saved {len(df)} rows to {OUTPUT}")

    for whale_id, group in df.groupby("whale_id"):
        active = group.dropna(subset=["ltv"])
        print(f"{whale_id}: {len(active)} active days, "
              f"ltv_mean={active['ltv'].mean():.3f}, "
              f"ltv_max={active['ltv'].max():.3f}, "
              f"ltv_min={active['ltv'].min():.3f}")


if __name__ == "__main__":
    main()
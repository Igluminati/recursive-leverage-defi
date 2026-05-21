import pandas as pd

RAW_EVENTS = "data/morpho/panel_raw_events.csv"
OUTPUT = "data/morpho/daily_panel.csv"


def parse_timestamps(series):
    return pd.to_datetime(series, utc=True).dt.tz_localize(None)

def load_events():
    df = pd.read_csv(RAW_EVENTS)
    df["date"] = parse_timestamps(df["timestamp"]).dt.normalize()
    return df


def build_whale_panel(df_whale):
    protocol = df_whale["protocol"].iloc[0]
    date_range = pd.date_range(df_whale["date"].min(), df_whale["date"].max(), freq="D")

    collateral_tokens = df_whale["collateral_token"].dropna().unique()
    borrow_tokens = df_whale["borrow_token"].dropna().unique()

    rows = []
    for collateral_token in collateral_tokens:
        coll_events = df_whale[df_whale["collateral_token"] == collateral_token].copy()
        coll_events["net"] = coll_events.apply(
            lambda r: r["amount"] if r["event_type"] == "supply" else -r["amount"], axis=1
        )
        daily_collateral = (
            coll_events.groupby("date")["net"]
            .sum()
            .reindex(date_range, fill_value=0)
            .cumsum()
            .clip(lower=0)
            .rename("collateral_balance")
        )

        for borrow_token in borrow_tokens:
            debt_events = df_whale[df_whale["borrow_token"] == borrow_token].copy()
            debt_events["net"] = debt_events.apply(
                lambda r: r["amount"] if r["event_type"] == "borrow" else -r["amount"], axis=1
            )
            daily_borrow = (
                debt_events.groupby("date")["net"]
                .sum()
                .reindex(date_range, fill_value=0)
                .cumsum()
                .clip(lower=0)
                .rename("borrow_balance")
            )

            panel = pd.concat([daily_collateral, daily_borrow], axis=1).reset_index()
            panel.rename(columns={"index": "date"}, inplace=True)
            panel["protocol"] = protocol
            panel["collateral_token"] = collateral_token
            panel["borrow_token"] = borrow_token
            rows.append(panel)

    return pd.concat(rows, ignore_index=True)


def main():
    df = load_events()

    panels = []
    for whale_id, df_whale in df.groupby("whale_id"):
        panel = build_whale_panel(df_whale)
        panel.insert(0, "whale_id", whale_id)
        panels.append(panel)

    result = pd.concat(panels, ignore_index=True)
    result = result[["whale_id", "protocol", "date", "collateral_token", "borrow_token",
                     "collateral_balance", "borrow_balance"]]
    result = result.sort_values(["whale_id", "collateral_token", "borrow_token", "date"]).reset_index(drop=True)

    result.to_csv(OUTPUT, index=False)
    print(f"Saved {len(result)} rows to {OUTPUT}")
    print()

    for whale_id, group in result.groupby("whale_id"):
        for (ct, bt), sub in group.groupby(["collateral_token", "borrow_token"]):
            print(f"{whale_id} / {ct} / {bt}: {len(sub)} days, "
                  f"collateral_balance max={sub['collateral_balance'].max():,.0f}, "
                  f"borrow_balance max={sub['borrow_balance'].max():,.0f}")


if __name__ == "__main__":
    main()
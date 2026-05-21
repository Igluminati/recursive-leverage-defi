import pandas as pd
import requests
import time

PANEL = "data/daily_panel.csv"
OUTPUT = "data/daily_panel_usd.csv"

TOKEN_ADDRESSES = {
    "sUSDe":     "ethereum:0x9d39a5de30e57443bff2a8307a4256c8797a3497",
    "syrupUSDC": "ethereum:0x80ac24aA929eaF5013f6436cdA2a7ba190f5Cc0b",
    "USDC":      "ethereum:0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
    "USDe":      "ethereum:0x4c9edd5852cd905f086c759e8383e09bff1e68b3",
    "USDtb":     "ethereum:0xc139190f447e929f090edeb554d95abb8b18ac1c",
    "PYUSD":     "ethereum:0x6c3ea9036406852006290770bedfcaba0e23a0e8",
}


def fetch_prices(token, address, start_date, end_date):
    start_ts = int(pd.Timestamp(start_date).timestamp())
    span = (pd.Timestamp(end_date) - pd.Timestamp(start_date)).days + 2

    url = f"https://coins.llama.fi/chart/{address}"
    params = {"start": start_ts, "span": span, "period": "1d"}

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    prices = data["coins"][address]["prices"]
    df = pd.DataFrame(prices, columns=["timestamp", "price"])
    df["date"] = pd.to_datetime(df["timestamp"], unit="s").dt.normalize()
    df = df.drop_duplicates("date").set_index("date")["price"].rename(token)

    print(f"    {len(df)} days fetched, "
          f"min={df.min():.4f}, max={df.max():.4f}, "
          f"first={df.iloc[0]:.4f} ({df.index[0].date()}), "
          f"last={df.iloc[-1]:.4f} ({df.index[-1].date()})")
    return df


def load_panel():
    df = pd.read_csv(PANEL)
    df["date"] = pd.to_datetime(df["date"])
    return df


def main():
    panel = load_panel()
    start_date = panel["date"].min()
    end_date = panel["date"].max()

    tokens = set(panel["collateral_token"].unique()) | set(panel["borrow_token"].unique())
    tokens.discard("")

    print(f"Fetching prices for: {sorted(tokens)}")
    price_series = {}
    for token in sorted(tokens):
        address = TOKEN_ADDRESSES[token]
        print(f"  {token}...")
        price_series[token] = fetch_prices(token, address, start_date, end_date)
        time.sleep(0.5)

    prices_df = pd.DataFrame(price_series)
    prices_df = prices_df.ffill()
    prices_df.index.name = "date"
    prices_df = prices_df.reset_index()
    prices_df["date"] = pd.to_datetime(prices_df["date"]).dt.normalize()
    prices_df.columns = ["date"] + [f"{c}_price" for c in prices_df.columns[1:]]

    panel = panel.merge(prices_df, on="date", how="left")
    price_cols = [c for c in panel.columns if c.endswith("_price") and c != "collateral_price" and c != "borrow_price"]
    panel[price_cols] = panel[price_cols].ffill()

    panel["collateral_price"] = panel.apply(
        lambda r: r[f"{r['collateral_token']}_price"]
        if pd.notna(r["collateral_token"]) else None, axis=1
    )

    panel["borrow_price"] = panel.apply(
        lambda r: r[f"{r['borrow_token']}_price"]
        if pd.notna(r["borrow_token"]) else None, axis=1
    )

    panel["collateral_balance_usd"] = panel["collateral_balance"] * panel["collateral_price"]
    panel["borrow_balance_usd"] = panel["borrow_balance"] * panel["borrow_price"]

    result = panel[[
        "whale_id", "protocol", "date",
        "collateral_token", "borrow_token",
        "collateral_balance", "borrow_balance",
        "collateral_price", "borrow_price",
        "collateral_balance_usd", "borrow_balance_usd",
    ]]

    result.to_csv(OUTPUT, index=False)
    print(f"\nSaved {len(result)} rows to {OUTPUT}")
    print()

    for whale_id, group in result.groupby("whale_id"):
        for borrow_token, sub in group.groupby("borrow_token"):
            print(f"{whale_id} / {borrow_token}:")
            print(f"  collateral_balance_usd max = {sub['collateral_balance_usd'].max():,.0f}")
            print(f"  borrow_balance_usd max     = {sub['borrow_balance_usd'].max():,.0f}")


if __name__ == "__main__":
    main()
import pandas as pd
import requests
import time

PANEL = "data/morpho/daily_panel.csv"
OUTPUT = "data/morpho/daily_panel_usd.csv"

TOKEN_ADDRESSES = {
    "sUSDe":     "ethereum:0x9d39a5de30e57443bff2a8307a4256c8797a3497",
    "syrupUSDC": "ethereum:0x80ac24aA929eaF5013f6436cdA2a7ba190f5Cc0b",
    "USDtb":     "ethereum:0xc139190f447e929f090edeb554d95abb8b18ac1c",
    "PYUSD":     "ethereum:0x6c3ea9036406852006290770bedfcaba0e23a0e8",
}


def fetch_prices(address, start_date, end_date):
    start_ts = int(pd.Timestamp(start_date).timestamp())
    span = (pd.Timestamp(end_date) - pd.Timestamp(start_date)).days + 2

    response = requests.get(
        f"https://coins.llama.fi/chart/{address}",
        params={"start": start_ts, "span": span, "period": "1d"},
        timeout=30,
    )
    response.raise_for_status()

    prices = response.json()["coins"][address]["prices"]
    df = pd.DataFrame(prices, columns=["timestamp", "price"])
    df["date"] = pd.to_datetime(df["timestamp"], unit="s").dt.normalize()
    return df.drop_duplicates("date").set_index("date")["price"].rename("price")


def main():
    panel = pd.read_csv(PANEL, parse_dates=["date"])
    start_date, end_date = panel["date"].min(), panel["date"].max()

    tokens = set(panel["collateral_token"]) | set(panel["borrow_token"])

    print(f"Fetching prices for: {sorted(tokens)}")
    price_map = {}
    for token in sorted(tokens):
        print(f"  {token}...")
        price_map[token] = fetch_prices(TOKEN_ADDRESSES[token], start_date, end_date)
        time.sleep(0.5)

    def attach_prices(df, token_col, price_col):
        for token, prices in price_map.items():
            mask = df[token_col] == token
            df.loc[mask, price_col] = df.loc[mask, "date"].map(prices)
        df[price_col] = pd.to_numeric(df[price_col], errors="coerce").ffill()

    panel["collateral_price"] = None
    panel["borrow_price"] = None
    attach_prices(panel, "collateral_token", "collateral_price")
    attach_prices(panel, "borrow_token", "borrow_price")

    panel["collateral_balance_usd"] = panel["collateral_balance"] * panel["collateral_price"].astype(float)
    panel["borrow_balance_usd"] = panel["borrow_balance"] * panel["borrow_price"].astype(float)

    panel.to_csv(OUTPUT, index=False)
    print(f"Saved {len(panel)} rows to {OUTPUT}")


if __name__ == "__main__":
    main()
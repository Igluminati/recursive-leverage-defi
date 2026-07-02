import pandas as pd
import requests
import time

PANEL = "data/morpho/daily_panel.csv"
OUTPUT = "data/morpho/daily_panel_usd.csv"

TOKEN_ADDRESSES = {
    "sUSDe": "ethereum:0x9d39a5de30e57443bff2a8307a4256c8797a3497",
    "sUSDS": "ethereum:0xa3931d71877C0E7a3148CB7Eb4463524FEc27fbD",
    "syrupUSDC": "ethereum:0x80ac24aA929eaF5013f6436cdA2a7ba190f5Cc0b",
    "USDtb": "ethereum:0xc139190f447e929f090edeb554d95abb8b18ac1c",
    "USDT": "ethereum:0xdac17f958d2ee523a2206206994597c13d831ec7",
    "PYUSD": "ethereum:0x6c3ea9036406852006290770bedfcaba0e23a0e8",
    "DAI": "ethereum:0x6b175474e89094c44da98b954eedeac495271d0f",
    "USDC": "ethereum:0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
}


def fetch_prices(address, start_date, end_date):
    CHUNK_DAYS = 365
    all_prices = []

    chunk_start = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date)

    while chunk_start <= end_ts:
        chunk_end = min(chunk_start + pd.Timedelta(days=CHUNK_DAYS - 1), end_ts)
        start_ts = int(chunk_start.timestamp())
        span = (chunk_end - chunk_start).days + 2

        response = requests.get(
            f"https://coins.llama.fi/chart/{address}",
            params={"start": start_ts, "span": span, "period": "1d"},
            timeout=30,
        )
        response.raise_for_status()

        prices = response.json()["coins"][address]["prices"]
        all_prices.extend(prices)

        chunk_start = chunk_end + pd.Timedelta(days=1)
        time.sleep(0.3)

    df = pd.DataFrame(all_prices, columns=["timestamp", "price"])
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

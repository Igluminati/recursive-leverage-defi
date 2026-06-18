import pandas as pd
import requests
import time

PANEL = "data/aave/daily_panel.csv"
OUTPUT = "data/aave/daily_panel_usd.csv"

TOKEN_ADDRESSES = {
    "sUSDe": "ethereum:0x9d39a5de30e57443bff2a8307a4256c8797a3497",
    "USDT": "ethereum:0xdac17f958d2ee523a2206206994597c13d831ec7",
    "USDe": "ethereum:0x4c9edd5852cd905f086c759e8383e09bff1e68b3",
}

FALLBACK_PRICES = {
    "sUSDe": 1.2,
    "USDT": 1.0,
    "USDe": 1.0,
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
        try:
            prices = fetch_prices(TOKEN_ADDRESSES[token], start_date, end_date)
            if prices.empty:
                raise ValueError("No prices returned")
            price_map[token] = prices
        except Exception:
            print(f"    Using fallback price for {token}: {FALLBACK_PRICES.get(token, 1.0)}")
            date_range = pd.date_range(start_date, end_date, freq="D")
            price_map[token] = pd.Series(FALLBACK_PRICES.get(token, 1.0), index=date_range, name="price")
        time.sleep(0.5)

    def attach_prices(df, token_col, price_col):
        for token, prices in price_map.items():
            mask = df[token_col] == token
            prices.index = prices.index.normalize()
            df.loc[mask, price_col] = df.loc[mask, "date"].dt.normalize().map(prices)
        df[price_col] = pd.to_numeric(df[price_col], errors="coerce")
        df[price_col] = df[price_col].bfill().ffill()

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

import os
import time
from datetime import datetime, timezone

import pandas as pd
from dotenv import load_dotenv
from web3 import Web3

AVG_BLOCK_TIME_SEC = 12
BLOCKS_PER_DAY = 7200

load_dotenv()

AAVE_V3_POOL = Web3.to_checksum_address("0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2")
W3_ADDRESS = Web3.to_checksum_address("0xea03e659a2e59c3715c6517afe58541be162161a")

FEATURES_PATH = "data/daily_features.csv"
OUTPUT_PATH = "data/w3_aave_health_factor.csv"
BLOCK_CACHE_PATH = "data/w3_eod_block_cache.csv"

POOL_ABI = [
    {
        "inputs": [{"name": "user", "type": "address"}],
        "name": "getUserAccountData",
        "outputs": [
            {"name": "totalCollateralBase", "type": "uint256"},
            {"name": "totalDebtBase", "type": "uint256"},
            {"name": "availableBorrowsBase", "type": "uint256"},
            {"name": "currentLiquidationThreshold", "type": "uint256"},
            {"name": "ltv", "type": "uint256"},
            {"name": "healthFactor", "type": "uint256"},
        ],
        "stateMutability": "view",
        "type": "function",
    }
]

HF_NO_DEBT_THRESHOLD = 10**50


def connect():
    rpc_url = os.getenv("RPC_URL")
    if not rpc_url:
        raise SystemExit("Set RPC_URL in .env (archive mainnet endpoint required).")
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        raise SystemExit(f"Could not connect to RPC_URL: {rpc_url}")
    return w3


def load_w3_dates():
    df = pd.read_csv(FEATURES_PATH)
    w3 = df[df["whale_id"] == "W-3"].copy()
    w3["date"] = pd.to_datetime(w3["date"])
    return sorted(w3["date"].dt.normalize().unique())


def end_of_day_unix(date):
    dt = datetime(date.year, date.month, date.day, 23, 59, 59, tzinfo=timezone.utc)
    return int(dt.timestamp())


def rpc_retry(fn, retries=8):
    for attempt in range(retries):
        try:
            return fn()
        except Exception as exc:
            msg = str(exc)
            if "429" not in msg and "Too Many Requests" not in msg:
                raise
            time.sleep(min(60, 2**attempt))
    return fn()


def block_at_or_before(w3, target_ts, hint_block=None):
    latest = rpc_retry(lambda: w3.eth.get_block("latest"))
    if target_ts >= latest["timestamp"]:
        return latest["number"]

    if hint_block is not None:
        lo = max(0, int(hint_block))
        hi = min(latest["number"], lo + BLOCKS_PER_DAY)
    else:
        genesis = rpc_retry(lambda: w3.eth.get_block(0))
        est = int((target_ts - genesis["timestamp"]) / AVG_BLOCK_TIME_SEC)
        lo = max(0, est - 5000)
        hi = min(latest["number"], est + 5000)

    while lo < hi:
        mid = (lo + hi + 1) // 2
        if rpc_retry(lambda m=mid: w3.eth.get_block(m))["timestamp"] <= target_ts:
            lo = mid
        else:
            hi = mid - 1
    return lo


def load_block_cache():
    if not os.path.exists(BLOCK_CACHE_PATH):
        return {}
    cache = pd.read_csv(BLOCK_CACHE_PATH)
    cache["date"] = pd.to_datetime(cache["date"])
    return dict(zip(cache["date"].dt.normalize(), cache["block_number"]))


def save_block_cache(cache):
    rows = [{"date": d, "block_number": b} for d, b in sorted(cache.items())]
    pd.DataFrame(rows).to_csv(BLOCK_CACHE_PATH, index=False)


def parse_account_data(result):
    collateral_base, debt_base, _, liq_threshold, ltv_wad, hf_wad = result
    collateral_usd = collateral_base / 1e8
    debt_usd = debt_base / 1e8
    liq_threshold_pct = liq_threshold / 10000
    ltv_protocol_pct = ltv_wad / 10000

    if hf_wad >= HF_NO_DEBT_THRESHOLD:
        health_factor = None
    else:
        health_factor = hf_wad / 1e18

    return {
        "total_collateral_usd": collateral_usd,
        "total_debt_usd": debt_usd,
        "health_factor": health_factor,
        "ltv_protocol_pct": ltv_protocol_pct,
        "liquidation_threshold_pct": liq_threshold_pct,
    }


def main():
    w3 = connect()
    pool = w3.eth.contract(address=AAVE_V3_POOL, abi=POOL_ABI)
    dates = load_w3_dates()
    block_cache = load_block_cache()

    rows = []
    prev_block = None
    for i, date in enumerate(dates):
        date_norm = pd.Timestamp(date).normalize()
        if date_norm not in block_cache:
            ts = end_of_day_unix(date_norm)
            block_cache[date_norm] = block_at_or_before(w3, ts, hint_block=prev_block)
            save_block_cache(block_cache)

        block_number = int(block_cache[date_norm])
        prev_block = block_number
        raw = rpc_retry(
            lambda b=block_number: pool.functions.getUserAccountData(W3_ADDRESS).call(
                block_identifier=b
            )
        )
        time.sleep(0.05)
        parsed = parse_account_data(raw)
        rows.append(
            {
                "whale_id": "W-3",
                "protocol": "aave",
                "date": date_norm.date().isoformat(),
                "block_number": block_number,
                **parsed,
            }
        )
        if (i + 1) % 20 == 0:
            print(f"  {i + 1}/{len(dates)} days...")

    save_block_cache(block_cache)
    hf_df = pd.DataFrame(rows)

    simple = pd.read_csv(FEATURES_PATH)
    simple = simple[simple["whale_id"] == "W-3"][["date", "ltv", "collateral_balance_usd", "borrow_balance_usd"]]
    simple["date"] = pd.to_datetime(simple["date"]).dt.date.astype(str)
    out = hf_df.merge(simple, on="date", how="left", suffixes=("", "_panel"))
    out.rename(
        columns={
            "ltv": "ltv_panel_simple",
            "collateral_balance_usd": "collateral_usd_panel",
            "borrow_balance_usd": "borrow_usd_panel",
        },
        inplace=True,
    )
    out.to_csv(OUTPUT_PATH, index=False)
    print(f"Saved {len(out)} rows to {OUTPUT_PATH}")

    if os.path.exists(FEATURES_PATH):
        features = pd.read_csv(FEATURES_PATH)
        features["date"] = pd.to_datetime(features["date"])
        for col in ("health_factor", "collateral_balance_usd_aave", "borrow_balance_usd_aave"):
            if col in features.columns:
                features = features.drop(columns=[col])
        hf_cols = out[["date", "health_factor", "total_collateral_usd", "total_debt_usd"]].rename(
            columns={
                "total_collateral_usd": "collateral_balance_usd_aave",
                "total_debt_usd": "borrow_balance_usd_aave",
            }
        )
        hf_cols["date"] = pd.to_datetime(hf_cols["date"])
        features = features.merge(hf_cols, on="date", how="left")
        mask = features["whale_id"] != "W-3"
        features.loc[mask, ["health_factor", "collateral_balance_usd_aave", "borrow_balance_usd_aave"]] = pd.NA
        features.to_csv(FEATURES_PATH, index=False)
        print(f"Merged HF columns into {FEATURES_PATH}")

    valid = out.dropna(subset=["health_factor"])
    print(f"Days with debt (HF defined): {len(valid)}")
    if len(valid):
        print(f"  HF min={valid['health_factor'].min():.4f}, max={valid['health_factor'].max():.4f}")
        over = valid[valid["health_factor"] < 1]
        print(f"  Days with HF < 1 (liquidatable): {len(over)}")
        spike = out[out["date"] == "2025-09-25"]
        if len(spike):
            r = spike.iloc[0]
            print(f"\n2025-09-25:")
            print(f"  panel simple LTV: {r['ltv_panel_simple']:.4f}")
            print(f"  Aave HF:          {r['health_factor']}")
            print(f"  Aave collateral:  ${r['total_collateral_usd']:,.0f}")
            print(f"  Aave debt:        ${r['total_debt_usd']:,.0f}")


if __name__ == "__main__":
    main()

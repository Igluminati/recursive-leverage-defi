import os
import csv
import pandas as pd
from collections import Counter

WHALES = {
    "W-1": {
        "address": "0x080ccea8654fd4ff80b81e46cff2278689d88fb0",
        "protocol": "morpho",
        "token": "sUSDe",
        "source": "dune",
        "borrow_assets": {"USDtb"},
    },
    "W-3": {
        "address": "0xea03e659a2e59c3715c6517afe58541be162161a",
        "protocol": "aave",
        "token": "sUSDe",
        "source": "dune",
        "collateral_assets": {"sUSDe", "USDe"},
        "borrow_assets": {"USDC", "USDe"},
    },
    "W-4": {
        "address": "0x0d4f7b204626e8233c5b42b1269a78e236e9a06b",
        "protocol": "morpho",
        "token": "sUSDe",
        "source": "dune",
        "borrow_assets": {"PYUSD"},
    },
    "W-5": {
        "address": "0x24385a793f725328d7f6224430e48b4236326717",
        "protocol": "morpho",
        "token": "syrupUSDC",
        "source": "dune",
        "borrow_assets": {"PYUSD"},
    },
}

DUNE_FILES = {
    "W-1": "data/morpho_w1_events.csv",
    "W-3": "data/aave_w3_events.csv",
    "W-4": "data/morpho_w4_events.csv",
    "W-5": "data/morpho_w5_events.csv",
}

COLLATERAL_EVENTS = {"supply", "withdraw"}
DEBT_EVENTS = {"borrow", "repay"}

FIELDNAMES = [
    "whale_id", "protocol", "event_type",
    "block_number", "timestamp", "tx_hash",
    "collateral_token", "borrow_token", "amount",
]


def build_row(whale_id, meta, event_type, block_number, timestamp, tx_hash, asset, amount):
    if event_type in COLLATERAL_EVENTS:
        collateral_assets = meta.get("collateral_assets", set())
        if not collateral_assets:
            collateral_assets = {meta["token"]}
        if asset not in collateral_assets:
            return None
        collateral_token, borrow_token = asset, ""
    elif event_type in DEBT_EVENTS:
        if asset not in meta["borrow_assets"]:
            return None
        collateral_token, borrow_token = "", asset
    else:
        return None

    return {
        "whale_id": whale_id,
        "protocol": meta["protocol"],
        "event_type": event_type,
        "block_number": block_number,
        "timestamp": timestamp,
        "tx_hash": tx_hash,
        "collateral_token": collateral_token,
        "borrow_token": borrow_token,
        "amount": amount,
    }


def load_from_dune(whale_id, meta):
    df = pd.read_csv(DUNE_FILES[whale_id])
    df.columns = df.columns.str.strip().str.lower()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.strftime("%Y-%m-%d %H:%M:%S UTC")

    rows = []
    for _, record in df.iterrows():
        row = build_row(
            whale_id=whale_id,
            meta=meta,
            event_type=str(record["event_type"]).strip().lower(),
            block_number=record["block_number"],
            timestamp=record["timestamp"],
            tx_hash=record["tx_hash"],
            asset=str(record["asset"]).strip(),
            amount=record["amount"],
        )
        if row:
            rows.append(row)
    return rows


if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    all_events = []

    for whale_id, meta in WHALES.items():
        print(f"Processing {whale_id} ({meta['protocol']}, {meta['address'][:10]}...)...")
        events = load_from_dune(whale_id, meta)
        print(f"  {len(events)} events")
        all_events.extend(events)

    all_events.sort(key=lambda r: (r["whale_id"], str(r["timestamp"])))

    output_path = "data/panel_raw_events.csv"
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(all_events)

    print("\nSummary:")
    total_counts = Counter(e["whale_id"] for e in all_events)
    event_counts = Counter((e["whale_id"], e["event_type"]) for e in all_events)
    for whale_id in WHALES:
        total = total_counts.get(whale_id, 0)
        supply = event_counts.get((whale_id, "supply"), 0)
        withdraw = event_counts.get((whale_id, "withdraw"), 0)
        borrow = event_counts.get((whale_id, "borrow"), 0)
        repay = event_counts.get((whale_id, "repay"), 0)
        print(f"{whale_id}: {total} events (supply={supply}, withdraw={withdraw}, borrow={borrow}, repay={repay})")
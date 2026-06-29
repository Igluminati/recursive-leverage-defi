import os
import csv
import pandas as pd
from collections import Counter

WHALES = {
    "W-6": {
        "address": "0x029469ca80e6c94436af010a369f54935a711080",
        "protocol": "aave",
        "collateral": "sUSDe",
        "borrow": "USDT",
    }
}

DUNE_FILES = {
    "W-6": "data/aave/from_dune/aave_w6_events.csv",
}

COLLATERAL_EVENTS = {"supply", "withdraw"}
DEBT_EVENTS = {"borrow", "repay"}

FIELDNAMES = [
    "whale_id", "protocol", "event_type",
    "block_number", "timestamp", "tx_hash",
    "collateral_token", "borrow_token", "amount",
]


def build_row(whale_id, meta, event_type, block_number, timestamp, tx_hash, amount):
    if event_type in COLLATERAL_EVENTS:
        collateral_token, borrow_token = meta["collateral"], ""
    else:
        collateral_token, borrow_token = "", meta["borrow"]

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
            amount=record["amount"],
        )
        rows.append(row)
    return rows


if __name__ == "__main__":
    os.makedirs("data/aave", exist_ok=True)
    all_events = []

    for whale_id, meta in WHALES.items():
        print(f"Processing {whale_id} ({meta['protocol']}, {meta['address'][:10]}...)...")
        events = load_from_dune(whale_id, meta)
        print(f"  {len(events)} events")
        all_events.extend(events)

    all_events.sort(key=lambda r: (r["whale_id"], str(r["timestamp"])))

    output_path = "data/aave/panel_raw_events.csv"
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(all_events)

    print("\nSummary:")
    total_counts = Counter(e["whale_id"] for e in all_events)
    event_counts = Counter((e["whale_id"], e["event_type"]) for e in all_events)
    for whale_id in WHALES:
        total = total_counts.get(whale_id)
        supply = event_counts.get((whale_id, "supply"))
        withdraw = event_counts.get((whale_id, "withdraw"))
        borrow = event_counts.get((whale_id, "borrow"))
        repay = event_counts.get((whale_id, "repay"))
        print(f"{whale_id}: {total} events (supply={supply}, withdraw={withdraw}, borrow={borrow}, repay={repay})")

import os
import csv
import pandas as pd
from collections import Counter

WHALES = {
    "W-1": {
        "address": "0x080ccea8654fd4ff80b81e46cff2278689d88fb0",
        "protocol": "morpho",
        "collateral": "sUSDe",
        "borrow": "USDtb",
    },
    "W-2": {
        "address": "0x97bb0e08b664f65f05e0cff03b68bc1238b2e21e",
        "protocol": "morpho",
        "collateral": "sUSDS",
        "borrow": "USDT",
    },
    "W-3": {
        "address": "0xcb1effb6f6e531137ccc1508a8d4982e873aee58",
        "protocol": "morpho",
        "collateral": "sUSDS",
        "borrow": "USDT",
    },
    "W-4": {
        "address": "0x0d4f7b204626e8233c5b42b1269a78e236e9a06b",
        "protocol": "morpho",
        "collateral": "sUSDe",
        "borrow": "PYUSD",
    },
    "W-5": {
        "address": "0x24385a793f725328d7f6224430e48b4236326717",
        "protocol": "morpho",
        "collateral": "syrupUSDC",
        "borrow": "PYUSD",
    },
    "W-6": {
        "address": "0xfafc2c5f6a0d05718f3e50d0765a79fc69cdde13",
        "protocol": "morpho",
        "collateral": "sUSDS",
        "borrow": "USDT",
    },
    "W-7": {
        "address": "0x32f07401eb177f2c0fc4f95f3928050d88dae7ed",
        "protocol": "morpho",
        "collateral": "sUSDe",
        "borrow": "PYUSD",
    },
    "W-8": {
        "address": "0x218b5b98805ad5193432999406e17bceb51770aa",
        "protocol": "morpho",
        "collateral": "sUSDe",
        "borrow": "DAI",
    },
    "W-9": {
        "address": "0x309e161a7056610f0af12c608b3a31f0ffbb146c",
        "protocol": "morpho",
        "collateral": "sUSDe",
        "borrow": "DAI",
    },
    "W-10": {
        "address": "0x3363aca0a6bd542d146408246b5d1e3743b977d6",
        "protocol": "morpho",
        "collateral": "sUSDe",
        "borrow": "DAI",
    },
    "W-11": {
        "address": "0xb48ac9c5585e5f3c88c63cf9bcbaedc921f76df2",
        "protocol": "morpho",
        "collateral": "sUSDe",
        "borrow": "DAI",
    },
    "W-12": {
        "address": "0x9bcb2ee24bd11046c0dcdfebd608eeb360a64495",
        "protocol": "morpho",
        "collateral": "sUSDS",
        "borrow": "USDT",
    },
    "W-13": {
        "address": "0x206777f4396817398ee61e7ac5e62af311e79836",
        "protocol": "morpho",
        "collateral": "sUSDS",
        "borrow": "USDT",
    },
    "W-14": {
        "address": "0xc05855cbe2a68f9a28a4d85a3a497ebe3adc9a1c",
        "protocol": "morpho",
        "collateral": "sUSDS",
        "borrow": "USDT",
    },
    "W-15": {
        "address": "0x59b6c75eeb7dfe417505919c3e5a919b7c1b0773",
        "protocol": "morpho",
        "collateral": "syrupUSDC",
        "borrow": "USDC",
    },
    "W-16": {
        "address": "0xf28dc8b6ded7e45f8cf84b9972487c8e1857a442",
        "protocol": "morpho",
        "collateral": "syrupUSDC",
        "borrow": "USDC",
    },
}

DUNE_FILES = {
    "W-1": "data/morpho/from_dune/morpho_w1_events.csv",
    "W-2": "data/morpho/from_dune/morpho_w2_events.csv",
    "W-3": "data/morpho/from_dune/morpho_w3_events.csv",
    "W-4": "data/morpho/from_dune/morpho_w4_events.csv",
    "W-5": "data/morpho/from_dune/morpho_w5_events.csv",
    "W-6": "data/morpho/from_dune/morpho_w6_events.csv",
    "W-7": "data/morpho/from_dune/morpho_w7_events.csv",
    "W-8": "data/morpho/from_dune/morpho_w8_events.csv",
    "W-9": "data/morpho/from_dune/morpho_w9_events.csv",
    "W-10": "data/morpho/from_dune/morpho_w10_events.csv",
    "W-11": "data/morpho/from_dune/morpho_w11_events.csv",
    "W-12": "data/morpho/from_dune/morpho_w12_events.csv",
    "W-13": "data/morpho/from_dune/morpho_w13_events.csv",
    "W-14": "data/morpho/from_dune/morpho_w14_events.csv",
    "W-15": "data/morpho/from_dune/morpho_w15_events.csv",
    "W-16": "data/morpho/from_dune/morpho_w16_events.csv",
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
    os.makedirs("data", exist_ok=True)
    all_events = []

    for whale_id, meta in WHALES.items():
        print(f"Processing {whale_id} ({meta['protocol']}, {meta['address'][:10]}...)...")
        events = load_from_dune(whale_id, meta)
        print(f"  {len(events)} events")
        all_events.extend(events)

    all_events.sort(key=lambda r: (r["whale_id"], str(r["timestamp"])))

    output_path = "data/morpho/panel_raw_events.csv"
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

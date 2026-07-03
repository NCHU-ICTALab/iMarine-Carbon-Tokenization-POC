import json
import os
import argparse
import pandas as pd
from web3 import Web3

from data.sources.csv_source import CsvSource
from data.gfi import TARGET_GFI, surplus_tonnes
from data.validate import validate_issuance

OFFCHAIN_DIR = "data/out/offchain"


def canonical(obj: dict) -> str:
    """標準化 JSON（排序鍵、無空白），確保鏈上鏈下算出同一個 hash。"""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def build_single(record: dict, seen: set | None = None) -> dict:
    """單筆核發請求：算超額 → 組鏈下明細 → keccak → 驗證 → 寫鏈下檔 → 回傳標準鑄造請求。

    record 欄位同 fleet.csv 一列：ship_id / reporting_period / attained_gfi / energy_mj / fuel。
    缺額（噸數 <= 0）或驗證不過 raise ValueError（訊息即錯誤原因）；驗證全過才寫鏈下檔。
    """
    tonnes = surplus_tonnes(record["attained_gfi"], TARGET_GFI, record["energy_mj"])

    offchain = {
        "ship_id": record["ship_id"],
        "reporting_period": record["reporting_period"],
        "calculation_basis": {
            "attained_gfi": record["attained_gfi"],
            "target_gfi": TARGET_GFI,
            "energy_mj": int(record["energy_mj"]),
            "fuel": record["fuel"],
        },
        "verification_body": "CR",
    }
    canon = canonical(offchain)
    data_hash = Web3.keccak(text=canon).hex()

    fname = f"{record['ship_id']}_{record['reporting_period']}.json"
    req = {
        "ship_id": record["ship_id"],
        "reporting_period": record["reporting_period"],
        "amount_tonnes": int(round(tonnes)),
        "uri": f"local://offchain/{fname}",
        "data_hash": data_hash,
        "calculation_basis": offchain["calculation_basis"],
        "to_role": "shipping",
    }
    errs = validate_issuance(req, seen if seen is not None else set())
    if errs:
        raise ValueError("；".join(errs))
    # 驗證通過才寫鏈下明細檔，避免留孤兒檔（正式版改放 IPFS，見 v2 規劃 5.2）
    os.makedirs(OFFCHAIN_DIR, exist_ok=True)
    with open(os.path.join(OFFCHAIN_DIR, fname), "w", encoding="utf-8") as f:
        f.write(canon)
    return req


def build(csv_path: str, out_path: str):
    os.makedirs(OFFCHAIN_DIR, exist_ok=True)
    records = CsvSource(csv_path).fetch()

    # 用 pandas 依「船 × 申報期」彙整（示範批次處理；此處一筆一期，可依需求改成整年加總）
    df = pd.DataFrame([r.to_dict() for r in records])

    requests, seen, skipped = [], set(), 0
    for _, row in df.iterrows():
        # 缺額或剛好達標：靜默跳過（維持原輸出——缺額不逐筆印，只有驗證錯誤才印）
        if surplus_tonnes(row["attained_gfi"], TARGET_GFI, row["energy_mj"]) <= 0:
            skipped += 1
            continue
        rec = {
            "ship_id": row["ship_id"],
            "reporting_period": row["reporting_period"],
            "attained_gfi": row["attained_gfi"],
            "energy_mj": int(row["energy_mj"]),
            "fuel": row["fuel"],
        }
        try:
            req = build_single(rec, seen)
        except ValueError as e:
            print(f"  ✗ 跳過 {rec['ship_id']} {rec['reporting_period']}：{e}")
            skipped += 1
            continue
        seen.add((req["ship_id"], req["reporting_period"]))
        requests.append(req)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(requests, f, ensure_ascii=False, indent=2)

    total = sum(r["amount_tonnes"] for r in requests)
    print(f"產出核發請求 {len(requests)} 筆、合計 {total} 噸（跳過 {skipped} 筆）→ {out_path}")
    print(f"注意：TARGET_GFI={TARGET_GFI} 為示意值，正式版須依 IMO 最終基準校準")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="data/out/fleet.csv")
    ap.add_argument("--out", default="data/out/minting_requests.json")
    a = ap.parse_args()
    build(a.csv, a.out)

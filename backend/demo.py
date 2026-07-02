from . import ledger, service


def main():
    ledger.init_db()
    print("① 依核發請求批次發行 SU…")
    res = service.issue_from_requests("data/out/minting_requests.json")
    print(f"   發行 {res['count']} 筆、合計 {res['total_tonnes']} 噸")

    print("② 航商 A 把第 0 號 SU 以 300 mUSD 上架…")
    service.list_su(0, 300)

    print("③ 產業買方買下第 0 號…")
    service.buy_su(0)

    print("④ 買方除役第 0 號、抵 Scope 3（purpose=3）…")
    service.retire_su(0, 3)

    print("\n=== 本地帳本（前 10 筆）===")
    sus = ledger.all_su(service.client)
    for s in sus[:10]:
        print(f"  SU#{s['token_id']} ship={s['ship_id']} amount={s['amount']}t "
              f"owner={s['owner_role']} status={s['status']} purpose={s['purpose_name']}")
    print(f"  …共 {len(sus)} 筆、合計 {sum(s['amount'] for s in sus)} 噸")


if __name__ == "__main__":
    main()

import re


def validate_issuance(rec: dict, seen: set) -> list[str]:
    """回傳錯誤清單；空清單代表通過。rec 是準備發行的一筆核發請求。"""
    errors = []
    if rec["amount_tonnes"] <= 0:
        errors.append("超額噸數必須 > 0")
    key = (rec["ship_id"], rec["reporting_period"])
    if key in seen:
        errors.append(f"重複發行：{key} 已發過")
    if not rec.get("calculation_basis"):
        errors.append("缺 calculation_basis（無法回溯計算依據）")
    # 收緊為 IMO+純數字：與後端 int(ship_id.replace("IMO","")) 的解析對齊
    if not re.fullmatch(r"IMO\d+", str(rec["ship_id"])):
        errors.append("ship_id 格式異常（應為 IMO+純數字）")
    return errors

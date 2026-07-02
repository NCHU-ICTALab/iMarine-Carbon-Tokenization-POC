# NZF 目標 GFI（gCO2e/MJ）— 佔位值，正式上線須依 IMO 最終指引校準（見 v2 規劃 5.1）
TARGET_GFI = 89.0


def surplus_tonnes(attained_gfi: float, target_gfi: float, energy_mj: float) -> float:
    """超額減碳噸數 = (目標 - 實際) × 能量 ÷ 1e6（g → tonne）。未超額則為 0。"""
    if attained_gfi >= target_gfi:
        return 0.0
    reduction_g = (target_gfi - attained_gfi) * energy_mj  # gCO2e
    return reduction_g / 1_000_000.0

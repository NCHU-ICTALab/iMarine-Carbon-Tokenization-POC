from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict


@dataclass
class ShipEnergyRecord:
    """一艘船、一個申報期的能耗與碳強度（資料層的統一輸入格式）。"""
    ship_id: str          # IMO Number
    reporting_period: str # 例 "2028" 或 "2028-Q1"
    attained_gfi: float   # 實際 GFI，gCO2e/MJ（well-to-wake）
    energy_mj: float      # 該期總能量使用（MJ）
    fuel: str             # 主要燃料

    def to_dict(self):
        return asdict(self)


class DataSource(ABC):
    """所有資料來源的共同介面。換資料源＝實作一個新的子類別。"""

    @abstractmethod
    def fetch(self) -> list[ShipEnergyRecord]:
        ...

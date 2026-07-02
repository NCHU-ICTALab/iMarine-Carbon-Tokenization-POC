import csv
from .base import DataSource, ShipEnergyRecord


class CsvSource(DataSource):
    """從 CSV 讀資料。欄位：ship_id, reporting_period, attained_gfi, energy_mj, fuel"""

    def __init__(self, path: str):
        self.path = path

    def fetch(self) -> list[ShipEnergyRecord]:
        rows = []
        with open(self.path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                rows.append(ShipEnergyRecord(
                    ship_id=r["ship_id"].strip(),
                    reporting_period=r["reporting_period"].strip(),
                    attained_gfi=float(r["attained_gfi"]),
                    energy_mj=float(r["energy_mj"]),
                    fuel=r["fuel"].strip(),
                ))
        return rows

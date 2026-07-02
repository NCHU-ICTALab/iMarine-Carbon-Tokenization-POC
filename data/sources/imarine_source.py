from .base import DataSource, ShipEnergyRecord


class IMarineSource(DataSource):
    """未來：直接串 iMarine 替代能源專區的 API / 匯出檔。
    只要實作 fetch() 回傳 list[ShipEnergyRecord]，下游（gfi/validate/build_requests）完全不用改。
    """

    def __init__(self, api_base: str, token: str | None = None):
        self.api_base = api_base
        self.token = token

    def fetch(self) -> list[ShipEnergyRecord]:
        raise NotImplementedError(
            "接 iMarine 時實作：打 API → 對映欄位 → 回傳 ShipEnergyRecord 清單"
        )

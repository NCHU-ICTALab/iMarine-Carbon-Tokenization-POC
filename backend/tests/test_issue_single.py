"""單筆發行測試。
上半：資料層 build_single 純函式單元測試（不需鏈，恆執行）。
下半（Task 2 追加）：service.issue_single 整合測試（需本地鏈 + make deploy，鏈不在就 skip）。
測試把鏈下目錄導到 tmp，不污染 data/out/offchain。"""
import json
import os

import pytest
from web3 import Web3

RPC_URL = os.getenv("RPC_URL", "http://127.0.0.1:8545")
NETWORK = os.getenv("NETWORK", "localhost")
_SHARED = os.path.join(os.path.dirname(__file__), "..", "..", "shared", f"contracts.{NETWORK}.json")


def _chain_ready() -> bool:
    if not os.path.exists(_SHARED):
        return False
    try:
        return Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={"timeout": 2})).is_connected()
    except Exception:
        return False


# ── 資料層 build_single 單元測試（不需鏈） ──────────────────────

@pytest.fixture()
def offdir(tmp_path, monkeypatch):
    """鏈下檔目錄導到 tmp，避免污染 data/out/offchain。"""
    import data.build_requests as br
    d = tmp_path / "offchain"
    monkeypatch.setattr(br, "OFFCHAIN_DIR", str(d))
    return d


def _rec(**kw):
    base = {"ship_id": "IMO9990101", "reporting_period": "2029-01",
            "attained_gfi": 55.0, "energy_mj": 100_000_000, "fuel": "LNG"}
    base.update(kw)
    return base


def test_build_single_happy(offdir):
    from data.build_requests import build_single
    req = build_single(_rec())
    assert req["amount_tonnes"] > 0
    assert req["to_role"] == "shipping"
    assert req["uri"] == "local://offchain/IMO9990101_2029-01.json"
    # 鏈下檔已寫，且 keccak(檔案內容) == data_hash（verify 的核心不變量）
    text = (offdir / "IMO9990101_2029-01.json").read_text(encoding="utf-8")
    assert "0x" + Web3.keccak(text=text).hex().removeprefix("0x") == \
           "0x" + req["data_hash"].removeprefix("0x")
    assert json.loads(text)["calculation_basis"]["attained_gfi"] == 55.0


def test_build_single_deficit_raises_and_writes_nothing(offdir):
    from data.build_requests import build_single
    with pytest.raises(ValueError, match="超額噸數"):
        build_single(_rec(attained_gfi=95.0))    # 高於 TARGET_GFI=89.0 → 缺額
    assert not offdir.exists() or not list(offdir.iterdir())


def test_build_single_bad_period_raises(offdir):
    from data.build_requests import build_single
    with pytest.raises(ValueError, match="reporting_period"):
        build_single(_rec(reporting_period="2029/01"))


def test_build_single_seen_duplicate_raises(offdir):
    from data.build_requests import build_single
    with pytest.raises(ValueError, match="重複發行"):
        build_single(_rec(), seen={("IMO9990101", "2029-01")})


# ── service.issue_single 整合測試（需本地鏈 + make deploy） ──────

needs_chain = pytest.mark.skipif(not _chain_ready(), reason="需要本地鏈 + make deploy（HANDOFF §7 步驟 1）")


@pytest.fixture()
def svc(tmp_path, monkeypatch):
    """隔離：測試 DB + 鏈下目錄（build_requests 與 service 兩處）都導到 tmp。"""
    from backend import config
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "test_ledger.db"))
    from backend import ledger, service
    import data.build_requests as br
    d = str(tmp_path / "offchain")
    monkeypatch.setattr(br, "OFFCHAIN_DIR", d)
    monkeypatch.setattr(service, "OFFCHAIN_DIR", d)
    ledger.init_db()
    return service


@needs_chain
def test_issue_single_happy_then_verify(svc):
    from backend import ledger
    res = svc.issue_single("IMO9990201", "2029-02", 55.0, 100_000_000, "LNG")
    assert res["token_id"] is not None
    assert res["amount_tonnes"] > 0
    assert res["tx"]
    row = next(s for s in ledger.all_su(svc.client) if s["token_id"] == res["token_id"])
    assert row["status"] == "held" and row["owner_role"] == "shipping"
    v = svc.verify_su(res["token_id"])
    assert v["match"] is True                     # 新 SU 的防竄改回驗完整可用


@needs_chain
def test_issue_single_duplicate_rejected(svc):
    svc.issue_single("IMO9990202", "2029-03", 55.0, 100_000_000, "LNG")
    with pytest.raises(ValueError, match="已發行過"):
        svc.issue_single("IMO9990202", "2029-03", 55.0, 100_000_000, "LNG")


@needs_chain
def test_issue_single_deficit_rejected_no_orphan(svc, tmp_path):
    with pytest.raises(ValueError, match="超額噸數"):
        svc.issue_single("IMO9990203", "2029-04", 95.0, 100_000_000, "VLSFO")
    assert not os.path.exists(os.path.join(str(tmp_path / "offchain"), "IMO9990203_2029-04.json"))


@needs_chain
def test_issue_single_bad_format_rejected(svc):
    with pytest.raises(ValueError, match="ship_id"):
        svc.issue_single("SHIP01", "2029-05", 55.0, 100_000_000, "LNG")
    with pytest.raises(ValueError, match="reporting_period"):
        svc.issue_single("IMO9990204", "202905", 55.0, 100_000_000, "LNG")


@needs_chain
def test_issue_single_mint_failure_cleans_offchain(svc, tmp_path, monkeypatch):
    """鑄造失敗補償：剛寫的鏈下檔要被清掉，重試不被重複防呆誤擋。"""
    from backend.chain_client import ChainTxError

    def boom(*a, **k):
        raise ChainTxError("simulated mint failure")

    monkeypatch.setattr(svc.client, "mint", boom)
    with pytest.raises(ChainTxError):
        svc.issue_single("IMO9990205", "2029-06", 55.0, 100_000_000, "LNG")
    assert not os.path.exists(os.path.join(str(tmp_path / "offchain"), "IMO9990205_2029-06.json"))

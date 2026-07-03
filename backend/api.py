from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from . import ledger, service
from .chain_client import ChainTxError

app = FastAPI(title="TCX SU PoC API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
ledger.init_db()


# 鏈上 revert（含 reason）→ 400；其他例外走 FastAPI 預設 500
@app.exception_handler(ChainTxError)
def chain_tx_error(request: Request, exc: ChainTxError):
    return JSONResponse(status_code=400, content={"error": str(exc)})


# 業務規則拒絕（缺額/重複/格式）→ 400；訊息繁中，UI toast 直接顯示
@app.exception_handler(ValueError)
def value_error(request: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"error": str(exc)})


@app.get("/health")
def health():
    return {"ok": True, "chainId": service.client.chain_id}


@app.get("/state")
def state():
    return {"roles": service.client.roles, "sus": ledger.all_su(service.client)}


@app.get("/events")
def events(limit: int = 50):
    return ledger.recent_events(limit)


@app.get("/verify/{token_id}")
def verify(token_id: int):
    # 防竄改回驗：鏈上 dataHash vs 鏈下明細重算的 keccak（match=True 代表未被竄改）
    return service.verify_su(token_id)


@app.post("/pipeline")
def pipeline():
    res = service.issue_from_requests("data/out/minting_requests.json")
    return {"issued": res["count"], "total_tonnes": res["total_tonnes"]}


class IssueBody(BaseModel):
    ship_id: str
    reporting_period: str
    attained_gfi: float
    energy_mj: int
    fuel: str


@app.post("/issue")
def do_issue(b: IssueBody):
    return service.issue_single(b.ship_id, b.reporting_period,
                                b.attained_gfi, b.energy_mj, b.fuel)


class ListBody(BaseModel):
    token_id: int
    price: int


@app.post("/list")
def do_list(b: ListBody):
    return {"tx": service.list_su(b.token_id, b.price)}


class TokenBody(BaseModel):
    token_id: int


@app.post("/buy")
def do_buy(b: TokenBody):
    return {"tx": service.buy_su(b.token_id)}


class RetireBody(BaseModel):
    token_id: int
    purpose: int = 3   # 預設 SCOPE3_OFFSET


@app.post("/retire")
def do_retire(b: RetireBody):
    return {"tx": service.retire_su(b.token_id, b.purpose)}

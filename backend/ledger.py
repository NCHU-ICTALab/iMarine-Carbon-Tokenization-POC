import sqlite3
import json
from web3.logs import DISCARD
from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS su (
  token_id INTEGER PRIMARY KEY,
  ship_id INTEGER, amount INTEGER, expiry INTEGER,
  owner TEXT, status TEXT, purpose INTEGER, data_hash TEXT
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts DATETIME DEFAULT CURRENT_TIMESTAMP,
  name TEXT, token_id INTEGER, detail TEXT
);
"""

PURPOSE_NAMES = ["NZF_REWARD", "EU_ETS_OFFSET", "PORT_FEE_REBATE", "SCOPE3_OFFSET"]


def _conn():
    c = sqlite3.connect(config.DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _hex0x(v) -> str:
    """bytes/HexBytes/str 統一輸出 0x 前綴 hex（HexBytes 版本間 .hex() 有無前綴不一致）。"""
    h = v if isinstance(v, str) else v.hex()
    return h if h.startswith("0x") else "0x" + h


def init_db():
    with _conn() as c:
        c.executescript(SCHEMA)


def _log(c, name, token_id, detail):
    c.execute("INSERT INTO events(name, token_id, detail) VALUES (?,?,?)",
              (name, token_id, json.dumps(detail, ensure_ascii=False)))


def apply_receipt(su, market, receipt):
    """把一筆交易收據裡的所有已知事件套用到帳本。"""
    with _conn() as c:
        for e in su.events.Issued().process_receipt(receipt, errors=DISCARD):
            a = e["args"]
            c.execute("""INSERT INTO su(token_id, ship_id, amount, expiry, owner, status, data_hash)
                         VALUES (?,?,?,?,?, 'held', ?)
                         ON CONFLICT(token_id) DO UPDATE SET
                           ship_id=excluded.ship_id, amount=excluded.amount,
                           expiry=excluded.expiry, owner=excluded.owner, data_hash=excluded.data_hash,
                           status='held', purpose=NULL""",
                      (a["tokenId"], a["shipId"], a["amount"], a["expiry"], a["to"], _hex0x(a["dataHash"])))
            _log(c, "Issued", a["tokenId"], {"to": a["to"], "amount": a["amount"]})

        for e in market.events.Listed().process_receipt(receipt, errors=DISCARD):
            a = e["args"]
            c.execute("UPDATE su SET status='listed' WHERE token_id=?", (a["tokenId"],))
            _log(c, "Listed", a["tokenId"], {"price": a["price"], "seller": a["seller"]})

        for e in market.events.Unlisted().process_receipt(receipt, errors=DISCARD):
            a = e["args"]
            c.execute("UPDATE su SET status='held' WHERE token_id=?", (a["tokenId"],))
            _log(c, "Unlisted", a["tokenId"], {})

        for e in market.events.Sold().process_receipt(receipt, errors=DISCARD):
            a = e["args"]
            c.execute("UPDATE su SET owner=?, status='held' WHERE token_id=?", (a["buyer"], a["tokenId"]))
            _log(c, "Sold", a["tokenId"], {"buyer": a["buyer"], "price": a["price"]})

        for e in su.events.Retired().process_receipt(receipt, errors=DISCARD):
            a = e["args"]
            c.execute("UPDATE su SET status='retired', purpose=? WHERE token_id=?", (a["purpose"], a["tokenId"]))
            _log(c, "Retired", a["tokenId"], {"purpose": PURPOSE_NAMES[a["purpose"]]})


def all_su(client):
    with _conn() as c:
        rows = c.execute("SELECT * FROM su ORDER BY token_id").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["owner_role"] = client.role_of(d["owner"]) if d["owner"] else None
        d["purpose_name"] = PURPOSE_NAMES[d["purpose"]] if d["purpose"] is not None else None
        out.append(d)
    return out


def recent_events(limit=50):
    with _conn() as c:
        rows = c.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]

from __future__ import annotations
import os
from typing import Optional, Iterable, Dict, Any
from dataclasses import dataclass
import pandas as pd
import yaml
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))  # crypto_backtester/
DB_NAME = os.getenv("DB_NAME", "econ_sim")

# v0.2: 자산군별 테이블 라우팅
BAR_TABLE_BY_MARKET = {
    "crypto": "crypto_bars",
    "equity": "equity_bars",
    "commodity": "commodity_bars",
    "fx": "fx_bars",
}

def resolve_bar_table(market: str) -> str:
    try:
        return BAR_TABLE_BY_MARKET[market]
    except KeyError:
        raise ValueError(f"unknown market={market} (allowed: {list(BAR_TABLE_BY_MARKET.keys())})")

def _expand_env(v: Any) -> Any:
    if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
        return os.getenv(v[2:-1])
    return v

def load_conf() -> dict:
    load_dotenv()  # 레포 루트(.env) 자동 로드
    conf_path = os.path.join(ROOT, "conf", "base.yaml")
    with open(conf_path, "r", encoding="utf-8") as f:
        conf = yaml.safe_load(f)
    db = conf.get("database", {})
    for k in list(db.keys()):
        db[k] = _expand_env(db[k])
    conf["database"] = db
    return conf

def get_engine() -> Engine:
    conf = load_conf()
    db = conf["database"]
    if not db.get("enabled", False):
        raise RuntimeError("Database is disabled in conf/base.yaml")
    dsn = (
        f"mysql+pymysql://{db['user']}:{db['password']}"
        f"@{db['host']}:{db['port']}/{db['name']}?charset=utf8mb4"
    )
    engine = create_engine(
        dsn,
        pool_pre_ping=True,
        connect_args={"connect_timeout": int(db.get("connect_timeout", 10))},
    )
    return engine

def ensure_asset(engine, symbol: str, exchange: str | None = None,
                currency: str | None = None, market: str = "crypto") -> int:
    with engine.begin() as conn:
        row = conn.execute(
            text(f"SELECT asset_id FROM `{DB_NAME}`.asset WHERE symbol=:s"),
            {"s": symbol}
        ).fetchone()
        if row:
            return int(row[0])
        conn.execute(
            text(f"""
                INSERT INTO `{DB_NAME}`.asset (class, symbol, exchange, currency, market)
                VALUES ('spot', :symbol, :exchange, :currency, :market)
            """),
            {"symbol": symbol, "exchange": exchange, "currency": currency, "market": market}
        )
        row = conn.execute(
            text(f"SELECT asset_id FROM `{DB_NAME}`.asset WHERE symbol=:s"),
            {"s": symbol}
        ).fetchone()
        return int(row[0])

def upsert_bars(engine, asset_id: int, res: str, df: pd.DataFrame,
                provider: str | None = None, market: str = "crypto") -> int:
    table = resolve_bar_table(market)
    if df.empty:
        return 0
    out = df.copy()
    records = []
    for ts, row in out.iterrows():
        # 각 row의 인덱스(ts)를 안전하게 UTC로 정규화
        ts = pd.Timestamp(ts)
        if ts.tz is None:
            ts_utc = ts.tz_localize("UTC")
        else:
            ts_utc = ts.tz_convert("UTC")
        records.append({
            "asset_id": asset_id,
            "res": res,
            "ts": ts_utc.to_pydatetime().replace(tzinfo=None),  # MySQL DATETIME(UTC, naive)
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": float(row["volume"]),
        })
    sql = text(f"""
        INSERT INTO `{DB_NAME}`.{table}
          (asset_id, res, ts, open, high, low, close, volume)
        VALUES
          (:asset_id, :res, :ts, :open, :high, :low, :close, :volume)
        ON DUPLICATE KEY UPDATE
          open=VALUES(open), high=VALUES(high), low=VALUES(low),
          close=VALUES(close), volume=VALUES(volume)
    """)
    with engine.begin() as conn:
        conn.execute(sql, records)
    return len(records)

def fetch_bars(engine, asset_id: int, res: str, start: str, end: str, market: str = "crypto") -> pd.DataFrame:
    table = resolve_bar_table(market)
    q = text(f"""
        SELECT ts, open, high, low, close, volume
        FROM `{DB_NAME}`.{table}
        WHERE asset_id=:aid AND res=:res AND ts>=:start AND ts<:end
        ORDER BY ts
    """)
    with engine.begin() as conn:
        rows = conn.execute(q, {"aid": asset_id, "res": res, "start": start, "end": end}).fetchall()
    if not rows:
        return pd.DataFrame(columns=["open","high","low","close","volume"])
    df = pd.DataFrame(rows, columns=["ts","open","high","low","close","volume"])
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    df = df.set_index("ts").sort_index()
    return df

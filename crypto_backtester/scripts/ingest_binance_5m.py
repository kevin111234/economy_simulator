from __future__ import annotations
import argparse, time
from typing import Iterator, Tuple
import requests
import pandas as pd

from crypto_backtester.engine.db_utils import get_engine, ensure_asset, upsert_bars

BINANCE_BASE = "https://api.binance.com"  # Spot
INTERVAL = "5m"
LIMIT = 1000                               # 최대 1000캔들/호출
STEP_MS = 5 * 60 * 1000                    # 5분(ms)

def to_ms(s: str) -> int:
    # 날짜(YYYY-MM-DD) 또는 ISO8601 → ms(UTC)
    ts = pd.to_datetime(s, utc=True)
    return int(ts.value // 1_000_000)

def fetch_klines(symbol: str, start_ms: int, end_ms: int, session: requests.Session, sleep: float = 0.2
                  ) -> Iterator[pd.DataFrame]:
    """
    Binance REST /api/v3/klines 페이징 제너레이터.
    - start_ms <= openTime < end_ms (end exclusive)
    - 한 번에 최대 1000개(≈3.47일)씩 가져오고 커밋
    """
    url = f"{BINANCE_BASE}/api/v3/klines"
    cursor = start_ms
    while cursor < end_ms:
        # 이번 페이지에서 가능한 최대 구간(끝을 살짝 당겨 과다포함 방지)
        page_end = min(end_ms - 1, cursor + LIMIT * STEP_MS - 1)
        params = dict(symbol=symbol.upper(), interval=INTERVAL,
                      startTime=cursor, endTime=page_end, limit=LIMIT)
        r = session.get(url, params=params, timeout=15)
        if r.status_code != 200:
            raise RuntimeError(f"Binance HTTP {r.status_code}: {r.text}")
        data = r.json()
        if not data:
            # 비정상 공백 회피: 다음 바로 전진
            cursor += STEP_MS
            time.sleep(sleep)
            continue
        # klines 포맷 참조: [openTime, open, high, low, close, volume, closeTime, ...]
        df = pd.DataFrame(data, columns=[
            "openTime","open","high","low","close","volume",
            "closeTime","qav","numTrades","tbbav","tbqav","ignore"
        ])
        df["ts"] = pd.to_datetime(df["openTime"], unit="ms", utc=True)
        df = df.set_index("ts")[["open","high","low","close","volume"]].astype(float).sort_index()
        yield df

        last_open = int(data[-1][0])
        # 다음 커서 = 마지막 openTime + 5분
        cursor = last_open + STEP_MS
        time.sleep(sleep)  # 레이트리밋 완충(가벼운 백오프)

def main():
    ap = argparse.ArgumentParser(description="Fetch 5m klines from Binance and upsert into MariaDB bars(res='5m').")
    ap.add_argument("--symbol", default="BTCUSDT", help="e.g., BTCUSDT (Spot)")
    ap.add_argument("--start", required=True, help="UTC start (YYYY-MM-DD or ISO8601)")
    ap.add_argument("--end",   required=True, help="UTC end (exclusive; YYYY-MM-DD or ISO8601)")
    ap.add_argument("--sleep", type=float, default=0.2, help="seconds between requests")
    ap.add_argument("--csv-out", default="", help="(optional) also append to CSV as file-rail")
    args = ap.parse_args()

    start_ms, end_ms = to_ms(args.start), to_ms(args.end)
    if end_ms <= start_ms:
        raise SystemExit("end must be greater than start (end is exclusive)")

    eng = get_engine()
    asset_id = ensure_asset(eng, args.symbol)

    total_rows, pages = 0, 0
    with requests.Session() as sess:
        for df in fetch_klines(args.symbol, start_ms, end_ms, sess, sleep=args.sleep):
            if df.empty:
                continue
            # 멱등 업서트
            n = upsert_bars(eng, asset_id, "5m", df, provider="binance", market="crypto")
            total_rows += n
            pages += 1
            last_ts = df.index[-1].isoformat()
            print(f"[{pages:04d}] upsert rows={n} (cum={total_rows}) last_ts={last_ts}")

            # (선택) 파일 레일: CSV append
            if args.csv_out:
                header = not pd.io.common.file_exists(args.csv_out)
                out_df = df.reset_index().rename(columns={"ts":"ts"})
                out_df.to_csv(args.csv_out, mode="a", index=False, header=header)

    print(f"DONE symbol={args.symbol} rows={total_rows} pages={pages} "
          f"period={pd.to_datetime(args.start, utc=True)}→{pd.to_datetime(args.end, utc=True)} (UTC, end exclusive)")

if __name__ == "__main__":
    main()

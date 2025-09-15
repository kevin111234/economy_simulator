from __future__ import annotations
import argparse
import pandas as pd
from crypto_backtester.engine.db_utils import get_engine, ensure_asset, fetch_bars, upsert_bars

def resample_5m_to_1d(df5: pd.DataFrame) -> pd.DataFrame:
    if df5.empty:
        return df5
    agg = {"open":"first","high":"max","low":"min","close":"last","volume":"sum"}
    # UTC 자정 경계, right-close(우측 포함) 규약
    d1 = df5.resample("1D", label="right", closed="right").agg(agg).dropna()
    return d1

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="BTCUSDT")
    ap.add_argument("--start", required=True, help="UTC start (e.g., 2024-08-31)")
    ap.add_argument("--end",   required=True, help="UTC end (exclusive, e.g., 2025-08-31)")
    args = ap.parse_args()

    eng = get_engine()
    asset_id = ensure_asset(eng, args.symbol)

    df5 = fetch_bars(eng, asset_id, "5m", args.start, args.end, market="crypto")
    if df5.empty:
        print("no 5m data found in range")
        return
    d1 = resample_5m_to_1d(df5)
    n = upsert_bars(eng, asset_id, "1d", d1, provider="resample", market="crypto")
    print(f"upserted {n} rows into bars(res='1d') for {args.symbol} [{args.start}→{args.end})")

if __name__ == "__main__":
    main()

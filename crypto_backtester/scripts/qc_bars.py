from __future__ import annotations
import argparse, sys
import pandas as pd
from crypto_backtester.engine.db_utils import get_engine, ensure_asset, fetch_bars

def expected_count(start: str, end: str, res: str) -> int:
    freq = {"5m":"5min", "1d":"1D"}[res]
    # end exclusive
    return len(pd.date_range(start=pd.to_datetime(start, utc=True),
                             end=pd.to_datetime(end,   utc=True),
                             freq=freq, inclusive="left"))

def qc(df: pd.DataFrame, res: str) -> dict:
    out = {"rows": len(df), "issues": []}
    if df.empty:
        out["issues"].append("EMPTY_DATA")
        return out
    # index & columns
    if not df.index.is_monotonic_increasing:
        out["issues"].append("NON_MONOTONIC_INDEX")
    if not df.index.is_unique:
        out["issues"].append("DUPLICATE_INDEX")
    if set(df.columns) != {"open","high","low","close","volume"}:
        out["issues"].append("BAD_COLUMNS")
    # NaN
    nan_ct = int(df.isna().sum().sum())
    if nan_ct:
        out["issues"].append(f"NAN_VALUES({nan_ct})")
    # OHLC sanity
    bad_hilo = ((df["high"] < df["low"]) | (df["low"] > df["high"])).sum()
    if bad_hilo:
        out["issues"].append(f"BAD_HILO({int(bad_hilo)})")
    bad_open = ((df["open"] > df["high"]) | (df["open"] < df["low"])).sum()
    bad_close = ((df["close"] > df["high"]) | (df["close"] < df["low"])).sum()
    if bad_open:
        out["issues"].append(f"OPEN_OUT_OF_RANGE({int(bad_open)})")
    if bad_close:
        out["issues"].append(f"CLOSE_OUT_OF_RANGE({int(bad_close)})")
    out["pass"] = (len(out["issues"]) == 0)
    return out

def missing_timestamps(df: pd.DataFrame, start: str, end: str, res: str, limit=10):
    if df.empty:
        return []
    freq = {"5m":"5min", "1d":"1D"}[res]
    full = pd.date_range(pd.to_datetime(start, utc=True),
                         pd.to_datetime(end,   utc=True),
                         freq=freq, inclusive="left")
    miss = full.difference(df.index)
    return [t.isoformat() for t in miss[:limit]]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--res", choices=["5m","1d"], required=True)
    ap.add_argument("--market", choices=["crypto","equity","commodity","fx"], default="crypto")
    ap.add_argument("--start", required=True)
    ap.add_argument("--end",   required=True, help="end exclusive")
    args = ap.parse_args()

    eng = get_engine()
    asset_id = ensure_asset(eng, args.symbol)

    df = fetch_bars(eng, asset_id, args.res, args.start, args.end, market=args.market)
    exp = expected_count(args.start, args.end, args.res)
    res_qc = qc(df, args.res)

    print(f"[QC] {args.symbol} {args.res} rows={len(df)} expected={exp}")
    print(f"     issues={res_qc['issues'] or 'NONE'}")
    if len(df) != exp:
        miss = missing_timestamps(df, args.start, args.end, args.res, limit=10)
        print(f"     missing_count={exp - len(df)} examples={miss}")

    sys.exit(0 if res_qc.get("pass", False) and len(df)==exp else 1)

if __name__ == "__main__":
    main()

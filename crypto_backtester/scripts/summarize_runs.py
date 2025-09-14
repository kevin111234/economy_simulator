import argparse, json, os, csv, datetime as dt
from typing import List, Dict

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reports-dir", default="crypto_backtester/reports")
    ap.add_argument("--sort-by", default="sharpe",
                    choices=["sharpe", "pnl", "mdd", "trades", "run_ts"])
    ap.add_argument("--top", type=int, default=1000)
    return ap.parse_args()

def run_id_to_dt(run_id: str) -> dt.datetime:
    # 형태: YYYYMMDD-HHMMSS-xxxxxx
    try:
        date_str, time_str, _ = run_id.split("-")
        return dt.datetime.strptime(date_str + time_str, "%Y%m%d%H%M%S")
    except Exception:
        return dt.datetime.min

def main():
    args = parse_args()
    path = os.path.join(args.reports_dir, "summary.jsonl")
    out_csv = os.path.join(args.reports_dir, "summary.csv")
    rows: List[Dict] = []
    if not os.path.exists(path):
        print(f"[summarize_runs] not found: {path}")
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            rec["run_ts"] = run_id_to_dt(rec.get("run_id",""))
            rows.append(rec)
    if not rows:
        print("[summarize_runs] empty summary.jsonl")
        return
    key = args.sort_by
    reverse = True if key in ("sharpe","pnl","run_ts") else False
    rows.sort(key=lambda r: r.get(key, 0), reverse=reverse)
    rows = rows[: args.top]
    # CSV 저장
    fieldnames = sorted({k for r in rows for k in r.keys()}, key=str)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=fieldnames)
        wr.writeheader()
        for r in rows:
            r = dict(r)
            if isinstance(r.get("run_ts"), dt.datetime):
                r["run_ts"] = r["run_ts"].isoformat()
            wr.writerow(r)
    print(f"[summarize_runs] wrote: {out_csv} (rows={len(rows)})")

if __name__ == "__main__":
    main()

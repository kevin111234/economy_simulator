# crypto_backtester/scripts/make_experiment_report.py
from __future__ import annotations
import argparse, json, csv, shutil
from pathlib import Path
from typing import Dict

def _write(p: Path, s: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8")

def _load_summary(from_dir: Path) -> Dict:
    fp = from_dir / "summary.json"
    if not fp.exists():
        raise SystemExit(f"not found: {fp}")
    return json.loads(fp.read_text(encoding="utf-8"))

def _card_md(s: Dict, notes: str) -> str:
    params = s.get("params", {})
    param_str = ", ".join(f"{k}={v}" for k, v in params.items()) if params else "-"
    return f"""# {s['symbol']} — {s['strategy']} ({s['res']}, {s['start']} ~ {s['end']})

## 요약(한 줄)
- **PnL {s['pnl']:+.4f}**, **Sharpe {s['sharpe']:.2f}**, **MDD {s['mdd']:+.4f}**, **Trades {s['trades']}**

## 세팅
- 비용: fee {int(s['fee_bps'])}bps, slip {int(s['slip_bps'])}bps
- 파라미터: {param_str}

## 메모
- {notes if notes else "-"}
"""

def _report_md(s: Dict, notes: str) -> str:
    return f"""# Report — {s['symbol']}({s['res']}) / {s['strategy']}

## 1) 결과 요약
- **PnL {s['pnl']:+.4f}**, **Sharpe {s['sharpe']:.2f}**, **MDD {s['mdd']:+.4f}**, **Trades {s['trades']}**

## 2) 에쿼티 & 드로다운
![equity](./figures/equity.png)
![dd](./figures/drawdown.png)

## 3) 메모
- {notes if notes else "-"}
"""

def _links_json() -> str:
    return json.dumps({
        "local": {
            "summary": "summary.json",
            "equity_csv": "equity.csv",
            "orders_csv": "orders.csv",
            "equity_png": "figures/equity.png",
            "drawdown_png": "figures/drawdown.png"
        }
    }, ensure_ascii=False, indent=2)

def _params_yaml(s: Dict, notes: str) -> str:
    params = s.get("params", {}) or {}
    lines = [
        f"symbol: {s['symbol']}",
        f"resolution: {s['res']}",
        f"start: \"{s['start']}\"",
        f"end: \"{s['end']}\"",
        "",
        f"strategy: {s['strategy']}",
        "params:",
    ]
    for k, v in params.items():
        lines.append(f"  {k}: {v}")
    lines += [
        "",
        f"start_cash: {int(s.get('start_cash', 10000))}",
        f"fee_bps: {int(s['fee_bps'])}",
        f"slip_bps: {int(s['slip_bps'])}",
        "liquidate_on_end: true",
        "db_logging: false",
        f"notes: \"{notes}\"",
    ]
    return "\n".join(lines) + "\n"

def _append_runs_csv(exp_dir: Path, s: Dict):
    out = exp_dir / "runs.csv"
    hdr = ["run_id","symbol","res","strategy","pnl","sharpe","mdd","trades","fee_bps","slip_bps","start","end"]
    write_header = not out.exists()
    with out.open("a", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=hdr)
        if write_header: wr.writeheader()
        wr.writerow({k: s.get(k) for k in hdr})

def _sync_artifacts(from_dir: Path, run_dir: Path):
    mapping = {
        "summary.json": "summary.json",
        "equity.csv": "equity.csv",
        "orders.csv": "orders.csv",
        "figures/equity.png": "figures/equity.png",
        "figures/drawdown.png": "figures/drawdown.png",
    }
    for src_rel, dst_rel in mapping.items():
        src = from_dir / src_rel
        dst = run_dir / dst_rel
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.resolve() != dst.resolve():
                shutil.copy2(src, dst)

def emit_from_local(from_dir: str, exp_dir: str, notes: str = "", no_params_file: bool = False) -> str:
    """
    runner가 artifact_root에 쓴 산출물(from_dir)을 실험 폴더(exp_dir)/runs/<run_id>/ 로 동기화하고,
    card.md / report.md / links.json / (옵션) params.yaml을 생성한다.
    """
    from_p = Path(from_dir).resolve()
    exp_p = Path(exp_dir).resolve()

    s = _load_summary(from_p)
    run_id = s["run_id"]
    run_dir = exp_p / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # 아티팩트 동기화
    _sync_artifacts(from_p, run_dir)

    # 리포트 파일 생성
    _write(run_dir / "card.md", _card_md(s, notes))
    _write(run_dir / "report.md", _report_md(s, notes))
    _write(run_dir / "links.json", _links_json())
    if not no_params_file:
        _write(run_dir / "params.yaml", _params_yaml(s, notes))

    # 실험 인덱스 누계
    _append_runs_csv(exp_p, s)

    return str(run_dir)

# --- CLI ---
def _parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-dir", required=True, help="runner가 쓴 산출물 디렉터리(= artifact_dir)")
    ap.add_argument("--exp-dir", required=True, help="실험 폴더(experiments/..)")
    ap.add_argument("--notes", type=str, default="")
    ap.add_argument("--no-params-file", action="store_true")
    return ap.parse_args()

def main():
    args = _parse_args()
    out = emit_from_local(args.from_dir, args.exp_dir, args.notes, args.no_params_file)
    print(f"[make_experiment_report] wrote -> {out}")

if __name__ == "__main__":
    main()

from __future__ import annotations
import argparse
from crypto_backtester.engine.db_utils import load_conf
from crypto_backtester.engine.runner import run_backtest

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--resolution", choices=["5m","1d"], required=True)
    ap.add_argument("--start", required=True)
    ap.add_argument("--end",   required=True, help="end exclusive")
    ap.add_argument("--strategy", choices=["sma_cross","sma_macd_atr"], required=True)

    # params (선택적)
    ap.add_argument("--sma-short", type=int, default=20)
    ap.add_argument("--sma-long",  type=int, default=60)
    ap.add_argument("--macd-fast", type=int, default=12)
    ap.add_argument("--macd-slow", type=int, default=26)
    ap.add_argument("--macd-signal", type=int, default=9)
    ap.add_argument("--atr-n", type=int, default=14)
    ap.add_argument("--atr-k", type=float, default=3.0)

    ap.add_argument("--start-cash", type=float, default=10_000.0)
    ap.add_argument("--fee-bps", type=float, default=None, help="override")
    ap.add_argument("--slip-bps", type=float, default=None, help="override")
    ap.add_argument("--no-db", action="store_true", help="DB 로깅 끄기")

    # 자동 리포트 & 로컬 전용
    ap.add_argument("--auto-report", action="store_true", help="실험 폴더 자동 생성")
    ap.add_argument("--exp-dir", type=str, default=None, help="실험 폴더 경로 (권장)")
    ap.add_argument("--local-only", action="store_true", help="실험기록 로컬 전용(= DB 로깅 강제 비활성화)")
    ap.add_argument("--notes", type=str, default="", help="실험 노트(리포트에 삽입)")

    args = ap.parse_args()

    conf = load_conf()
    fee_bps = args.fee_bps if args.fee_bps is not None else conf["fees_bps"]["taker"]
    slip_bps = args.slip_bps if args.slip_bps is not None else conf["slippage_bps"]["crypto"]

    if args.strategy == "sma_cross":
        params = {"short": args.sma_short, "long": args.sma_long}
    else:
        params = {
            "sma_short": args.sma_short, "sma_long": args.sma_long,
            "macd_fast": args.macd_fast, "macd_slow": args.macd_slow, "macd_signal": args.macd_signal,
            "atr_n": args.atr_n, "atr_k": args.atr_k,
        }

    artifact_root = args.exp_dir if args.auto_report and args.exp_dir else None

    res = run_backtest(
        symbol=args.symbol, res=args.resolution, start=args.start, end=args.end,
        strategy_name=args.strategy, strategy_params=params,
        start_cash=args.start_cash, fee_bps=fee_bps, slip_bps=slip_bps,
        db_logging=(not args.no_db) and (not args.local_only),
        artifact_root=artifact_root, save_fig=True
    )

    # 자동 리포트: 실험 폴더에 run 단위 서브폴더 생성/동기화
    if args.auto_report and args.exp_dir:
        from crypto_backtester.scripts.make_experiment_report import emit_from_local
        emit_from_local(
            from_dir=res["artifact_dir"],
            exp_dir=args.exp_dir,
            notes=args.notes,
            no_params_file=False  # params.yaml 생성
        )
        print(f"[auto-report] wrote -> {args.exp_dir}/runs/{res['run_id']}")

if __name__ == "__main__":
    main()

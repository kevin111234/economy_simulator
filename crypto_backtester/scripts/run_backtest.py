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

    run_backtest(
        symbol=args.symbol, res=args.resolution, start=args.start, end=args.end,
        strategy_name=args.strategy, strategy_params=params,
        start_cash=args.start_cash, fee_bps=fee_bps, slip_bps=slip_bps,
        db_logging=(not args.no_db)
    )

if __name__ == "__main__":
    main()

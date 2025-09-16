from __future__ import annotations
import argparse
from crypto_backtester.engine.db_utils import load_conf
from crypto_backtester.engine.runner import run_backtest

def _parse_kv_list(kvs):
    """--param key=val 형태를 딕셔너리로 변환. 숫자/불리언 자동 캐스팅."""
    params = {}
    if not kvs:
        return params
    for kv in kvs:
        if "=" not in kv:
            continue
        k, v = kv.split("=", 1)
        v = v.strip()
        # 타입 캐스팅
        if v.lower() in ("true", "false"):
            v = (v.lower() == "true")
        else:
            try:
                if "." in v:
                    v = float(v)
                else:
                    v = int(v)
            except ValueError:
                pass
        params[k.strip()] = v
    return params

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--resolution", choices=["5m","1d"], required=True)
    ap.add_argument("--start", required=True)
    ap.add_argument("--end",   required=True, help="end exclusive")
    # 전략 지정: (1) 기존 이름 (2) 함수 경로
    ap.add_argument("--strategy", choices=["sma_cross","sma_macd_atr"], help="레거시 이름 기반 전략")
    ap.add_argument("--strategy-func", help="함수 경로: package.module:function (예: crypto_backtester.strategies.sma_align_macd:decide)")
    # 공통 파라미터
    ap.add_argument("--start-cash", type=float, default=10_000.0)
    ap.add_argument("--fee-bps", type=float, default=None, help="override")
    ap.add_argument("--slip-bps", type=float, default=None, help="override")
    ap.add_argument("--artifact-root", default=None, help="experiments/<...> 루트 경로")
    ap.add_argument("--no-liquidate", action="store_true", help="마지막 바 강제 청산 비활성화")
    ap.add_argument("--no-print-trades", action="store_true", help="체결 로그 미출력")
    # 레거시 개별 파라미터도 유지
    ap.add_argument("--sma-short", type=int, default=20)
    ap.add_argument("--sma-long",  type=int, default=60)
    ap.add_argument("--macd-fast", type=int, default=12)
    ap.add_argument("--macd-slow", type=int, default=26)
    ap.add_argument("--macd-signal", type=int, default=9)
    ap.add_argument("--atr-n", type=int, default=14)
    ap.add_argument("--atr-k", type=float, default=3.0)
    # 범용 파라미터(--param key=val 지원)
    ap.add_argument("--param", action="append", help="임의 파라미터 (예: --param tp_pct=0.05 --param sl_pct=-0.1)")

    args = ap.parse_args()
    conf = load_conf()
    fee_bps = args.fee_bps if args.fee_bps is not None else conf["fees_bps"]["taker"]
    slip_bps = args.slip_bps if args.slip_bps is not None else conf["slippage_bps"]["crypto"]

    # 레거시 파라미터 묶기
    legacy_params = {
        "short": args.sma_short, "long": args.sma_long,
        "sma_short": args.sma_short, "sma_long": args.sma_long,
        "macd_fast": args.macd_fast, "macd_slow": args.macd_slow, "macd_signal": args.macd_signal,
        "atr_n": args.atr_n, "atr_k": args.atr_k,
    }
    user_params = _parse_kv_list(args.param)
    strategy_params = {**legacy_params, **user_params}

    res = run_backtest(
        symbol=args.symbol, res=args.resolution, start=args.start, end=args.end,
        start_cash=args.start_cash, fee_bps=fee_bps, slip_bps=slip_bps,
        artifact_root=args.artifact_root,
        liquidate_on_end=(not args.no_liquidate if hasattr(args, "no-liquidate") else True),  # 안전
        print_trades=(not args.no_print_trades),
        strategy=args.strategy,
        strategy_params=strategy_params,
        strategy_func=args.strategy_func
    )

if __name__ == "__main__":
    main()

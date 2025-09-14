from __future__ import annotations
import os, json, math, time, uuid
from typing import Dict, Any, List, Tuple
import pandas as pd
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # 헤드리스 환경 렌더링
import matplotlib.pyplot as plt

from crypto_backtester.engine.db_utils import get_engine, ensure_asset, fetch_bars
try:
    import yaml  # params.yaml 저장용
except Exception:
    yaml = None

# --------- 내부 유틸 ---------
def _gen_run_id() -> str:
    return time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]

def _periods_per_year(res: str) -> int:
    if res == "1d":
        return 365
    if res == "5m":
        return 365 * 24 * 12  # 105,120
    raise ValueError(f"unknown res={res}")

def _metrics(equity: pd.Series, res: str) -> Dict[str, float]:
    eq = equity.dropna()
    ret = eq.pct_change().dropna()
    if ret.empty:
        return {"pnl": 0.0, "sharpe": 0.0, "mdd": 0.0}
    mu, sd = ret.mean(), ret.std()
    ann = _periods_per_year(res)
    sharpe = (mu / sd * math.sqrt(ann)) if sd > 0 else 0.0
    roll_max = eq.cummax()
    dd = eq / roll_max - 1.0
    mdd = float(dd.min()) if len(dd) else 0.0
    pnl = float(eq.iloc[-1] / eq.iloc[0] - 1.0)
    return {"pnl": pnl, "sharpe": float(sharpe), "mdd": float(mdd)}

def _one_line(run_id: str, symbol: str, res: str, strategy: str,
              pnl: float, sharpe: float, mdd: float, trades: int,
              fee_bps: float, slip_bps: float, start: str, end: str) -> str:
    def pct(x): return f"{x*100:+.1f}%"
    return (f"[run_id={run_id}] {symbol} {res} {strategy} "
            f"PnL={pct(pnl)} Sharpe={sharpe:.2f} MDD={pct(mdd)} Trades={trades} "
            f"Fee={int(fee_bps)}bps Slip={int(slip_bps)}bps Period={start}→{end}")

# --------- 공개 API ---------
def run_backtest(
    symbol: str, res: str, start: str, end: str,
    strategy_name: str, strategy_params: Dict[str, Any],
    start_cash: float, fee_bps: float, slip_bps: float,
    liquidate_on_end: bool = True, db_logging: bool = True,
    artifact_root: str | None = None,   # 실험 산출물 루트(exp-dir). None이면 experiments/<ES_EXP_NAME>/runs/<run_id> 사용
    save_fig: bool = True
) -> Dict[str, Any]:
    """
    실행 결과 산출물 저장 정책(통일):
      - artifact_root 지정: <artifact_root>/runs/<run_id>/
      - artifact_root 미지정: crypto_backtester/experiments/<ES_EXP_NAME 또는 UNNAMED-EXP>/runs/<run_id>/
      - 저장물: equity.csv, orders.csv, summary.json, params.yaml, figures/{equity.png, drawdown.png}
    """
    # 데이터 로드
    eng = get_engine()
    aid = ensure_asset(eng, symbol, market="crypto")
    df = fetch_bars(eng, aid, res, start, end, market="crypto")
    if df.empty:
        raise RuntimeError("no data")

    # 전략 로드
    if strategy_name == "sma_cross":
        from crypto_backtester.strategies.sma_cross import generate_signals
        params = {"short": strategy_params.get("short", 20),
                  "long":  strategy_params.get("long", 60)}
    elif strategy_name == "sma_macd_atr":
        from crypto_backtester.strategies.sma_macd_atr import generate_signals
        params = {
            "sma_short": strategy_params.get("sma_short", 20),
            "sma_long":  strategy_params.get("sma_long", 60),
            "macd_fast": strategy_params.get("macd_fast", 12),
            "macd_slow": strategy_params.get("macd_slow", 26),
            "macd_signal": strategy_params.get("macd_signal", 9),
            "atr_n":     strategy_params.get("atr_n", 14),
            "atr_k":     strategy_params.get("atr_k", 3.0),
        }
    else:
        raise ValueError(f"unknown strategy={strategy_name}")

    sig = generate_signals(df, **params).reindex(df.index).fillna(0).astype(int)

    # 실행 엔진 (on-close, long-only, all-in)
    slip = slip_bps / 10_000.0
    fee  = fee_bps  / 10_000.0

    cash = start_cash
    qty = 0.0
    equity_pairs: List[tuple[datetime, float]] = []
    orders: List[Dict[str, Any]] = []
    prev_sig = 0

    for ts, row in df.iterrows():
        price = float(row["close"])
        s = int(sig.loc[ts])

        # 포지션 전환
        if prev_sig == 0 and s == 1:
            # BUY (시장가, 슬리피지+수수료)
            buy_px = price * (1.0 + slip)
            qty = cash / buy_px if buy_px > 0 else 0.0
            notional = qty * buy_px
            fee_amt = notional * fee
            cash = cash - fee_amt - notional  # notional은 자산으로 전환
            orders.append({
                "run_id": "",  # 나중에 채움
                "ts": ts.to_pydatetime().replace(tzinfo=None),
                "side": "BUY", "symbol": symbol, "res": res,
                "qty": qty, "price": buy_px, "fee_bps": fee_bps, "slippage_bps": slip_bps
            })
        elif prev_sig == 1 and s == 0:
            # SELL
            sell_px = price * (1.0 - slip)
            notional = qty * sell_px
            fee_amt = notional * fee
            cash = cash + notional - fee_amt
            orders.append({
                "run_id": "",
                "ts": ts.to_pydatetime().replace(tzinfo=None),
                "side": "SELL", "symbol": symbol, "res": res,
                "qty": qty, "price": sell_px, "fee_bps": fee_bps, "slippage_bps": slip_bps
            })
            qty = 0.0

        prev_sig = s
        # 마크투마켓
        equity_pairs.append((ts.to_pydatetime(), cash + qty * price))

    # 종료 청산
    last_ts = df.index[-1]
    if liquidate_on_end and qty > 0:
        price = float(df.loc[last_ts, "close"])
        sell_px = price * (1.0 - slip)
        notional = qty * sell_px
        fee_amt = notional * fee
        cash = cash + notional - fee_amt
        orders.append({
            "run_id": "",
            "ts": last_ts.to_pydatetime().replace(tzinfo=None),
            "side": "SELL", "symbol": symbol, "res": res,
            "qty": qty, "price": sell_px, "fee_bps": fee_bps, "slippage_bps": slip_bps
        })
        qty = 0.0
        if equity_pairs:
            equity_pairs[-1] = (last_ts.to_pydatetime(), cash)  # 마지막 시점 에쿼티 갱신

    equity_df = pd.Series({ts: val for ts, val in equity_pairs}, name="equity").sort_index()
    m = _metrics(equity_df, res)
    trades = sum(1 for o in orders if o["side"] == "SELL")  # '완결된 거래'로 카운트

    # run_id, 요약/로그 저장
    run_id = _gen_run_id()
    start_s, end_s = pd.to_datetime(start).date().isoformat(), pd.to_datetime(end).date().isoformat()
    line = _one_line(run_id, symbol, res, strategy_name, m["pnl"], m["sharpe"], m["mdd"], trades,
                     fee_bps, slip_bps, start_s, end_s)
    print(line)

    # --- 산출물 저장 위치 결정(항상 experiments 계층) ---
    if artifact_root is None:
        exp_name = os.environ.get("ES_EXP_NAME", "UNNAMED-EXP")
        base = Path(__file__).resolve().parents[1] / "experiments" / exp_name
    else:
        base = Path(artifact_root).resolve()
    run_dir = base / "runs" / run_id
    fig_dir = run_dir / "figures"
    run_dir.mkdir(parents=True, exist_ok=True)
    fig_dir.mkdir(parents=True, exist_ok=True)
    equity_path = str(run_dir / "equity.csv")
    orders_path = str(run_dir / "orders.csv")

    # CSV 저장
    equity_df.to_csv(equity_path, header=True)
    for o in orders: o["run_id"] = run_id
    pd.DataFrame(orders).to_csv(orders_path, index=False)

    # summary 저장
    summary_obj = {
        "run_id": run_id, "symbol": symbol, "res": res, "strategy": strategy_name,
        "pnl": float(m["pnl"]), "sharpe": float(m["sharpe"]), "mdd": float(m["mdd"]), "trades": int(trades),
        "fee_bps": float(fee_bps), "slip_bps": float(slip_bps), "start": start_s, "end": end_s,
        "start_cash": float(start_cash),
        "params": strategy_params
    }
    with open(str(run_dir / "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary_obj, f, ensure_ascii=False, indent=2)

    # params.yaml 저장(없으면 params.json으로 폴백)
    params_payload = {
        "symbol": symbol, "resolution": res, "start": start_s, "end": end_s,
        "strategy": strategy_name, "start_cash": float(start_cash),
        "fee_bps": float(fee_bps), "slip_bps": float(slip_bps),
        "params": strategy_params,
    }
    if yaml is not None:
        with open(str(run_dir / "params.yaml"), "w", encoding="utf-8") as f:
            yaml.safe_dump(params_payload, f, allow_unicode=True, sort_keys=False)
    else:
        with open(str(run_dir / "params.json"), "w", encoding="utf-8") as f:
            json.dump(params_payload, f, ensure_ascii=False, indent=2)

    # 그림 저장
    if save_fig:
        # equity
        plt.figure(figsize=(10, 4))
        equity_df.plot(ax=plt.gca())
        plt.title(f"Equity — {symbol} {res} {strategy_name}")
        plt.tight_layout()
        if artifact_root:
            plt.savefig(str(fig_dir / "equity.png"))
        else:
            plt.savefig(str(fig_dir / f"{run_id}_equity.png"))
        plt.close()

        # drawdown
        dd = equity_df / equity_df.cummax() - 1.0
        plt.figure(figsize=(10, 3))
        dd.plot(ax=plt.gca())
        plt.title("Drawdown")
        plt.tight_layout()
        if artifact_root:
            plt.savefig(str(fig_dir / "drawdown.png"))
        else:
            plt.savefig(str(fig_dir / f"{run_id}_drawdown.png"))
        plt.close()

    return {
        "run_id": run_id,
        "artifact_dir": str(run_dir),
        "equity_path": equity_path,
        "orders_path": orders_path,
        "summary": summary_obj
    }

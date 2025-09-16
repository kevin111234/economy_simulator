from __future__ import annotations
import json, math, time, uuid, importlib
from typing import Dict, Any, List, Tuple, Optional, Callable
import pandas as pd
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # 헤드리스 환경 렌더링
import matplotlib.pyplot as plt

from crypto_backtester.engine.db_utils import get_engine, ensure_asset, fetch_bars, load_conf
from crypto_backtester.engine.indicators import sma, ema, macd, atr, rsi


# -------------------------
# 내부 유틸
# -------------------------
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

def _import_func(path: str) -> Callable:
    """
    'package.module:function' 형태의 경로에서 함수를 import.
    예: 'crypto_backtester.strategies.sma_align_macd:decide'
    """
    if ":" not in path:
        raise ValueError("strategy_func 경로 형식은 'module.path:func' 이어야 합니다.")
    mod_path, fn_name = path.split(":", 1)
    mod = importlib.import_module(mod_path)
    fn = getattr(mod, fn_name)
    if not callable(fn):
        raise TypeError(f"{path} 은(는) callable 이 아닙니다.")
    return fn


# -------------------------
# 핵심: 블라인드 의사결정 & 체결 엔진
# -------------------------
def run_backtest(
    symbol: str,
    res: str,
    start: str,
    end: str,
    start_cash: float,
    fee_bps: float,
    slip_bps: float,
    artifact_root: Optional[str] = None,
    liquidate_on_end: bool = True,
    print_trades: bool = True,
    # 전략 선택(둘 중 하나를 사용):
    strategy: Optional[str] = None,             # 레거시 이름 기반 (sma_cross, sma_macd_atr)
    strategy_params: Optional[Dict[str, Any]] = None,
    strategy_func: Optional[str] = None,        # 신규: 'module.path:func' 함수형 전략
) -> Dict[str, Any]:
    """
    미래를 블라인드하여 t 시점까지의 정보만 전략에 제공하고,
    의사결정은 t 종가 기준 → 체결은 t+1 시가(시장가+슬리피지/수수료)로 수행.

    전략 함수 시그니처(권장):
        decide(past_df: pd.DataFrame, ctx: Dict, state: Dict, params: Dict) -> (signal, weight) | {'signal':..., 'weight':...}
        - signal: 'buy' | 'sell' | 'hold'
        - weight: 0.0 ~ 1.0 (목표 보유비중; hold일 땐 None 가능)

    제공 컨텍스트(ctx):
        {
          'now': Timestamp,               # 의사결정 기준 시각 (t)
          'position_qty': float,
          'position_avg_price': float|None,
          'cash': float,
          'equity': float,               # t 종가 기준
          'last_price': float,           # t 종가
          'last_fill_ts': Timestamp|None,
          'last_fill_price': float|None,
        }
    """
    strategy_params = strategy_params or {}

    # 1) 데이터 로드
    eng = get_engine()
    aid = ensure_asset(eng, symbol, market="crypto")  # v0.2: crypto_bars 라우팅
    raw = fetch_bars(eng, aid, res, start, end)
    if raw.empty:
        raise RuntimeError("no data")
    df = raw.copy()

    # 2) 공통 피처(전략에 풍부한 정보 제공; 미래 블라인드 방지 위해 슬라이스로 전달)
    #    필요 시 전략 함수에서 추가 지표를 계산해도 무방.
    df["sma_20"]  = sma(df["close"], 20)
    df["sma_60"]  = sma(df["close"], 60)
    df["sma_120"] = sma(df["close"], 120)
    macd_line, macd_sig, macd_hist = macd(df["close"], 12, 26, 9)
    df["macd_line"] = macd_line
    df["macd_signal"] = macd_sig
    df["macd_hist"] = macd_hist
    # indicators.atr(df, n)는 high/low/close 컬럼을 가진 전체 DataFrame을 받습니다.
    df["atr_14"] = atr(df, 14)
    df["rsi_14"] = rsi(df["close"], 14)

    # 3) 전략 함수 결정
    decide_fn: Optional[Callable] = None
    strat_name_for_log = ""
    if strategy_func:
        decide_fn = _import_func(strategy_func)
        strat_name_for_log = strategy_func
    else:
        raise ValueError("strategy function을 지정해야 합니다.")

    # 4) 실행 엔진 (t에서 의사결정 → t+1 체결)
    slip = slip_bps / 10_000.0
    fee  = fee_bps  / 10_000.0

    cash = float(start_cash)
    qty: float = 0.0
    avg_price: Optional[float] = None

    equity_pairs: List[Tuple[datetime, float]] = []
    orders: List[Dict[str, Any]] = []
    last_fill_ts: Optional[pd.Timestamp] = None
    last_fill_price: Optional[float] = None
    trades: int = 0

    index = df.index.to_list()
    # 마지막 바 직전까지 의사결정 (t+1 체결을 위해 끝-1 까지만)
    for i in range(0, len(index) - 1):
        t = index[i]
        t1 = index[i + 1]  # 체결 시각
        past = df.loc[:t]  # 미래 블라인드: t 시점까지 전달
        last_close = float(past.iloc[-1]["close"])
        equity_t = cash + qty * last_close

        # 컨텍스트 구성
        ctx = {
            "now": t,
            "position_qty": qty,
            "position_avg_price": avg_price,
            "cash": cash,
            "equity": equity_t,
            "last_price": last_close,
            "last_fill_ts": last_fill_ts,
            "last_fill_price": last_fill_price,
        }

        # 전략 호출
        decision = decide_fn(past, ctx, state := (locals().setdefault("_state", {})), strategy_params)
        # 다양한 반환 형태 수용
        sig: Optional[str] = None
        weight: Optional[float] = None
        if isinstance(decision, (tuple, list)) and len(decision) >= 1:
            sig = str(decision[0]).lower()
            weight = None if len(decision) < 2 or decision[1] is None else float(decision[1])
        elif isinstance(decision, dict):
            sig = str(decision.get("signal", "hold")).lower()
            w = decision.get("weight", None)
            weight = None if w is None else float(w)
        else:
            # 잘못된 반환은 hold 처리
            sig, weight = "hold", None

        # 목표 비중 (None이면 현 상태 유지)
        last_price_for_weight = last_close
        target_weight = None
        if weight is not None:
            target_weight = max(0.0, min(1.0, weight))

        # t+1 시가로 체결
        next_open = float(df.loc[t1, "open"])
        # 체결 전 포트폴리오 가치(체결 기준으로 환산)
        equity_t1_pre = cash + qty * next_open
        cur_weight = 0.0 if equity_t1_pre <= 0 else (qty * next_open) / equity_t1_pre

        # 액션→목표 비중 매핑
        if sig == "buy":
            target_weight = 1.0 if target_weight is None else target_weight
        elif sig == "sell":
            target_weight = 0.0 if target_weight is None else target_weight
        elif sig == "hold":
            # target_weight None → 유지
            if target_weight is None:
                target_weight = cur_weight
        else:
            target_weight = cur_weight  # 알 수 없는 신호는 유지

        # 목표 수량
        target_qty = 0.0 if equity_t1_pre <= 0 else (target_weight * equity_t1_pre) / next_open
        delta_qty = target_qty - qty

        filled = False
        if abs(delta_qty) > 1e-12:
            if delta_qty > 0:
                # BUY: 슬리피지 반영한 체결가
                fill_px = next_open * (1.0 + slip)
                # 구매 가능한 최대 수량(수수료 고려)
                # 비용 = qty*px + fee
                # fee = notional * fee
                # 총현금 필요 = q*px * (1+fee)
                max_buy_qty = cash / (fill_px * (1.0 + fee)) if fill_px > 0 else 0.0
                buy_qty = min(delta_qty, max_buy_qty)
                if buy_qty > 1e-12:
                    notional = buy_qty * fill_px
                    fee_amt = notional * fee
                    cash -= (notional + fee_amt)
                    # 평균단가 갱신
                    if qty <= 0:
                        avg_price = fill_px
                    else:
                        avg_price = (avg_price * qty + fill_px * buy_qty) / (qty + buy_qty) if avg_price else fill_px
                    qty += buy_qty
                    last_fill_ts, last_fill_price = t1, fill_px
                    filled = True
                    trades += 0  # BUY 자체는 체결 로그만, '완결 거래'는 SELL에서 카운트
                    if print_trades:
                        new_equity = cash + qty * next_open
                        pos_pct = 0.0 if new_equity <= 0 else (qty * next_open) / new_equity
                        print(f"[TRADE] {t1} BUY  qty={buy_qty:.8f} px={fill_px:.2f} "
                              f"notional={notional:.2f} cash={cash:.2f} eq={new_equity:.2f} pos={pos_pct*100:.1f}%")
            else:
                # SELL
                sell_qty = min(qty, -delta_qty)
                if sell_qty > 1e-12:
                    fill_px = next_open * (1.0 - slip)
                    notional = sell_qty * fill_px
                    fee_amt = notional * fee
                    cash += (notional - fee_amt)
                    qty -= sell_qty
                    # avg_price: 잔량 0이면 리셋
                    if qty <= 1e-12:
                        qty = 0.0
                        avg_price = None
                        trades += 1  # 포지션 종료로 '완결 거래' 1회
                    last_fill_ts, last_fill_price = t1, fill_px
                    filled = True
                    if print_trades:
                        new_equity = cash + qty * next_open
                        pos_pct = 0.0 if new_equity <= 0 else (qty * next_open) / new_equity
                        print(f"[TRADE] {t1} SELL qty={sell_qty:.8f} px={fill_px:.2f} "
                              f"notional={notional:.2f} cash={cash:.2f} eq={new_equity:.2f} pos={pos_pct*100:.1f}%")

        # 에쿼티 기록(시가 기준으로 마킹)
        equity_pairs.append((pd.Timestamp(t1).to_pydatetime(), cash + qty * next_open))

    # 마지막 바에서 청산 옵션
    last_ts = df.index[-1]
    last_close = float(df.loc[last_ts, "close"])
    if liquidate_on_end and qty > 0:
        fill_px = last_close * (1.0 - slip)
        notional = qty * fill_px
        fee_amt = notional * fee
        cash += (notional - fee_amt)
        if print_trades:
            new_equity = cash  # 포지션 0
            print(f"[TRADE] {last_ts} SELL qty={qty:.8f} px={fill_px:.2f} "
                  f"notional={notional:.2f} cash={cash:.2f} eq={new_equity:.2f} pos=0.0%")
        qty = 0.0
        avg_price = None
        trades += 1
        equity_pairs.append((pd.Timestamp(last_ts).to_pydatetime(), cash))
    else:
        # 마감 시점 에쿼티(종가 기준)
        equity_pairs.append((pd.Timestamp(last_ts).to_pydatetime(), cash + qty * last_close))

    equity_df = pd.Series({ts: val for ts, val in equity_pairs}, name="equity").sort_index()
    m = _metrics(equity_df, res)

    # 5) 산출물 저장
    run_id = _gen_run_id()
    start_s, end_s = pd.to_datetime(start).date().isoformat(), pd.to_datetime(end).date().isoformat()
    line = _one_line(run_id, symbol, res, strat_name_for_log or (strategy or "func"),
                     m["pnl"], m["sharpe"], m["mdd"], trades,
                     fee_bps, slip_bps, start_s, end_s)
    print(line)

    # 경로 구성
    if artifact_root:
        base = Path(artifact_root).resolve()
    else:
        # 실험명이 지정되지 않으면 UNNAMED-EXP로 모음
        base = (Path(__file__).resolve().parents[1] / "reports" / "UNNAMED-EXP")
    run_dir = base / "runs" / run_id
    fig_dir = run_dir / "figures"
    run_dir.mkdir(parents=True, exist_ok=True)
    fig_dir.mkdir(parents=True, exist_ok=True)

    # 파일 저장
    equity_path = str(run_dir / "equity.csv")
    orders_path = str(run_dir / "orders.csv")
    pd.Series(equity_df).to_csv(equity_path, header=True)

    # 의사결정 결과(실거래 집계) — orders.csv
    # 실제 체결 로그를 저장하려면 위 체결 지점에서 append 하도록 확장 가능.
    # 여기서는 최소 필수 집계만 저장(상세 주문 로그가 필요하면 확장 권장)
    # -> 간단히 placeholder (비움) 유지
    pd.DataFrame(orders).to_csv(orders_path, index=False)

    # summary.json (+ params)
    summary_obj = {
        "run_id": run_id, "symbol": symbol, "res": res,
        "strategy": strat_name_for_log or (strategy or "func"),
        "pnl": float(m["pnl"]), "sharpe": float(m["sharpe"]), "mdd": float(m["mdd"]),
        "trades": int(trades), "fee_bps": float(fee_bps), "slip_bps": float(slip_bps),
        "start": start_s, "end": end_s, "start_cash": float(start_cash),
        "params": strategy_params
    }
    with open(str(run_dir / "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary_obj, f, ensure_ascii=False, indent=2)

    # params.yaml(가벼운 메타덤프)
    try:
        import yaml
        with open(str(run_dir / "params.yaml"), "w", encoding="utf-8") as f:
            yaml.safe_dump({
                "symbol": symbol, "resolution": res,
                "start": start_s, "end": end_s,
                "start_cash": float(start_cash),
                "fee_bps": float(fee_bps), "slip_bps": float(slip_bps),
                "strategy": strat_name_for_log or (strategy or "func"),
                "strategy_params": strategy_params
            }, f, allow_unicode=True, sort_keys=False)
    except Exception:
        pass

    # 그림 저장
    plt.figure(figsize=(10, 4))
    equity_df.plot(ax=plt.gca())
    plt.title(f"Equity — {symbol} {res} {strat_name_for_log or (strategy or 'func')}")
    plt.tight_layout()
    plt.savefig(str(fig_dir / "equity.png"))
    plt.close()

    dd = equity_df / equity_df.cummax() - 1.0
    plt.figure(figsize=(10, 3))
    dd.plot(ax=plt.gca())
    plt.title("Drawdown")
    plt.tight_layout()
    plt.savefig(str(fig_dir / "drawdown.png"))
    plt.close()

    return {
        "run_id": run_id,
        "artifact_dir": str(run_dir),
        "equity_path": equity_path,
        "orders_path": orders_path,
        "summary": summary_obj
    }

"""
export ES_EXP_NAME="{파일명}"

python -m crypto_backtester.scripts.run_backtest \
  --symbol BTCUSDT --resolution 5m \
  --start 2024-08-31 --end 2025-08-31 \
  --strategy-func crypto_backtester.strategies.sma_align_macd:decide \
  --param tp_pct=0.05 --param sl_pct=-0.10 --param target_weight=1.0 \
  --start-cash 10000 \
  --artifact-root "experiments/${ES_EXP_NAME}"
"""
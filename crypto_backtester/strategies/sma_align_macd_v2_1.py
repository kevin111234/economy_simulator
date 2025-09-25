# strategies/sma_align_macd_v2_2.py
# -----------------------------------------------------------------------------
# SMA+MACD+RSI v2.2 (롱 전용)
# - 요구사항: "처음 진입 시점의 시작 현금(start_cash)을 기준자본으로 고정"
#   * 트렌드(60%): SMA20>60>120 && MACD line>0 → start_cash * 60% 집행
#   * RSI(40%): RSI<=20 → start_cash * 40% 집행
#   * 두 버킷은 '처음' 충족될 때만 할당, 합산 최대 100%
# - 목표비중 = (할당 Notional 총합 / 현재 equity) → ('buy', target_weight)로 통일
# - 부분청산(익절 분할): MACD hist 둔화 & 포지션 PnL≥+1% → 할당 Notional 50% 축소
# - 전량청산: 트레일링 스탑, RSI≥65, 일손실 캡
# - 가드: 리밸런스 데드존, 동일 바 중복행동 금지, 포지션당 부분청산 1회, 최소 홀드 바수
# -----------------------------------------------------------------------------

from __future__ import annotations
from typing import Dict, Tuple, Any
import math
import numpy as np
import pandas as pd

# 내장/로컬 양쪽 호환
try:
    from crypto_backtester.engine.indicators import sma as _sma, rsi as _rsi, atr as _atr, macd as _macd
except Exception:
    try:
        from engine.indicators import sma as _sma, rsi as _rsi, atr as _atr, macd as _macd
    except Exception:
        _sma = _rsi = _atr = _macd = None


# ---------- 유틸 ----------

def _safe_get_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    # SMA
    if "sma_20" not in out.columns:
        out["sma_20"] = (_sma(out["close"], 20) if _sma else out["close"].rolling(20, min_periods=20).mean())
    if "sma_60" not in out.columns:
        out["sma_60"] = (_sma(out["close"], 60) if _sma else out["close"].rolling(60, min_periods=60).mean())
    if "sma_120" not in out.columns:
        out["sma_120"] = (_sma(out["close"], 120) if _sma else out["close"].rolling(120, min_periods=120).mean())
    # MACD
    if not {"macd_line", "macd_signal", "macd_hist"}.issubset(out.columns):
        if _macd:
            ml, ms, mh = _macd(out["close"], 12, 26, 9)
        else:
            ema12 = out["close"].ewm(span=12, adjust=False, min_periods=12).mean()
            ema26 = out["close"].ewm(span=26, adjust=False, min_periods=26).mean()
            ml = ema12 - ema26
            ms = ml.ewm(span=9, adjust=False, min_periods=9).mean()
            mh = ml - ms
        out["macd_line"], out["macd_signal"], out["macd_hist"] = ml, ms, mh
    # RSI
    if "rsi_14" not in out.columns:
        if _rsi:
            out["rsi_14"] = _rsi(out["close"], n=14)
        else:
            d = out["close"].diff()
            up = d.clip(lower=0).ewm(alpha=1/14, adjust=False, min_periods=14).mean()
            dn = (-d.clip(upper=0)).ewm(alpha=1/14, adjust=False, min_periods=14).mean()
            rs = up / dn.replace(0, np.nan)
            out["rsi_14"] = 100 - 100/(1+rs)
    # ATR
    if "atr_14" not in out.columns:
        if _atr:
            out["atr_14"] = _atr(out["high"], out["low"], out["close"], n=14)
        else:
            prev = out["close"].shift(1)
            tr = pd.concat([(out["high"]-out["low"]).abs(),
                            (out["high"]-prev).abs(),
                            (out["low"]-prev).abs()], axis=1).max(axis=1)
            out["atr_14"] = tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    return out


def _get(ctx: Dict[str, Any], key: str, default=None):
    return ctx[key] if key in ctx and ctx[key] is not None else default


def _clip(x: float, lo: float, hi: float) -> float:
    return float(max(lo, min(hi, x)))


# ---------- 파라미터 ----------

DEFAULT_PARAMS = {
    # 임계
    "rsi_buy_th": 20.0,
    "rsi_sell_th": 65.0,

    # 버킷 크기 (시작 현금 기준)
    "bucket_trend_pct": 0.60,   # SMA정렬+MACD>0
    "bucket_rsi_pct": 0.40,     # RSI<=20
    "weight_cap": 1.00,         # 레버리지 없음

    # 트레일/리스크
    "atr_n": 14,                # (지표는 14로 계산됨)
    "trail_k": 2.5,             # 고점 - k*ATR

    # 부분청산
    "partial_take_ratio": 0.50,     # 50% 감액
    "min_partial_pnl_pct": 0.01,    # +1% 이상 수익일 때만

    # 보호 장치
    "daily_loss_cap_pct": 0.03,     # -3% 이상 손실 시 당일 중단
    "cooldown_min": 60,
    "reentry_block_n": 10,

    # 체결 억제
    "rebalance_deadzone": 0.02,     # 목표비중-현재비중 < 2%p면 거래 금지
    "min_hold_bars": 2,             # 목표 변경 후 최소 홀드 바수
}


# ---------- 메인 ----------

def decide(past_df: pd.DataFrame,
           ctx: Dict[str, Any],
           state: Dict[str, Any] | None,
           params: Dict[str, Any] | None) -> Tuple[str, float]:
    P = dict(DEFAULT_PARAMS); P.update(params or {})
    state = {} if state is None else state
    df = _safe_get_indicators(past_df)

    # 준비/검증
    t = df.index[-1]
    last = df.iloc[-1]
    req = ["sma_20","sma_60","sma_120","macd_line","macd_signal","macd_hist",
           "rsi_14","atr_14","close","high","low","open"]
    if any(pd.isna(last.get(c)) for c in req):
        return ("hold", np.nan)

    # 시세/지표
    price = float(last["close"])
    rsi = float(last["rsi_14"])
    macd_line = float(last["macd_line"])
    macd_hist = float(last["macd_hist"])
    prev_hist = float(df["macd_hist"].iloc[-2]) if len(df)>=2 and pd.notna(df["macd_hist"].iloc[-2]) else macd_hist
    sma20, sma60, sma120 = float(last["sma_20"]), float(last["sma_60"]), float(last["sma_120"])
    atr = float(last["atr_14"])
    trend_aligned = (sma20 > sma60 > sma120)

    # 계좌 상태
    equity = float(_get(ctx, "equity", 0.0))
    cash = float(_get(ctx, "cash", 0.0))
    pos_qty = float(_get(ctx, "position_qty", 0.0) or 0.0)
    avg_price = float(_get(ctx, "avg_price", np.nan) or np.nan)
    position_value = pos_qty * price
    current_weight = (position_value / equity) if equity > 0 else 0.0

    i_now = len(df) - 1

    # ── 시작 현금(start_cash)·버킷 상태 초기화 ───────────────────────────
    # 완전 무포지션(비중 0)일 때, start_cash를 현재 cash로 스냅샷
    if current_weight <= 0.0 and pos_qty <= 0.0:
        if not state.get("in_position", False):
            state["start_cash"] = cash
            state["alloc_trend"] = False
            state["alloc_rsi"] = False
            state["allocated_notional"] = 0.0
            state["partial_taken"] = False
            state["entry_price"] = np.nan
            state["high_since_entry"] = np.nan
            state["trail_price"] = np.nan
        state["in_position"] = False
    else:
        state["in_position"] = True

    start_cash = float(state.get("start_cash", cash))

    # ── 쿨다운/재진입 차단 & 일손실 캡 ──────────────────────────────────
    today_key = str(pd.to_datetime(t).floor("D"))
    if state.get("day_key") != today_key:
        state["day_key"] = today_key
        state["day_start_equity"] = equity
    day_start = float(state.get("day_start_equity") or equity)
    day_pnl_pct = (equity - day_start) / day_start if day_start > 0 else 0.0

    cooldown_until = state.get("cooldown_until")
    if (cooldown_until is not None) and (pd.Timestamp(t) < pd.Timestamp(cooldown_until)):
        return ("hold", np.nan)

    reentry_block_until_i = int(state.get("reentry_block_until_i", -1) or -1)
    if i_now <= reentry_block_until_i:
        return ("hold", np.nan)

    # ── 버킷 할당 (처음 충족 시 1회 집행) ────────────────────────────────
    bucket_trend = (not state.get("alloc_trend", False)) and (trend_aligned and macd_line > 0)
    bucket_rsi   = (not state.get("alloc_rsi", False))   and (rsi <= P["rsi_buy_th"])

    if bucket_trend:
        add_notional = P["bucket_trend_pct"] * start_cash
        state["allocated_notional"] = float(state.get("allocated_notional", 0.0)) + add_notional
        state["alloc_trend"] = True

    if bucket_rsi:
        add_notional = P["bucket_rsi_pct"] * start_cash
        state["allocated_notional"] = float(state.get("allocated_notional", 0.0)) + add_notional
        state["alloc_rsi"] = True

    allocated_notional = float(state.get("allocated_notional", 0.0))
    target_weight_from_buckets = _clip((allocated_notional / equity) if equity > 0 else 0.0,
                                       0.0, P["weight_cap"])

    # ── 출구 우선순위 ────────────────────────────────────────────────────
    entry_price = state.get("entry_price", np.nan)
    high_since = state.get("high_since_entry", np.nan)
    trail_price = state.get("trail_price", np.nan)

    if pos_qty > 0:
        # 트레일 갱신
        high_since = float(df["high"].iloc[-1]) if not math.isfinite(high_since) else max(high_since, float(df["high"].iloc[-1]))
        state["high_since_entry"] = high_since
        trail_k = float(P["trail_k"])
        trail_px = high_since - trail_k * atr
        trail_price = trail_px if not math.isfinite(trail_price) else max(trail_price, trail_px)
        state["trail_price"] = trail_price

        if price < trail_price:
            _on_full_exit_reset(state, i_now, t, P, loss=(math.isfinite(entry_price) and price < entry_price))
            return ("sell", 0.0)

    if day_pnl_pct <= -abs(P["daily_loss_cap_pct"]):
        if pos_qty > 0:
            _on_full_exit_reset(state, i_now, t, P, loss=True, day_stop=True)
            return ("sell", 0.0)

    # 부분청산(1회): MACD 둔화 & PnL≥+1%
    if pos_qty > 0 and (not state.get("partial_taken", False)):
        pos_pnl_pct = (price - avg_price) / avg_price if (math.isfinite(avg_price) and avg_price > 0) else 0.0
        if (macd_hist < prev_hist) and (pos_pnl_pct >= P["min_partial_pnl_pct"]):
            # 할당 Notional 50% 축소 → 목표비중 재계산
            state["allocated_notional"] = allocated_notional * (1.0 - float(P["partial_take_ratio"]))
            state["partial_taken"] = True
            state["acted_at_index"] = i_now
            new_w = _clip(state["allocated_notional"] / equity if equity > 0 else 0.0, 0.0, P["weight_cap"])
            return ("buy", new_w)

    # 전량청산: RSI≥65
    if pos_qty > 0 and rsi >= P["rsi_sell_th"]:
        _on_full_exit_reset(state, i_now, t, P, loss=(math.isfinite(avg_price) and price < avg_price))
        return ("sell", 0.0)

    # ── 엔트리/증감액 집행 ───────────────────────────────────────────────
    if state.get("acted_at_index") == i_now:
        return ("hold", np.nan)

    desired_w = target_weight_from_buckets
    # 데드존 & 최소 홀드
    if abs(desired_w - current_weight) < P["rebalance_deadzone"]:
        return ("hold", np.nan)
    last_target_i = int(state.get("last_target_index", -10))
    if (i_now - last_target_i) < int(P["min_hold_bars"]):
        return ("hold", np.nan)

    # 최초 진입 메타
    if desired_w > current_weight and pos_qty <= 0:
        state["entry_price"] = price
        state["high_since_entry"] = float(df["high"].iloc[-1])
        state["trail_price"] = float("nan")

    state["acted_at_index"] = i_now
    state["last_target_index"] = i_now
    # 감액/증액 모두 'buy'로 절대 목표비중 전달 (러너 호환)
    return ("buy", desired_w)


# ---------- 전량 청산 시 상태 리셋 ----------

def _on_full_exit_reset(state: Dict[str, Any], i_now: int, t: pd.Timestamp, P: Dict[str, Any],
                        loss: bool = False, day_stop: bool = False):
    # 손실 스트릭/쿨다운
    if loss:
        loss_streak = int(state.get("loss_streak", 0) or 0) + 1
        state["loss_streak"] = loss_streak
        if loss_streak >= 3:
            state["cooldown_until"] = pd.Timestamp(t) + pd.Timedelta(minutes=int(P["cooldown_min"]))
    else:
        state["loss_streak"] = 0
    if day_stop:
        state["cooldown_until"] = pd.Timestamp(t) + pd.Timedelta(hours=24)

    state["reentry_block_until_i"] = i_now + int(P["reentry_block_n"])
    # 트레일/버킷/메타 리셋
    state["entry_price"] = np.nan
    state["high_since_entry"] = np.nan
    state["trail_price"] = np.nan
    state["partial_taken"] = False
    state["acted_at_index"] = i_now

    state["alloc_trend"] = False
    state["alloc_rsi"] = False
    state["allocated_notional"] = 0.0
    state["in_position"] = False

"""
python crypto_backtester/scripts/run_backtest.py \
  --symbol BTCUSDT \
  --resolution 5m \
  --start 2022-01-01 \
  --end 2025-09-01 \
  --strategy-func crypto_backtester.strategies.sma_align_macd_v2_1:decide \
  --fee-bps 5 \
  --slip-bps 4 \
  --artifact-root experiments/demo \
  --param rsi_buy_th=20 \
  --param rsi_sell_th=65 \
  --param trail_k=2.5 \
  --param rebalance_deadzone=0.02 \
  --param min_hold_bars=2

"""
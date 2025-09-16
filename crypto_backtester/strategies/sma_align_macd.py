from __future__ import annotations
from typing import Dict, Any, Tuple, Union, Optional
import pandas as pd

def decide(
    past_df: pd.DataFrame,
    ctx: Dict[str, Any],
    state: Dict[str, Any],
    params: Dict[str, Any]
) -> Union[Tuple[str, float], Tuple[str, None], Dict[str, Any]]:
    """
    매수 조건:
      1) sma_20 > sma_60 > sma_120  (정렬)
      2) macd_line > 0
    매도 조건:
      - 수익 +5% 이상 (tp_pct=0.05)
      - 손실 -10% 이하 (sl_pct=-0.10)

    반환: ('buy', w) / ('sell', 0.0) / ('hold', None)
    """
    tp_pct = float(params.get("tp_pct", 0.05))
    sl_pct = float(params.get("sl_pct", -0.10))
    target_weight = float(params.get("target_weight", 1.0))

    last = past_df.iloc[-1]
    close = float(last["close"])

    sma20  = float(last.get("sma_20", float("nan")))
    sma60  = float(last.get("sma_60", float("nan")))
    sma120 = float(last.get("sma_120", float("nan")))
    macd_line = float(last.get("macd_line", float("nan")))

    have_pos = ctx["position_qty"] > 0
    avg_price = ctx.get("position_avg_price", None)

    # 익절/손절: 포지션 보유 중에만
    if have_pos and avg_price:
        pnl = (close / avg_price) - 1.0
        if pnl >= tp_pct or pnl <= sl_pct:
            return ("sell", 0.0)

    # 매수 조건
    if (sma20 > sma60 > sma120) and (macd_line > 0):
        # 이미 목표 비중 이상이면 hold
        # 실제 목표비중 여부는 러너가 판단하지만, 여기서는 의도를 명확히 전달
        return ("buy", target_weight)

    return ("hold", None)

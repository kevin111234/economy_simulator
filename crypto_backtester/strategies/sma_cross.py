from __future__ import annotations
import pandas as pd
from crypto_backtester.engine.indicators import sma

def generate_signals(df: pd.DataFrame, short: int = 20, long: int = 60) -> pd.Series:
    """단순 SMA 크로스, long-only. t 신호 → t+1 체결을 위해 shift(1) 적용."""
    s = sma(df["close"], short)
    l = sma(df["close"], long)
    sig = (s > l).astype(int)
    return sig.shift(1).fillna(0).astype(int)

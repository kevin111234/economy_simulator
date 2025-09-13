from __future__ import annotations
import pandas as pd
from crypto_backtester.engine.indicators import sma, macd, atr

def generate_signals(
    df: pd.DataFrame,
    sma_short: int = 20,
    sma_long: int = 60,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal: int = 9,
    atr_n: int = 14,
    atr_k: float = 3.0,
) -> pd.Series:
    """
    엔트리: SMA 크로스 상승 & MACD>0
    이그zit: Chandelier Exit 스타일 - close < (rolling_max(high, atr_n) - atr_k*ATR)
           또는 SMA 재하락, MACD<0
    """
    s = sma(df["close"], sma_short)
    l = sma(df["close"], sma_long)
    macd_line, macd_sig, _ = macd(df["close"], macd_fast, macd_slow, macd_signal)
    a = atr(df, atr_n)
    ce_long = df["high"].rolling(atr_n, min_periods=atr_n).max() - atr_k * a

    long_entry = (s > l) & (macd_line > 0)
    long_exit  = (df["close"] < ce_long) | (s < l) | (macd_line < 0)

    # 상태 머신: 0/1 포지션
    state = 0
    sig = []
    for i in range(len(df)):
        if state == 0:
            if bool(long_entry.iloc[i]):
                state = 1
        else:
            if bool(long_exit.iloc[i]):
                state = 0
        sig.append(state)

    sig = pd.Series(sig, index=df.index).astype(int)
    return sig.shift(1).fillna(0).astype(int)  # t 신호 → t+1 체결

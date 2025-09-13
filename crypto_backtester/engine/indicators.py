from __future__ import annotations
import pandas as pd

def sma(close: pd.Series, n: int) -> pd.Series:
    return close.rolling(n, min_periods=n).mean()

def ema(close: pd.Series, n: int) -> pd.Series:
    return close.ewm(span=n, adjust=False, min_periods=n).mean()

def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = macd_line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist

def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """Wilder's ATR (EWMA with alpha=1/n)"""
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low),
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    atr_ = tr.ewm(alpha=1.0/n, adjust=False, min_periods=n).mean()
    return atr_

def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1.0/n, adjust=False, min_periods=n).mean()
    avg_loss = loss.ewm(alpha=1.0/n, adjust=False, min_periods=n).mean()
    rs = avg_gain / (avg_loss.replace(0, pd.NA))
    rsi_ = 100 - (100 / (1 + rs))
    return rsi_

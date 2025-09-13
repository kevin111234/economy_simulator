import pandas as pd
from crypto_backtester.engine.indicators import sma, ema, rsi, atr, macd

def test_sma_matches_pandas():
    s = pd.Series(range(1,11), dtype=float)
    assert sma(s, 3).iloc[-1] == s.rolling(3).mean().iloc[-1]

def test_macd_shapes():
    s = pd.Series(range(1,200), dtype=float)
    m, sig, h = macd(s, 12, 26, 9)
    assert len(m) == len(sig) == len(h) == len(s)

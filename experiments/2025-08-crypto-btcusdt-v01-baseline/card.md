# BTCUSDT v0.1 Baseline (5m, 2024-08-31 ~ 2025-08-31)

## 가설
- 단순 **SMA 크로스(20/60)** long-only가 5m에서도 추세 구간을 포착한다. [Speculation]

## 세팅
- 데이터: Binance 5m, on-close 체결
- 전략: sma_cross(20/60), long-only, all-in
- 비용: 수수료 5bps, 슬리피지 4bps(왕복 18bps)
- 시작현금: $10,000, 종료 시 청산

## 요약(한 줄)
- PnL -80.68%, Sharpe -4.90, MDD -80.69%, Trades 1053 → 비용/휘핑 과다.

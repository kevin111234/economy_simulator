# crypto_backtester (part of Economy Simulator)

암호화폐 및 다중 자산군을 대상으로 하는 백테스트 엔진입니다.  
MariaDB 기반 시계열 저장소, 표준화된 지표 계산기, 전략 인터페이스, 실행/리포팅 파이프라인을 포함합니다.

## Features
- **데이터 계층**
  - Binance 5m 시세 인제스트
  - 5m → 1d 리샘플링
  - 월 단위 파티션 관리
  - 품질 점검(QC) 도구

- **엔진 계층**
  - SMA / EMA / MACD / ATR / RSI 등 기본 지표
  - 전략 함수 인터페이스 (`decide(past_df, ctx, state, params)`)
  - 슬리피지/수수료 반영 체결, 현금 제약 반영
  - PnL / Sharpe / MDD 계산
  - 산출물: equity.csv, orders.csv, summary.json, figures/

- **리포트 계층**
  - 단일 실행 결과를 표준 디렉토리에 동기화
  - `card.md`, `report.md`, `runs.csv` 생성
  - 다건 실행 요약(summarize_runs)

## Project Layout
```

conf/
base.yaml              # 기본 설정
db/migrations/           # 초기 스키마, 파티션, migrate.sh
engine/
db\_utils.py            # DB 유틸
indicators.py          # 지표 계산기
runner.py              # 백테스트 코어
strategies/
sma\_align\_macd.py      # 예시 전략
scripts/
ingest\_binance\_5m.py   # 데이터 적재
resample\_to\_1d.py      # 5m → 1d 변환
qc\_bars.py             # QC 도구
run\_backtest.py        # 백테스트 실행 CLI
make\_experiment\_report.py # 리포트 생성
summarize\_runs.py      # 실행 집계

````

## Quickstart
1. **DB 초기화**
   ```bash
   cd db/migrations
   ./migrate.sh
````

2. **데이터 인제스트**

   ```bash
   python scripts/ingest_binance_5m.py --symbol BTCUSDT --start 2024-01-01 --end 2024-12-31
   ```

3. **QC 점검**

   ```bash
   python scripts/qc_bars.py --symbol BTCUSDT --res 5m --market crypto --start 2024-01-01 --end 2024-12-31
   ```

4. **리샘플**

   ```bash
   python scripts/resample_to_1d.py --symbol BTCUSDT --start 2024-01-01 --end 2024-12-31
   ```

5. **백테스트**

   ```bash
   python scripts/run_backtest.py \
     --symbol BTCUSDT \
     --resolution 1d \
     --start 2024-01-01 --end 2024-12-31 \
     --strategy-func crypto_backtester.strategies.sma_align_macd:decide \
     --param tp_pct=0.05 --param sl_pct=-0.1 \
     --artifact-root experiments/test
   ```

6. **리포트 정리**

   ```bash
   python scripts/make_experiment_report.py --from-dir experiments/test/runs/<run_id> --exp-dir experiments/test
   ```

7. **실행 요약**

   ```bash
   python scripts/summarize_runs.py --reports-dir crypto_backtester/reports --sort-by sharpe --top 20
   ```


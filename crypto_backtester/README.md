# crypto_backtester (part of Economy Simulator)

암호화폐 및 다중 자산군을 대상으로 하는 백테스트 엔진입니다.  
MariaDB 기반 시계열 저장소, 표준화된 지표 계산기, 전략 인터페이스, 실행/리포팅 파이프라인을 포함합니다.

---

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

---

## Project Layout
```

conf/
base.yaml
db/migrations/
0001\_init.tmpl.sql
0002\_partitions.tmpl.sql
migrate.sh
engine/
db\_utils.py
indicators.py
runner.py
strategies/
sma\_align\_macd.py
scripts/
ingest\_binance\_5m.py
resample\_to\_1d.py
qc\_bars.py
run\_backtest.py
make\_experiment\_report.py
summarize\_runs.py

````

---

## Quickstart

### 1. DB 초기화
```bash
cd db/migrations
./migrate.sh --drop   # clean setup
````

### 2. 데이터 인제스트

```bash
python scripts/ingest_binance_5m.py \
  --symbol BTCUSDT \
  --start 2024-01-01 \
  --end 2024-12-31
```

### 3. QC 점검

```bash
python scripts/qc_bars.py \
  --symbol BTCUSDT \
  --res 5m \
  --market crypto \
  --start 2024-01-01 \
  --end 2024-12-31
```

### 4. 리샘플

```bash
python scripts/resample_to_1d.py \
  --symbol BTCUSDT \
  --start 2024-01-01 \
  --end 2024-12-31
```

### 5. 백테스트

```bash
python scripts/run_backtest.py \
  --symbol BTCUSDT \
  --resolution 1d \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --strategy-func crypto_backtester.strategies.sma_align_macd:decide \
  --param tp_pct=0.05 \
  --param sl_pct=-0.1 \
  --artifact-root experiments/test
```

### 6. 리포트 정리

```bash
python scripts/make_experiment_report.py \
  --from-dir experiments/test/runs/<run_id> \
  --exp-dir experiments/test \
  --notes "첫 번째 실험"
```

### 7. 실행 요약

```bash
python scripts/summarize_runs.py \
  --reports-dir crypto_backtester/reports \
  --sort-by sharpe \
  --top 20
```

---

## Sample Session

```bash
# 1) 데이터 적재
python scripts/ingest_binance_5m.py --symbol BTCUSDT --start 2024-01-01 --end 2024-06-01

# 2) QC
python scripts/qc_bars.py --symbol BTCUSDT --res 5m --market crypto --start 2024-01-01 --end 2024-06-01

# 3) 리샘플
python scripts/resample_to_1d.py --symbol BTCUSDT --start 2024-01-01 --end 2024-06-01

# 4) 백테스트
python scripts/run_backtest.py \
  --symbol BTCUSDT --resolution 1d \
  --start 2024-01-01 --end 2024-06-01 \
  --strategy-func crypto_backtester.strategies.sma_align_macd:decide \
  --param tp_pct=0.05 --param sl_pct=-0.1 \
  --artifact-root experiments/demo

# 5) 실험 보고서 생성
python scripts/make_experiment_report.py \
  --from-dir experiments/demo/runs/20250101-120000-abcdef \
  --exp-dir experiments/demo --notes "데모 런"

# 6) 실행 모아보기
python scripts/summarize_runs.py --reports-dir crypto_backtester/reports --sort-by sharpe --top 5
```

---

## Example Directory Structure

```
experiments/demo/
├── runs/
│   └── 20250101-120000-abcdef/
│       ├── equity.csv
│       ├── orders.csv
│       ├── summary.json
│       ├── params.yaml
│       └── figures/
│           ├── equity.png
│           └── drawdown.png
├── runs.csv
├── report.md
├── card.md
└── links.json
```


# GUIDE: How to Run crypto_backtester

이 문서는 실무적으로 터미널에서 어떤 명령어를 입력해야 백테스트와 데이터 파이프라인을 수행할 수 있는지를 안내합니다.

---

## 1. Database Migration
초기 스키마와 파티션을 설정합니다.

```bash
cd db/migrations
./migrate.sh --drop   # DB를 새로 만들 때
./migrate.sh          # DB 업데이트
````

---

## 2. Ingest (데이터 적재)

Binance Spot API에서 5m 데이터를 불러와 DB에 저장합니다.

```bash
python scripts/ingest_binance_5m.py \
  --symbol BTCUSDT \
  --start 2024-01-01 \
  --end 2024-06-01 \
  --sleep 0.5
```

옵션:

* `--csv-out tmp.csv` : DB 적재 대신 CSV 파일에 기록

---

## 3. QC (데이터 품질 검사)

DB에 저장된 데이터가 정상인지 검사합니다.

```bash
python scripts/qc_bars.py \
  --symbol BTCUSDT \
  --res 5m \
  --market crypto \
  --start 2024-01-01 \
  --end 2024-06-01
```

---

## 4. Resample (5m → 1d)

DB 내 5m 봉을 1일 봉으로 리샘플링합니다.

```bash
python scripts/resample_to_1d.py \
  --symbol BTCUSDT \
  --start 2024-01-01 \
  --end 2024-06-01
```

---

## 5. Run Backtest

전략 함수를 지정하여 백테스트를 실행합니다.

```bash
python scripts/run_backtest.py \
  --symbol BTCUSDT \
  --resolution 1d \
  --start 2024-01-01 \
  --end 2024-06-01 \
  --strategy-func crypto_backtester.strategies.sma_align_macd:decide \
  --param tp_pct=0.05 \
  --param sl_pct=-0.1 \
  --artifact-root experiments/dev
```

옵션:

* `--fee-bps 5 --slip-bps 4` : 수수료와 슬리피지 지정
* `--param key=val` : 전략 파라미터 전달

---

## 6. Make Experiment Report

러너 산출물을 실험 폴더에 정리합니다.

```bash
python scripts/make_experiment_report.py \
  --from-dir experiments/dev/runs/<run_id> \
  --exp-dir experiments/dev \
  --notes "첫 번째 실험"
```

---

## 7. Summarize Runs

여러 실행을 정렬/집계합니다.

```bash
python scripts/summarize_runs.py \
  --reports-dir crypto_backtester/reports \
  --sort-by sharpe \
  --top 50
```

---

## Best Practices

* 항상 **QC → Resample → Backtest** 순으로 실행하세요.
* `artifact-root`는 실험 단위로 분리 관리하세요 (`experiments/<exp_name>`).
* DB는 월별 파티션이므로 장기간 데이터도 관리 부담이 적습니다.

---

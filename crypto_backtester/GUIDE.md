# GUIDE: How to Use crypto_backtester

이 문서는 실무적으로 어떤 명령어를 입력해야 전체 파이프라인을 돌릴 수 있는지를 단계별로 안내합니다.

---

## 1. DB Migration
초기 스키마와 파티션을 설정합니다.

```bash
cd db/migrations
./migrate.sh --drop   # DB 새로 생성
./migrate.sh          # 기존 DB 업데이트
````

---

## 2. Data Ingest (Binance 5m)

```bash
python scripts/ingest_binance_5m.py \
  --symbol BTCUSDT \
  --start 2024-01-01 \
  --end 2024-06-01 \
  --sleep 0.5
```

옵션:

* `--csv-out tmp.csv` : CSV 파일 저장
* `--sleep 0.5` : API 호출 사이에 딜레이(레이트리밋 완화)

---

## 3. Quality Check

```bash
python scripts/qc_bars.py \
  --symbol BTCUSDT \
  --res 5m \
  --market crypto \
  --start 2024-01-01 \
  --end 2024-06-01
```

출력: 예상 vs 실제 캔들 수, 누락 구간, NaN 여부 등

---

## 4. Resample 5m → 1d

```bash
python scripts/resample_to_1d.py \
  --symbol BTCUSDT \
  --start 2024-01-01 \
  --end 2024-06-01
```

---

## 5. Run Backtest

```bash
python scripts/run_backtest.py \
  --symbol BTCUSDT \
  --resolution 1d \
  --start 2024-01-01 \
  --end 2024-06-01 \
  --strategy-func crypto_backtester.strategies.sma_align_macd:decide \
  --fee-bps 5 --slip-bps 4 \
  --param tp_pct=0.05 \
  --param sl_pct=-0.1 \
  --artifact-root experiments/demo
```

실행 후 `experiments/demo/runs/<run_id>/` 폴더 생성:

* `equity.csv`, `orders.csv`, `summary.json`, `params.yaml`
* `figures/equity.png`, `figures/drawdown.png`

---

## 6. Make Experiment Report

```bash
python scripts/make_experiment_report.py \
  --from-dir experiments/demo/runs/<run_id> \
  --exp-dir experiments/demo \
  --notes "첫 번째 실험"
```

결과:

* `card.md` (한눈 요약)
* `report.md` (상세 리포트)
* `links.json` (상대 경로 맵)
* `runs.csv` (실험 누적 기록)

---

## 7. Summarize Runs

여러 실행을 한눈에 모아봅니다.

```bash
python scripts/summarize_runs.py \
  --reports-dir crypto_backtester/reports \
  --sort-by sharpe \
  --top 10
```

결과: `reports/summary.csv`에 상위 실행 정리

---

## Recommended Workflow

1. `migrate.sh` → DB 준비
2. `ingest_binance_5m.py` → 5m 데이터 적재
3. `qc_bars.py` → 데이터 품질 검사
4. `resample_to_1d.py` → 1d 변환
5. `run_backtest.py` → 백테스트 실행
6. `make_experiment_report.py` → 실험 정리
7. `summarize_runs.py` → 전체 비교

---
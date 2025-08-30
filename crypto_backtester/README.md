# Crypto Backtester v0.1 — 실행 가이드 (BTCUSDT • 1년)

> 범위: **현물 long-only**, on-close 체결, **상수 비용(수수료/슬리피지)**, **해상도 5m·1d(1h 제외)**, **MariaDB** 연동, 실험 기록은 GitHub 내부만 사용.

## 1) 실험 설정(확정)

* 심볼/시장: **BTCUSDT (Binance 현물)**
* 기간(UTC): **2024-08-31 \~ 2025-08-30** (최근 1년)
* 해상도: **5m, 1d** (1h 미사용)
* 비용 가정(상수, bps): 수수료 **maker=1**, **taker=5** / 슬리피지 **crypto=4**
* 저장 정책:

  * DB(MariaDB): **5m 최근 1년**, **1d 전기간**
  * 파일(Parquet): 장기 5m 원본(3–5년+) 보관

---

## 2) 레포 구조(실험 폴더 포함)

```
/engine/           # 체결/비용/러너
/strategies/       # sma_cross, sma_macd_atr (+ 메타 JSON)
/scripts/          # ingest/resample/run/analytics/admin(스켈레톤)
/db/               # DDL, 파티션 관리 SQL
/datasets/         # 5m CSV/Parquet 원본
/reports/          # 요약·커브·주문 CSV/JSONL
/experiments/2025-08-crypto-btcusdt-v01-baseline/
  card.md          # 사고과정·가설·결과 요약
  params.yaml      # 실행 파라미터(아래 예시)
  runs.csv         # 핵심 지표 집계(헤더 고정)
  report.md        # 1~2p 요약 리포트
  links.json       # DB run_id / 질의문
  figures/         # equity, drawdown 등
```

---

## 3) 설정 스냅샷

### `/conf/base.yaml` (핵심 발췌)

```yaml
fees_bps: { maker: 1.0, taker: 5.0 }
slippage_bps: { crypto: 4 }
resolutions: { crypto: [5m, 1d] }   # 1h 미사용
database:
  driver: mariadb
  host: ${DB_HOST}
  port: ${DB_PORT}
  user: ${DB_USER}
  password: ${DB_PASS}
  name: ${DB_NAME}
  pool_size: ${DB_POOL_SIZE}
  connect_timeout: ${DB_CONNECT_TIMEOUT}
  timezone: "UTC"
  enabled: true
```

### `.env.example`

```ini
DB_HOST=localhost
DB_PORT=3306
DB_USER=econ_user
DB_PASS=change_me
DB_NAME=econ_sim
DB_POOL_SIZE=10
DB_CONNECT_TIMEOUT=10
```

---

## 4) 실험 폴더 내용(초안)

### `params.yaml` (v0.1 기준)

```yaml
experiment:
  slug: "2025-08-crypto-btcusdt-v01-baseline"
  seed: 42

data:
  source: "binance"
  symbol: "BTCUSDT"
  tz: "UTC"
  start: "2024-08-31"
  end:   "2025-08-30"
  resolutions: ["5m", "1d"]   # 1h 제외

costs:
  fees_bps: { maker: 1.0, taker: 5.0 }
  slippage_bps: { default: 4 }

strategies:
  - name: "sma_cross"
    params: { short: 20, long: 60 }
  - name: "sma_macd_atr"
    params:
      sma:   { short: 20, long: 60 }
      macd:  { fast: 12, slow: 26, signal: 9 }
      atr:   { n: 14, k: 3.0 }

runner:
  liquidate_on_end: true
  outputs: ["orders_csv", "equity_csv", "summary_jsonl", "console_one_line"]

analytics:   # v0.1 미니 버전
  label_horizons: ["5m", "1d"]
  up_event_thresholds: { "5m": 0.003, "1d": 0.02 }   # 예: +0.3%, +2%
  precursor_window: { "5m": "30m", "1d": "24h" }
  indicators: ["SMA20", "SMA60", "MACD", "RSI", "ATR"]
```

### `runs.csv` (헤더)

```
run_id,seed,start,end,symbol,resolution,strategy,fee_bps,slip_bps,sharpe,mdd,pnl,trades,notes
```

### `links.json` (예시)

```json
{
  "mysql": {
    "backtest_run_id": "to-fill-after-first-run",
    "orders_query": "SELECT * FROM orders WHERE run_id='to-fill' ORDER BY ts LIMIT 10"
  }
}
```

---

## 5) DB 스키마 & 파티션(최근 1년)

### 핵심 테이블

```sql
-- 가격
CREATE TABLE IF NOT EXISTS bars (
  asset_id INT NOT NULL,
  res ENUM('5m','1d') NOT NULL,
  ts DATETIME NOT NULL,
  ts_date DATE AS (DATE(ts)) VIRTUAL,
  open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume DOUBLE,
  PRIMARY KEY (asset_id, res, ts),
  KEY idx_ts (ts),
  KEY idx_date (ts_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 백테스트 요약·주문
CREATE TABLE IF NOT EXISTS backtest_run (
  run_id VARCHAR(64) PRIMARY KEY,
  symbol VARCHAR(32), res VARCHAR(8),
  strategy VARCHAR(64), params_json JSON,
  start_ts DATETIME, end_ts DATETIME,
  fee_bps DOUBLE, slip_bps DOUBLE,
  pnl DOUBLE, sharpe DOUBLE, mdd DOUBLE, trades INT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS orders (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  run_id VARCHAR(64), ts DATETIME, side VARCHAR(8),
  symbol VARCHAR(32), res VARCHAR(8),
  qty DOUBLE, price DOUBLE, fee_bps DOUBLE, slippage_bps DOUBLE,
  INDEX idx_run (run_id), INDEX idx_ts (ts)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### 월 파티션(예시: 2024-09 \~ 2025-09 경계)

```sql
ALTER TABLE bars
PARTITION BY RANGE COLUMNS (ts_date) (
  PARTITION p2024_09 VALUES LESS THAN ('2024-10-01'),
  PARTITION p2024_10 VALUES LESS THAN ('2024-11-01'),
  PARTITION p2024_11 VALUES LESS THAN ('2024-12-01'),
  PARTITION p2024_12 VALUES LESS THAN ('2025-01-01'),
  PARTITION p2025_01 VALUES LESS THAN ('2025-02-01'),
  PARTITION p2025_02 VALUES LESS THAN ('2025-03-01'),
  PARTITION p2025_03 VALUES LESS THAN ('2025-04-01'),
  PARTITION p2025_04 VALUES LESS THAN ('2025-05-01'),
  PARTITION p2025_05 VALUES LESS THAN ('2025-06-01'),
  PARTITION p2025_06 VALUES LESS THAN ('2025-07-01'),
  PARTITION p2025_07 VALUES LESS THAN ('2025-08-01'),
  PARTITION p2025_08 VALUES LESS THAN ('2025-09-01')
);
```

> 운영 규칙: 매월 1일 새 파티션 추가, **최근 12개월 유지** 후 초과분 드롭.

---

## 6) 파이프라인(연구 단계 실행 순서)

1. **Ingest (5m 원본 적재)**

   * `datasets/btcusdt_5m.csv` → UTC, 컬럼 `ts,open,high,low,close,volume`
   * 중복/역시계 제거 → DB `bars(res='5m')`와 Parquet 동시 적재

2. **Resample (1d 생성)**

   * 5m → 1d (first/max/min/last/sum) → DB `bars(res='1d')` 업서트

3. **Indicators/Labels (v0.1 미니)**

   * SMA/EMA/MACD/RSI/ATR 계산, `indicator_value`(선택) 적재
   * 라벨 K∈{5m,1d} 계산(미래 바 확보시 확정)

4. **Backtest (전략 2종)**

   * `sma_cross(20,60)` / `sma_macd_atr(12,26,9 / ATR n=14,k=3)`
   * **한 줄 요약** 콘솔 출력 + `reports/summary.jsonl` 저장
   * DB `backtest_run` & `orders`에 저장

5. **Analytics (미니)**

   * IC(Spearman) / 전조 빈도-리프트 계산 → `reports/<run_id>_analytics.json`

6. **실험 기록(레포 내부)**

   * `/experiments/2025-08-crypto-btcusdt-v01-baseline/`에
     `card.md, params.yaml, runs.csv, report.md, links.json, figures/*` 정리

---

## 7) “한 줄 요약” 포맷(고정)

```
[run_id=<id>] BTCUSDT <res> <strategy> PnL=+12.8% Sharpe=0.93 MDD=-23.1% Trades=84 Fee=5bps Slip=4bps Period=2024-08-31→2025-08-30
```

`reports/summary.jsonl` 예:

```json
{"run_id":"<id>","symbol":"BTCUSDT","res":"5m","strategy":"sma_macd_atr",
 "pnl":0.128,"sharpe":0.93,"mdd":-0.231,"trades":84,"fee_bps":5,"slip_bps":4,
 "start":"2024-08-31","end":"2025-08-30","seed":42}
```

---

## 8) 품질 게이트(DoD)

* **무결성**: 결측/중복/역시계 0, 5m→1d 집계 규칙 검증 통과
* **메타모픽**: `fee=0 & slip=0` → 벡터화 손익과 정확히 일치
* **재현성**: 같은 입력/파라미터/시드 → 동일 요약 수치
* **성능**: 5m 1년 단일 전략 원활 실행(메모리 폭증 없음)
* **저장**: `reports/`(CSV/JSONL) + DB `backtest_run/orders` 행 생성
* **문서**: 실험 폴더에 card/report/runs/links/figures 채워짐

---

## 9) 운영 스케줄(관리자 기능 • 스켈레톤)

| 잡                               | 주기     | 내용                            |
| ------------------------------- | ------ | ----------------------------- |
| `ingest:crypto`                 | 5분     | 신규 5m 바 수집 → DB/Parquet 동시 적재 |
| `resample:1d`                   | 1일 1회  | 5m → 1d 생성·업서트                |
| `indicators:recalc`             | 5\~60분 | 최신 바 기준 지표 업데이트               |
| `labels:update`                 | 5\~60분 | 미래 바 확보 시 라벨 확정               |
| `analytics:update`              | 1일     | 전조·IC 통계 캐시 갱신                |
| `retention:drop_old_partitions` | 월 1회   | 5m 12개월 초과 파티션 드롭             |

---

## 10) 장기 계획(crypto 전용 로드맵)

* **v0.1**: 위 가이드 달성(전략 2종, 한 줄 요약, DB/JSONL, 미니 analytics)
* **v0.2**: 변동성 타겟 사이징, 비용 분해, Turnover 보고, 파라미터 스윕(그리드/랜덤), 워크포워드
* **v0.3**: 상관/MI/전조 패턴 캐시 고도화, 준실시간 갱신(5m)
* **v0.4**: Perp(펀딩/레버리지/청산/숏) 도입, 리스크 오버레이
* **v0.5**: REST API 1차(`/strategies`, `/backtests` 큐), 사용자 파라미터 검증·레이트 리밋
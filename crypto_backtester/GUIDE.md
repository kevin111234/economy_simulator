# DB 빠른 시작 (터미널 전용)

> 스키마는 단순화되어 **시장데이터만 DB(bars/asset)** 에 저장합니다.
> 캔들 `ts`는 **UTC**(naive DATETIME), 백테스트 조회 구간은 **end exclusive** 규약입니다.

## 0) 환경 변수 로드

레포 루트의 `.env`를 셸에 올립니다.

```bash
cd /path/to/economy_simulator
set -a && . ./.env && set +a   # DB_HOST/DB_PORT/DB_USER/DB_PASS/DB_NAME 등 로드
echo "$DB_HOST:$DB_PORT $DB_NAME"
```

> `DB_NAME`은 migrations SQL에서 사용하는 스키마(`econ_sim`)와 일치해야 합니다.

---

## 1) 스키마 생성(1회)

### 1-1) 기본 테이블 생성

```bash
MIG_DIR=crypto_backtester/db/migrations

# 데이터베이스 및 기본 테이블(asset, bars) 생성
mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASS" < "$MIG_DIR/0001_init.sql"
```

* 포함 내용: DB 생성(`econ_sim`), `asset`, `bars` 테이블(복합 PK: `asset_id,res,ts`) 생성.&#x20;

### 1-2) 월별 파티션 생성

```bash
# bars 테이블 월별 파티션 + pmax(안전망) 구성
mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASS" < "$MIG_DIR/0002_partitions.sql"
```

* 포함 내용: `bars`를 `ts` 기준 월 단위 파티셔닝, 마지막 `pmax`로 초과 구간 수용.&#x20;

---

## 2) 건강 체크

```bash
# 연결 확인(1이 출력되면 OK)
mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASS" -Nse "SELECT 1;"

# 테이블 목록
mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASS" -e "SHOW TABLES FROM econ_sim;"

# 테이블 구조 확인
mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASS" -e "DESC econ_sim.asset; DESC econ_sim.bars;"

# 파티션 목록( bars )
mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASS" -e \
"SELECT TABLE_NAME, PARTITION_NAME
 FROM INFORMATION_SCHEMA.PARTITIONS
 WHERE TABLE_SCHEMA='econ_sim' AND TABLE_NAME='bars';"
```

---

## 3) 데이터 적재/리샘플/점검 (스크립트 연결)

### 3-1) 5분봉 적재 (Binance)

```bash
# 최근 1년(예: 2024-08-31 ~ 2025-08-31; end exclusive) BTCUSDT
python -m crypto_backtester.scripts.ingest_binance_5m \
  --symbol BTCUSDT \
  --start 2024-08-31 --end 2025-08-31 \
  --sleep 0.2
```

적재 확인(예상치: 365일 × 24h × 12 = **105,120**):

```bash
mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASS" -e "
SELECT COUNT(*) AS n_5m
FROM econ_sim.bars b
JOIN econ_sim.asset a USING(asset_id)
WHERE a.symbol='BTCUSDT' AND b.res='5m'
  AND b.ts >= '2024-08-31 00:00:00' AND b.ts < '2025-08-31 00:00:00';"
```

### 3-2) 1일봉 리샘플

```bash
python -m crypto_backtester.scripts.resample_to_1d \
  --symbol BTCUSDT \
  --start 2024-08-31 --end 2025-08-31
```

카운트 확인(예상치 **365**):

```bash
mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASS" -e "
SELECT COUNT(*) AS n_1d
FROM econ_sim.bars b
JOIN econ_sim.asset a USING(asset_id)
WHERE a.symbol='BTCUSDT' AND b.res='1d'
  AND b.ts >= '2024-08-31 00:00:00' AND b.ts < '2025-08-31 00:00:00';"
```

### 3-3) 품질 점검(QC)

```bash
python -m crypto_backtester.scripts.qc_bars \
  --symbol BTCUSDT --res 5m \
  --start 2024-08-31 --end 2025-08-31

python -m crypto_backtester.scripts.qc_bars \
  --symbol BTCUSDT --res 1d \
  --start 2024-08-31 --end 2025-08-31
```

---

## 4) 백테스트 실행(산출물은 로컬 `experiments/`)

```bash
# SMA Cross
python -m crypto_backtester.scripts.run_backtest \
  --symbol BTCUSDT --resolution 5m \
  --start 2024-08-31 --end 2025-08-31 \
  --strategy sma_cross --sma-short 20 --sma-long 60 \
  --start-cash 10000 \
  --auto-report \
  --exp-dir experiments/2025-08-crypto-btcusdt-v01-baseline \
  --notes "v0.1 baseline: SMA20/60"

# SMA+MACD+ATR
python -m crypto_backtester.scripts.run_backtest \
  --symbol BTCUSDT --resolution 5m \
  --start 2024-08-31 --end 2025-08-31 \
  --strategy sma_macd_atr \
  --sma-short 20 --sma-long 60 \
  --macd-fast 12 --macd-slow 26 --macd-signal 9 \
  --atr-n 14 --atr-k 3.0 \
  --start-cash 10000 \
  --auto-report \
  --exp-dir experiments/2025-08-crypto-btcusdt-v01-sma_macd_atr \
  --notes "baseline run"
```

생성물(각 run):

```
experiments/<EXP>/runs/<run_id>/
  ├─ equity.csv
  ├─ orders.csv
  ├─ summary.json
  ├─ params.yaml  # PyYAML 없으면 params.json
  └─ figures/
      ├─ equity.png
      └─ drawdown.png
```

---

## 5) 파티션 운용 팁

새로운 달이 시작되면 `pmax`를 **재조직(reorganize)** 하여 다음 월 파티션을 추가하는 것을 권장합니다. 예를 들어 **2025-09** 월 파티션을 추가하려면:

```sql
ALTER TABLE econ_sim.bars
REORGANIZE PARTITION pmax INTO (
  PARTITION p2025_09 VALUES LESS THAN ('2025-10-01 00:00:00'),
  PARTITION pmax     VALUES LESS THAN (MAXVALUE)
);
```

> 현재 제공된 파티션 스크립트는 2024-09 \~ 2025-08 + `pmax`를 정의합니다. 필요 시 위 방식으로 월별 파티션을 순차 추가하세요.&#x20;

---

## 6) 초기화/재시작(선택)

DB를 완전히 초기화하려면:

```bash
# 파괴적 작업: 주의
mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASS" -e "DROP DATABASE IF EXISTS econ_sim;"

# 재생성
mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASS" < "$MIG_DIR/0001_init.sql"
mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASS" < "$MIG_DIR/0002_partitions.sql"
```

* 0001: `econ_sim`/`asset`/`bars` 생성.&#x20;
* 0002: `bars` 월별 파티션 + `pmax`.&#x20;

---

## 7) 요약 규칙

* DB엔 **시장데이터(asset, bars)** 만 저장.
* 모든 **실험 결과는 로컬** `experiments/`에만 저장.
* `ts`는 **UTC**, 조회는 **end exclusive**.
* 품질 이슈는 **재적재로 자연 정정** 가능(UPSERT).

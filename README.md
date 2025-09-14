# 경제/투자전략 통합 시뮬레이터 (Economy Simulator)

여기는 여러 자산군의 **백테스트·이벤트(뉴스/지표) 충격 분석·상관관계·ML 예측**을 한 번에 실험하고 비교하도록 설계된 연구용 프레임워크입니다. 처음은 **비트코인(BTC) 백테스터**로 시작해 같은 규격으로 암호화폐 전반을 확장하고, 이후 **미국 주식(개별/ETF/지수) → 금/한국 주식 → 이벤트 랩 → 상관관계 → ML → RL(보조 도구)** 순서로 고도화합니다.

## 무엇을 목표로 하나요?
- **한 판 위에서 공정 비교**: 자산만 바뀌어도 동일한 규칙(수수료·슬리피지·리포트)로 전략 성능을 비교합니다.  
- **재현 가능한 연구**: 데이터 스키마·설정(YAML)·시드·실험 로그(MLflow)를 표준화해 결과를 다시 만들 수 있게 합니다.  
- **크로스에셋 통찰**: 암호화폐와 주식·금·환율을 한 파이프라인에 올려 **이벤트 충격**과 **레짐 변화**를 계량화합니다.

## 현재·예정 기능 한눈에
- **Crypto 백테스터(선행)**: BTC부터 시작해 ETH/주요 알트 확장. 데이터 해상도 **5m/1h/1d**, 슬리피지는 **상수값(bps)** 로 일관 적용.  
- **미국/한국 주식 & 금**: 주식은 **일봉(D1)** 기준, 분할/배당 정정과 거래 캘린더 반영. 금은 XAUUSD 또는 GLD를 사용.  
- **환율 데이터 적재**: USDKRW 등 주요 환율을 별도 피처로 저장해 포트폴리오·레짐 판정·헤지에 활용.  
- **이벤트 랩**: 자연어처리(OpenAI API 등)로 뉴스/지표를 토픽·감정·서프라이즈로 분류하고, 발표 전후 ±T 윈도에서 자산 반응을 분석.  
- **상관관계 엔진**: 롤링 상관(기본 일 단위)과 레짐(고/저 변동성) 분해, 필요 시 준실시간 업데이트.  
- **ML & RL**: LSTM을 베이스라인으로 다양한 예측법을 실험. RL은 **새 기술적 지표/재무특징 발굴**을 돕는 보조 도구로 사용.

### 데이터 해상도 & 슬리피지 요약
| 자산군 | 해상도 | 슬리피지(기본, bps) |
|---|---|---|
| 암호화폐 | 5m / 1h / 1d | 3–5 |
| 미국/한국 주식 | 1d | 1–2 / 2–4 |
| 금 · FX | 1d | 1–2 |
<!-- TODO: 자산/유동성 상태별 동적 슬리피지 모델로 확장 -->

## 설계 원칙
- **단일 스키마·단일 엔진·어댑터 구조**: 시장별 차이는 어댑터로 캡슐화하고, 코어 로직은 재사용합니다.  
- **단순한 실행 가정으로 빠른 커버리지**: 초기에 슬리피지는 **상수값**으로 고정(예: Crypto 3–5bps, US 1–2bps, KR 2–4bps, Gold/FX 1–2bps).  
- **검증 우선**: 데이터 무결성(중복/결측/역시계)·정정(분할/배당)·메타모픽 테스트(수수료/슬리피지 0 가정 일치)로 결과 신뢰도를 확보합니다.

---

## 시스템 개요 (Overview)

### 핵심 원칙
- **단일 엔진·단일 스키마·어댑터 구조**: 자산군/시장 차이는 어댑터로 캡슐화, 코어 로직 재사용 극대화  
- **재현 가능성**: 설정(YAML), 시드, 실험로그(MLflow) 표준화  
- **비교 가능성**: 슬리피지·수수료·리포팅 규칙 통일

### 데이터 해상도 & 기본 규칙
- **암호화폐**: 5m / 1h / 1d (24/7)  
- **주식(미국·한국)**: 1d (거래 캘린더·분할·배당 정정 반영)  
- **금**: XAUUSD 또는 GLD(1d)  
- **환율**: USDKRW 등 주요 통화 (1d) — 포트폴리오/레짐 판정/헤지에 피처로 사용  
- **슬리피지(상수값, bps)**: Crypto 3–5 / 미국주식 1–2 / 한국주식 2–4 / 금·FX 1–2

### 모듈 개요
- **Data Layer**: 시계열(OHLCV, 환율, 펀딩비/미결제약정(후속)), 주식 정정(분할·배당), 거래 캘린더 / 이벤트(뉴스·지표) 스키마(발표시각·토픽·감정·서프라이즈)  
- **Backtest Engine**: 이벤트 드리븐 `on_bar` 엔진(주문·수수료·슬리피지 **상수** 처리), MTF 지원(crypto), 주식은 D1  
- **Adapters**: Binance-Crypto / US-Equities / KR-Equities / Gold / FX  
- **Strategies**: 공통 인터페이스(`generate_signals` · `position_sizer` · `risk_overlays`), MTF 필터/리스크 오버레이  
- **Event Lab**: NLP(OpenAI API 등) 기반 토픽·감정·서프라이즈 분류, ±T 윈도 반응(수익·변동성·거래대금 등)  
- **Correlation**: 롤링 상관(기본 일 단위) · 레짐(고/저 변동성) 분해, 선택적 준실시간 업데이트(5–15분 리샘플)  
- **ML & RL**: ML= LSTM 베이스라인부터 확장 / RL= 새 기술적 지표·재무특징 규칙 후보 발굴(보조)  
- **Reports**: 전략/자산/이벤트별 비교 리포트 자동 생성(성과표·MDD·Turnover·비용 분해)

---

## 데이터베이스 (MySQL)

### 목적
- **메타데이터·카탈로그·실험/주문 로그**의 단일 진실원(Single Source of Truth).  
- 대시보드/리포트를 위한 **요약 지표·롤링 상관·이벤트 인덱스**의 빠른 조회.  
- 대용량 시계열(OHLCV)은 기본적으로 Parquet로 저장(**Hybrid 모드**). 필요 시 일부 해상도(예: 1d, 1h)를 MySQL에 동시 적재(**Canonical 모드**)하여 조회 최적화.

### 연결 설정
```ini
# .env (예시)
DB_HOST=localhost
DB_PORT=3306
DB_USER=econ_user
DB_PASS=***redacted***
DB_NAME=econ_sim
DB_POOL_SIZE=10
DB_CONNECT_TIMEOUT=10
````

```yaml
# /conf/base.yaml (발췌)
database:
  driver: mysql
  host: ${DB_HOST}
  port: ${DB_PORT}
  user: ${DB_USER}
  password: ${DB_PASS}
  name: ${DB_NAME}
  pool_size: ${DB_POOL_SIZE}
  connect_timeout: ${DB_CONNECT_TIMEOUT}
  timezone: "UTC"
```

### 스키마 개요

* **asset**: `asset_id` PK, `class`(crypto/us\_equity/kr\_equity/fx/metal), `symbol`, `exchange`, `currency`.
* **bars** *(선택적 동시 적재)*: `asset_id`, `ts(UTC)`, `resolution(ENUM: '5m','1h','1d')`, `open,high,low,close,volume`

  * **PK** `(asset_id, resolution, ts)` / **INDEX** `(ts)`
  * **파티션 권장**: `ts_date`(생성 칼럼=DATE(ts)) 기준 **월 단위 RANGE**
* **event**: `event_id` PK, `type`(macro/news/earnings/exchange), `release_time`, `topic`, `sentiment`, `surprise_value`, `surprise_pct`, `symbol?`, `source`.
* **corp\_action**: `asset_id`, `ex_date`, `type`(split/dividend), `ratio`, `amount`.
* **mkt\_calendar**: `market_code`, `date`, `is_open`, `open_time`, `close_time`, `notes`.
* **correlation\_cache**: `asof_date`, `window`(60D/252D...), `asset_id_a`, `asset_id_b`, `corr`, `regime_label`.
* **backtest\_run**: `run_id` PK, `strategy`, `params(JSON)`, `start_ts`, `end_ts`, `fees_bps`, `cost_bps`, `notes`.
* **실험 산출물(로컬)**: `experiments/<실험>/runs/<run_id>/` 폴더에 `equity.csv`, `orders.csv`, `summary.json`, `figures/*.png` 저장.

> **권장 사항**
>
> * MySQL **8.0+**, `sql_mode=STRICT_TRANS_TABLES`, 타임존 **UTC**.
> * `CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci`.
> * 조회 패턴에 맞춘 복합 인덱스: `(asset_id, resolution, ts)` / `(release_time, type)` 등.
> * 대용량 시계열은 Parquet가 **원본**, MySQL은 **인덱스/요약/로그** 중심(기본). 운영상 필요하면 `bars`도 동시 적재.

### 마이그레이션/백업

* **/db/migrations**에 스키마 변경 이력(Alembic/Flyway 등) 관리.
* 주기적 `mysqldump` + 월별 파티션 보관 전략.
* CI에서 마이그레이션 실행 → 리포트 스냅샷 검증.

---

## 설정 예시 (`/conf/base.yaml`)

```yaml
# 기본 수수료/슬리피지/해상도 설정
fees:
  maker_bps: 1.0
  taker_bps: 5.0

slippage_bps:
  crypto: 4        # 기본 3–5bps 범위. 심볼별 override 가능
  us_equities: 2   # 대형주 기준
  kr_equities: 3
  gold_fx: 2

resolutions:
  crypto: [5m, 1h, 1d]  # 암호화폐 다중 해상도
  equities: [1d]        # 미국/한국 주식은 일봉
  gold: [1d]
  fx: [1d]

calendars:
  us_equities: "XNYS"   # TODO: 프리/애프터마켓 후속
  kr_equities: "XKRX"

adjustments:
  equities:
    split: true
    dividend: "reinvest"   # 또는 "price-only"

database:
  driver: mysql
  host: ${DB_HOST}
  port: ${DB_PORT}
  user: ${DB_USER}
  password: ${DB_PASS}
  name: ${DB_NAME}
  pool_size: ${DB_POOL_SIZE}
  connect_timeout: ${DB_CONNECT_TIMEOUT}
  timezone: "UTC"
```

<!-- TODO: 시장/계정 티어별 수수료, 자산/상태별 동적 슬리피지, F/X 헤지 규칙 -->

---

## 리포지토리 구조 (Repository Structure)

```
/economy_simulator
  /adapters/           # 데이터 소스/시장 어댑터 (Binance, US, KR, Gold, FX)
  /engine/             # 공통 백테스터 엔진 (on_bar, 주문·수수료·슬리피지 상수)
  /strategies/         # 룰 시그널·사이징·리스크 오버레이
  /data_spec/          # 스키마·무결성 규칙, 캘린더/정정 정의
  /datasets/           # Parquet/Arrow (원본 데이터; LFS/DVC 또는 외부 스토리지)
  /event_lab/          # 이벤트 스키마·NLP 분류·±T 반응 분석
  /correlation/        # 롤링/레짐 상관 계산 + 업데이트 잡
  /ml/                 # 라벨링·피처·LSTM 베이스라인
  /rl/                 # 보조 탐색용 환경 (지표/재무특징 후보 발굴)
  /db/                 # MySQL DDL·ERD·마이그레이션 (Alembic 등)
  /conf/               # YAML 설정 (해상도·슬리피지 상수·수수료·캘린더·DB 등)
  /experiments/        # ★ 실험 단위 폴더(사고과정+결과를 묶는 핵심)
  /reports/            # 렌더링된 리포트(HTML/PNG/MD); GitHub Pages로 공개
  /notebooks/          # EDA/해설용 노트북(결과 스냅샷만 커밋)
  /scripts/            # CLI (ingest/run/report/scaffold)
  /tests/              # pytest (무결성·메타모픽·통계·성능)
  /docker/             # Dockerfile/compose
  /docs/               # 정적 사이트(MkDocs/Quarto) 소스 (선택)
  .github/
    ISSUE_TEMPLATE/    # 이슈 템플릿(실험 제안, 버그, 데이터)
    PULL_REQUEST_TEMPLATE.md
```

---

## 워크플로우 (간단)

1. **Ingest**: 어댑터로 시계열/이벤트 수집 → 정합성·정정 처리 → **Parquet 저장** + (선택) `bars` MySQL 동시 적재
2. **Backtest**: 공통 엔진 + 슬리피지/수수료 규칙 → **주문/체결 로그를 MySQL에 기록**
3. **Event Lab / Correlation**: 이벤트 반응·상관 구조 분석(이벤트/상관 캐시 **MySQL** 조회/적재)
4. **ML/RL**: 예측/아이디어 발굴 모듈로 확장
5. **Report**: 전략/자산/이벤트별 비교 리포트 자동 생성

---

## 실험 기록 정책 (GitHub Only)
- 모든 실험 기록은 **이 레포 안**에 보관합니다. 외부 사이트·GitHub Pages 비사용.
- 실험 단위 폴더는 `/experiments/YYYY-MM-<slug>/` 규칙을 따릅니다.
- 각 실험은 `card.md`(사고과정), `params.yaml`(설정), `runs.csv`(핵심 결과), `figures/`(그래프), `report.md`(요약)를 포함합니다.
**추적 연결**: `card.md` 하단에 `MLflow run_id`(있다면)와 **로컬 run_id**를 명시합니다.
- 루트 `EXPERIMENTS.md`에서 모든 실험을 표로 인덱싱하고, 최근 3개 실험은 README의 **Latest Experiments**로 노출합니다.

## Latest Experiments
- (예시) 2025-09: BTC SMA+MACD+ATR → `experiments/2025-09-crypto-btc-sma-macd-atr/report.md`
- (예시) 2025-09: ETH 외삽 + 이벤트 블랙아웃 30m A/B → `experiments/2025-09-eth-blackout-ab/report.md`

## 릴리스/태그 정책
- 프레임워크 릴리스: `vX.Y.Z` (엔진/구조 변화)
- 데이터/실험 스냅샷: `exp-YYYY-MM-<slug>-vN` 태그 후 **GitHub Release**에 결과 번들(그림/표/요약)을 첨부합니다.
- 큰 산출물(HTML/PNG/CSV)은 커밋 대신 **Release Assets** 또는 PR **Artifacts**로 보관합니다.

---

## 로드맵 (요약)

1. Crypto: BTC 백테스터 → 암호화폐 전반 확장
2. Equities: 미국 주식/ETF/지수(일봉, 정정/캘린더)
3. Metals & KR: 금(XAUUSD/GLD), 한국 주식 + 환율 적재(USDKRW)
4. Event Lab: 뉴스/지표 분류, ±T 반응 분석과 룰 A/B
5. Correlation: 롤링/레짐 상관, 기본 일 단위 업데이트(옵션: 준실시간)
6. ML: LSTM 베이스라인부터 확장
7. RL(보조): 지표/재무특징 규칙 후보 발굴

---

## 이 프로젝트가 아닌 것

* 즉시 실매매용 시그널 제공 도구가 아닙니다.
* 초기 단계에서는 **실행 현실(체결 큐/스프레드 동학)** 을 단순화합니다. 정밀 실행 모델은 후속 과제로 단계적 도입합니다.

## 누구에게 유용한가요?

* 여러 자산·여러 전략을 **같은 잣대**로 비교하려는 트레이더/리서처
* 이벤트 주도형 리스크와 레짐 변화를 **정량화**하고 싶은 분
* 실험과 리포트를 **재현 가능한 연구 자산**으로 남기려는 개발자

---

## 라이선스 / 기여

* **License**: TBD
* **Contributing**: 이슈 템플릿/PR 가이드 예정(테스트 통과·리포트 스냅샷 필수)

## 출처 (Sources)

* Marcos López de Prado, *Advances in Financial Machine Learning*
* Robert Pardo, *Evaluation and Optimization of Trading Strategies*
* Álvaro Cartea, Sebastian Jaimungal, José Penalva, *Algorithmic and High-Frequency Trading*
* Joel Hasbrouck, *Empirical Market Microstructure*
* Ian Goodfellow, Yoshua Bengio, Aaron Courville, *Deep Learning* (시계열 딥러닝 일반론)

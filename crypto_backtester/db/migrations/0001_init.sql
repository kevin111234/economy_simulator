-- 0001_init.sql
-- 목적: econ_sim 스키마 초기화 (시장데이터 전용: asset, bars, ingest_status)
-- 비고: 캔들 ts는 UTC (naive DATETIME). end exclusive 조회 관례.
--       파티셔닝은 0002_partitions.sql에서 수행.

SET NAMES utf8mb4;
SET time_zone = '+00:00';

CREATE DATABASE IF NOT EXISTS `econ_sim`
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE `econ_sim`;

-- A) 자산 메타 테이블 (확장 컬럼 포함)
CREATE TABLE IF NOT EXISTS `asset` (
  `asset_id`    INT NOT NULL AUTO_INCREMENT,
  `class`       VARCHAR(16)        NULL,  -- 'spot','perp' 등 (선택)
  `symbol`      VARCHAR(32)        NULL,  -- 예: 'BTCUSDT'
  `exchange`    VARCHAR(32)        NULL,  -- 예: 'Binance'
  `market`      ENUM('crypto','equity','etf','index','fx','commodity') NULL,
  `base_asset`  VARCHAR(16)        NULL,  -- 예: 'BTC'
  `quote_asset` VARCHAR(16)        NULL,  -- 예: 'USDT'
  `tick_size`   DECIMAL(18,8)      NULL,
  `lot_size`    DECIMAL(18,8)      NULL,
  `currency`    VARCHAR(16)        NULL,  -- 정산통화(예: 'USDT','USD')
  PRIMARY KEY (`asset_id`),
  UNIQUE KEY `uq_asset_symbol` (`symbol`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- B) 캔들 테이블 (메타 컬럼 포함)
CREATE TABLE IF NOT EXISTS `bars` (
  `asset_id`   INT                NOT NULL,
  `res`        ENUM('5m','1d')    NOT NULL,
  `ts`         DATETIME           NOT NULL,  -- UTC
  `ts_date`    DATE GENERATED ALWAYS AS (DATE(`ts`)) VIRTUAL,
  `open`       DOUBLE             NULL,
  `high`       DOUBLE             NULL,
  `low`        DOUBLE             NULL,
  `close`      DOUBLE             NULL,
  `volume`     DOUBLE             NULL,
  `provider`   VARCHAR(16)        NULL,      -- 'binance','resampler' 등
  `ingest_ts`  DATETIME           NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `adj_factor` DECIMAL(18,9)      NULL DEFAULT 1.000000000,  -- 주식 확장 여지
  `adj_close`  DECIMAL(24,10)     NULL,
  PRIMARY KEY (`asset_id`,`res`,`ts`),
  KEY `k_date` (`ts_date`),
  KEY `k_provider` (`provider`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- C) 적재 상태 테이블 (옵셔널 운영 로그)
CREATE TABLE IF NOT EXISTS `ingest_status` (
  `asset_id`    INT               NOT NULL,
  `res`         ENUM('5m','1d')   NOT NULL,
  `last_ts`     DATETIME          NULL,
  `last_run_ts` DATETIME          NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `status`      ENUM('ok','error') NOT NULL DEFAULT 'ok',
  `msg`         VARCHAR(255)      NULL,
  PRIMARY KEY (`asset_id`,`res`),
  CONSTRAINT `fk_ingest_asset`
    FOREIGN KEY (`asset_id`) REFERENCES `asset`(`asset_id`)
    ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

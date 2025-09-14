-- 0001_init.tmpl.sql — v0.2 baseline (split tables)
SET NAMES utf8mb4;
SET time_zone = '+00:00';

CREATE DATABASE IF NOT EXISTS `econ_sim`
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE `econ_sim`;

-- asset (메타)
CREATE TABLE IF NOT EXISTS `asset` (
  `asset_id`    INT NOT NULL AUTO_INCREMENT,
  `class`       VARCHAR(16)        NULL,
  `symbol`      VARCHAR(32)        NULL,
  `exchange`    VARCHAR(32)        NULL,
  `market`      ENUM('crypto','equity','etf','index','fx','commodity') NULL,
  `base_asset`  VARCHAR(16)        NULL,
  `quote_asset` VARCHAR(16)        NULL,
  `tick_size`   DECIMAL(18,8)      NULL,
  `lot_size`    DECIMAL(18,8)      NULL,
  `currency`    VARCHAR(16)        NULL,
  PRIMARY KEY (`asset_id`),
  UNIQUE KEY `uq_asset_symbol` (`symbol`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ingest_status (운영 로그)
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

-- crypto_bars (5m/1d)
CREATE TABLE IF NOT EXISTS `crypto_bars` (
  `asset_id`   INT              NOT NULL,
  `res`        ENUM('5m','1d')  NOT NULL,
  `ts`         DATETIME         NOT NULL,   -- UTC
  `ts_date`    DATE GENERATED ALWAYS AS (DATE(`ts`)) VIRTUAL,
  `open`       DOUBLE           NULL,
  `high`       DOUBLE           NULL,
  `low`        DOUBLE           NULL,
  `close`      DOUBLE           NULL,
  `volume`     DOUBLE           NULL,
  `provider`   VARCHAR(16)      NULL,
  `ingest_ts`  DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`asset_id`,`res`,`ts`),
  KEY `k_date` (`ts_date`),
  KEY `k_provider` (`provider`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- equity_bars (1d + 조정열)
CREATE TABLE IF NOT EXISTS `equity_bars` (
  `asset_id`   INT              NOT NULL,
  `res`        ENUM('1d')       NOT NULL,
  `ts`         DATETIME         NOT NULL,   -- UTC 자정 right-close
  `ts_date`    DATE GENERATED ALWAYS AS (DATE(`ts`)) VIRTUAL,
  `open`       DOUBLE           NULL,
  `high`       DOUBLE           NULL,
  `low`        DOUBLE           NULL,
  `close`      DOUBLE           NULL,
  `volume`     DOUBLE           NULL,
  `provider`   VARCHAR(16)      NULL,
  `ingest_ts`  DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `adj_factor` DECIMAL(18,9)    NULL DEFAULT 1.000000000,
  `adj_close`  DECIMAL(24,10)   NULL,
  PRIMARY KEY (`asset_id`,`res`,`ts`),
  KEY `k_date` (`ts_date`),
  KEY `k_provider` (`provider`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- commodity_bars (1d)
CREATE TABLE IF NOT EXISTS `commodity_bars` (
  `asset_id`   INT              NOT NULL,
  `res`        ENUM('1d')       NOT NULL,
  `ts`         DATETIME         NOT NULL,
  `ts_date`    DATE GENERATED ALWAYS AS (DATE(`ts`)) VIRTUAL,
  `open`       DOUBLE           NULL,
  `high`       DOUBLE           NULL,
  `low`        DOUBLE           NULL,
  `close`      DOUBLE           NULL,
  `volume`     DOUBLE           NULL,
  `provider`   VARCHAR(16)      NULL,
  `ingest_ts`  DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`asset_id`,`res`,`ts`),
  KEY `k_date` (`ts_date`),
  KEY `k_provider` (`provider`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- fx_bars (1d)
CREATE TABLE IF NOT EXISTS `fx_bars` (
  `asset_id`   INT              NOT NULL,
  `res`        ENUM('1d')       NOT NULL,
  `ts`         DATETIME         NOT NULL,
  `ts_date`    DATE GENERATED ALWAYS AS (DATE(`ts`)) VIRTUAL,
  `open`       DOUBLE           NULL,
  `high`       DOUBLE           NULL,
  `low`        DOUBLE           NULL,
  `close`      DOUBLE           NULL,
  `volume`     DOUBLE           NULL,
  `provider`   VARCHAR(16)      NULL,
  `ingest_ts`  DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`asset_id`,`res`,`ts`),
  KEY `k_date` (`ts_date`),
  KEY `k_provider` (`provider`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

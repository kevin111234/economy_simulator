CREATE DATABASE IF NOT EXISTS econ_sim CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS econ_sim.asset (
  asset_id INT AUTO_INCREMENT PRIMARY KEY,
  class VARCHAR(16), symbol VARCHAR(32), exchange VARCHAR(32), currency VARCHAR(16),
  UNIQUE KEY uniq_symbol (symbol)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS econ_sim.bars (
  asset_id INT NOT NULL,
  res ENUM('5m','1d') NOT NULL,
  ts DATETIME NOT NULL,
  ts_date DATE AS (DATE(ts)) VIRTUAL,
  open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume DOUBLE,
  PRIMARY KEY (asset_id, res, ts),
  KEY idx_ts (ts),
  KEY idx_date (ts_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS econ_sim.backtest_run (
  run_id VARCHAR(64) PRIMARY KEY,
  symbol VARCHAR(32), res VARCHAR(8),
  strategy VARCHAR(64), params_json JSON,
  start_ts DATETIME, end_ts DATETIME,
  fee_bps DOUBLE, slip_bps DOUBLE,
  pnl DOUBLE, sharpe DOUBLE, mdd DOUBLE, trades INT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS econ_sim.orders (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  run_id VARCHAR(64), ts DATETIME, side VARCHAR(8),
  symbol VARCHAR(32), res VARCHAR(8),
  qty DOUBLE, price DOUBLE, fee_bps DOUBLE, slippage_bps DOUBLE,
  INDEX idx_run (run_id), INDEX idx_ts (ts)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

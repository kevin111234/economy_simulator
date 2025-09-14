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

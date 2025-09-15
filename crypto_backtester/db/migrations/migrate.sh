#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
MIG_DIR="$ROOT/crypto_backtester/db/migrations"
RENDER_DIR="$MIG_DIR/_rendered"

set -a && . "$ROOT/.env" && set +a
DB_NAME="${DB_NAME:-econ_sim}"
DB_HOST="${DB_HOST:?}"; DB_PORT="${DB_PORT:?}"
DB_USER="${DB_USER:?}"; DB_PASS="${DB_PASS:?}"

DROP=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --drop) DROP=1; shift ;;
    *) echo "usage: $0 [--drop]"; exit 1 ;;
  esac
done

mkdir -p "$RENDER_DIR/$DB_NAME"

render(){ sed "s/__DB_NAME__/${DB_NAME}/g" "$1" > "$2"; }

if [[ $DROP -eq 1 ]]; then
  mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASS" \
    -e "DROP DATABASE IF EXISTS \`$DB_NAME\`;"
fi

render "$MIG_DIR/0001_init.tmpl.sql"       "$RENDER_DIR/$DB_NAME/0001_init.$DB_NAME.sql"
render "$MIG_DIR/0002_partitions.tmpl.sql" "$RENDER_DIR/$DB_NAME/0002_partitions.$DB_NAME.sql"

mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASS" < "$RENDER_DIR/$DB_NAME/0001_init.$DB_NAME.sql"
mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASS" < "$RENDER_DIR/$DB_NAME/0002_partitions.$DB_NAME.sql"

# 검증
mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASS" -e "SHOW TABLES FROM \`$DB_NAME\`;"
mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASS" -e "
SELECT TABLE_NAME, PARTITION_NAME
FROM INFORMATION_SCHEMA.PARTITIONS
WHERE TABLE_SCHEMA='$DB_NAME'
  AND TABLE_NAME IN ('crypto_bars','equity_bars','commodity_bars','fx_bars');"
echo "OK: $DB_NAME initialized."

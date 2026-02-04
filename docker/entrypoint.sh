#!/usr/bin/env bash
set -euo pipefail

CRON_SCHEDULE="${CRON_SCHEDULE:-0 7 * * 1}"
REPORT_ARGS="${REPORT_ARGS:-}"
RUN_ON_START="${RUN_ON_START:-false}"

echo "[entrypoint] Iniciando container de relatórios"
echo "[entrypoint] Cron schedule: ${CRON_SCHEDULE}"
echo "[entrypoint] Report args: ${REPORT_ARGS}"

if [ "${RUN_ON_START}" = "true" ]; then
  echo "[entrypoint] Executando relatório na inicialização"
  bash -lc "cd /app && python run.py ${REPORT_ARGS}" || true
fi

CRON_FILE="/etc/cron.d/weekly-report"
echo "${CRON_SCHEDULE} root cd /app && python run.py ${REPORT_ARGS} >> /proc/1/fd/1 2>&1" > "${CRON_FILE}"
chmod 0644 "${CRON_FILE}"
crontab "${CRON_FILE}"

echo "[entrypoint] Cron instalado. Iniciando serviço..."
cron -f

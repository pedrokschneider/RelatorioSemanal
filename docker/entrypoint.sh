#!/usr/bin/env bash
set -euo pipefail

echo "[entrypoint] Iniciando bot Discord para relatórios"
echo "[entrypoint] Bot executará apenas quando solicitado via Discord"
echo "[entrypoint] Modo: serviço (monitoramento contínuo)"

# Executar o bot do Discord em modo serviço
# Se o bot sair, aguardar e tentar novamente
cd /app

while true; do
    echo "[entrypoint] Iniciando bot Discord em modo serviço..."
    python discord_bot.py --service || {
        echo "[entrypoint] Bot saiu com código $?. Aguardando 30 segundos antes de reiniciar..."
        sleep 30
    }
done

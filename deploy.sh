#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# ÚNICO CAMINO DE DEPLOY DEL BOT. No deployar a mano a otro servicio.
#
# Historia: había DOS servicios de bot en Cloud Run (agente-bot y agente-v4) y se
# deployaba al equivocado, así que el código nuevo nunca llegaba al bot vivo.
# Este script saca toda ambigüedad: actualiza el código de la rama correcta y
# deploya SIEMPRE al servicio que usa WhatsApp, agente-bot.
#
# Uso: cd ~/verifika && ./deploy.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# Rama de trabajo actual. Cuando se mergee a main, cambiar a "main".
RAMA="claude/interpreter-solver-pipeline-mdlynm"
# Servicio VIVO, el que usa el webhook de WhatsApp. NO cambiar sin repointar Meta.
SERVICIO="agente-bot"
REGION="southamerica-east1"

cd "$(dirname "$0")"

echo "==> Sincronizando código con la rama $RAMA (descarta cambios locales)..."
git fetch origin
git checkout "$RAMA"
git reset --hard "origin/$RAMA"

# Verificación dura: el archivo que rompió los deploys tiene que estar presente.
if [ ! -f app/logger.py ]; then
  echo "ERROR: falta app/logger.py. La copia quedó incompleta. Abortando deploy." >&2
  exit 1
fi

echo "==> Deployando al servicio $SERVICIO en $REGION..."
gcloud run deploy "$SERVICIO" --region "$REGION" --source .

echo "==> Listo. Deploy a $SERVICIO completo. Probá el bot."

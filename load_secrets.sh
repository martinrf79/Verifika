#!/bin/bash
export DEEPSEEK_API_KEY=$(gcloud secrets versions access latest --secret=deepseek-key)
export TELEGRAM_BOT_TOKEN=$(gcloud secrets versions access latest --secret=telegram-token)
export META_WHATSAPP_TOKEN=$(gcloud secrets versions access latest --secret=meta-whatsapp-token)
export ADMIN_TOKEN=$(gcloud secrets versions access latest --secret=admin-token)
export SENTRY_DSN=$(gcloud secrets versions access latest --secret=sentry-dsn)
export PROJECT_ID=memory-engine-v1
export USE_VERIFIKA=true
export VERIFIKA_SOLVER_PROVIDER=deepseek
export VERIFIKA_SOLVER_MODEL=deepseek-chat
export VERIFIKA_PROPOSER_PROVIDER=deepseek
export VERIFIKA_PROPOSER_MODEL=deepseek-chat
export VERIFIKA_CHECKER_PROVIDER=deepseek
export VERIFIKA_CHECKER_MODEL=deepseek-chat
export VERIFIKA_UMBRAL_CONFIANZA=0.7
export VERIFIKA_BLOQUEAR_CONTRADICHAS=true
# VERIFIKA_FALLBACK_MESSAGE se saco el 3-ago: el texto vive en la fuente
# (base_conocimiento.json, bloque mensajes) y no se pisa por env.

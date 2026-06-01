# Agente Multi-Canal v4

Bot de ventas conversacional para WhatsApp y Telegram.
Multi-tenant (cada cliente trae sus propias credenciales de Meta).
Sentry, idempotencia y health por tienda integrados.

## Cambios desde v3-fix

- **Multi-tenant WhatsApp**: el webhook resuelve la tienda por `phone_number_id`. Cada cliente tiene su propio token y verify_token.
- **Conector WhatsApp Meta directo** (reemplaza 360dialog).
- **Idempotencia**: si Telegram o Meta reenvían el mismo mensaje, no se procesa dos veces.
- **Sentry opcional**: si configurás `SENTRY_DSN`, los errores se capturan automáticamente.
- **Health por tienda**: `GET /admin/health/{tienda_id}` con header `X-Admin-Token`.
- **Script de onboarding**: `scripts/crear_cliente.py` da de alta una tienda nueva.
- **Plantillas CSV**: `templates/productos_template.csv` y `templates/faq_template.csv`.

## Limitación honesta de v4

Las **tools** del agente (`search_products`, `query_faq`, etc.) todavía leen del catálogo **default** de la tienda configurada en `TIENDA_ID`. Para clientes con catálogos distintos, en esta versión hay que **deployar una instancia separada por cliente**, o esperar v5 donde las tools se parametrizarán por tienda.

En la práctica esto significa que multi-tenant v4 ya sirve para:
- Tu tienda actual + tests internos
- Clientes que comparten catálogo (improbable)

Para el primer cliente real con catálogo propio: deployar Cloud Run aparte con su `TIENDA_ID` en env vars. Costo igual (Cloud Run free tier), un poco más de mantenimiento.

## Variables de entorno

```
# Negocio (default)
BUSINESS_NAME=Tienda Tecno
TIENDA_ID=tienda_principal

# GCP
GCP_PROJECT=memory-engine-v1

# LLM
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_MODEL=deepseek-chat

# Telegram (opcional, para tienda default)
TELEGRAM_TOKEN=xxx

# WhatsApp (opcional, solo si usás token global; en multi-tenant cada tienda tiene el suyo)
WHATSAPP_VERIFY_TOKEN=verify_global

# Admin
ADMIN_TOKEN=xxx-token-fuerte

# Sentry (opcional pero recomendado)
SENTRY_DSN=https://xxx@xxx.ingest.sentry.io/xxx
ENVIRONMENT=production
```

## Deploy

```bash
gcloud run deploy agente-bot \
  --source . \
  --region=southamerica-east1 \
  --project=memory-engine-v1 \
  --update-secrets=TELEGRAM_TOKEN=telegram-token:latest,DEEPSEEK_API_KEY=deepseek-key:latest,SENTRY_DSN=sentry-dsn:latest,ADMIN_TOKEN=admin-token:latest
```

## Alta de cliente nuevo

1. El cliente te pasa: `phone_number_id`, `access_token` de Meta, catálogo en CSV, FAQ en CSV.
2. Corrés:

```bash
python scripts/crear_cliente.py \
  --tienda_id "ferreteria_juan" \
  --nombre "Ferretería Juan" \
  --phone_id "1234567890" \
  --token "EAAxxxx..." \
  --verify_token "verify_juan_2026" \
  --catalogo data/clientes/juan/productos.csv \
  --faq data/clientes/juan/faq.csv
```

3. En Meta → WhatsApp → Configuration → Webhook configurás:
   - URL: `https://TU-CLOUD-RUN.run.app/webhook/whatsapp`
   - Verify token: el mismo que pasaste arriba
   - Suscribirse al campo `messages`

4. Probás mandando un mensaje al número del cliente.

## Health check por tienda

```bash
curl https://TU-CLOUD-RUN.run.app/admin/health/ferreteria_juan \
  -H "X-Admin-Token: TU-ADMIN-TOKEN"
```

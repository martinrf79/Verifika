# Agente Multi-Canal v4

> **PUERTA ÚNICA: el bloque 0 de `CLAUDE.md`.** Cualquier sesión —de cualquier
> modelo— entra por ahí antes de tocar nada. Este README explica el producto y
> el alta de clientes; **no** dice cómo se trabaja ni dónde está parado el
> sistema. Si algo de acá contradice al bloque 0, gana el bloque 0.

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

**El nombre del proveedor y del modelo NO se escriben acá.** Los define
`app/config.py` (`LLM_PROVIDER` y el `*_MODEL` que corresponda), y hay un candado
que lo verifica: `tests/test_documentos_no_mienten.py`. El motivo no es
prolijidad — este bloque configuraba durante meses un proveedor que el sistema ya
no usaba, así que quien seguía estas instrucciones arrancaba mal.

Para ver los valores reales y todas las variables disponibles, mirá
`app/config.py`: cada una está ahí con su default y su comentario.

```
# Negocio (default)
BUSINESS_NAME=Tienda Tecno
TIENDA_ID=tienda_principal

# GCP
GCP_PROJECT=memory-engine-v1

# LLM — el proveedor y el modelo salen de app/config.py.
# Acá solo va la CLAVE del proveedor que ese archivo declare.
LLM_PROVIDER=<ver app/config.py>
<PROVEEDOR>_API_KEY=xxx

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

**No se deploya a mano desde acá.** Hay un solo camino y está en `DEPLOY.md`: el
push a `main` dispara `.github/workflows/deploy.yml`, que corre la batería de
tests ANTES de deployar, o `./deploy.sh` desde Cloud Shell.

Este README no repite los secretos ni los flags del deploy a propósito: la línea
de `gcloud` que estaba acá nombraba secretos de un proveedor que ya no se usa, y
es exactamente el modo de falla que el candado de documentos previene. La lista
viva de secretos está en `deploy.yml`.

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

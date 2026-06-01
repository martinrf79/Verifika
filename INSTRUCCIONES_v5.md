# INSTRUCCIONES — Evolución de agente v4 a v5

Este zip contiene los archivos nuevos y modificados para sumar Verifika al agente sin romper lo que funciona.

---

## Qué hay adentro

```
CLAUDE.md                          ← Instrucciones persistentes para Claude Code (pegar en raíz)
app/
├── config.py                      ← MODIFICADO: agrega USE_VERIFIKA y mensaje fallback
├── core/
│   ├── agent.py                   ← MODIFICADO: fix del SYSTEM_PROMPT multi-tenant
│   └── orchestrator.py            ← MODIFICADO: integración Verifika detrás de flag
└── verifika/                      ← MÓDULO NUEVO
    ├── __init__.py
    ├── llm_adapter.py             ← Adaptador de modelo (cualquier provider)
    ├── proposer.py                ← Descompone respuesta en afirmaciones
    ├── checker.py                 ← Verifica afirmaciones contra evidencia
    └── pipeline.py                ← Orquesta Proposer + Checker + Router de Confianza
tests/
└── smoke_verifika.py              ← Test para validar antes de activar
```

---

## Pasos para instalar

### 1. Backup

Antes de tocar nada:

```bash
cd ~/agente-v4
git add -A
git commit -m "v4 estable, backup antes de evolucionar a v5"
git tag v4-stable
```

### 2. Pegar archivos nuevos

Copiar el contenido del zip a la raíz del proyecto. Los archivos que ya existen (`config.py`, `agent.py`, `orchestrator.py`) se sobrescriben. Los nuevos (`verifika/`, `tests/`, `CLAUDE.md`) se crean.

### 3. Variables de entorno

Agregar al `.env`:

```bash
# Verifika — empezar APAGADO en producción hasta validar
USE_VERIFIKA=false

# Configuración por rol (todos DeepSeek por default)
VERIFIKA_SOLVER_PROVIDER=deepseek
VERIFIKA_SOLVER_MODEL=deepseek-chat
VERIFIKA_PROPOSER_PROVIDER=deepseek
VERIFIKA_PROPOSER_MODEL=deepseek-chat
VERIFIKA_CHECKER_PROVIDER=deepseek
VERIFIKA_CHECKER_MODEL=deepseek-chat

# Umbral de confianza (0.0 a 1.0). Si menos del 70% de afirmaciones están
# soportadas, Verifika bloquea la respuesta y manda el fallback.
VERIFIKA_UMBRAL_CONFIANZA=0.7

# Si hay AUNQUE SEA una afirmación contradicha, bloquear sí o sí
VERIFIKA_BLOQUEAR_CONTRADICHAS=true

# Mensaje cuando se bloquea
VERIFIKA_FALLBACK_MESSAGE=No tengo esa información confirmada en el catálogo. Dejame consultar y te confirmo en breve.
```

### 4. Correr el smoke test

```bash
# Asegurarse de tener DEEPSEEK_API_KEY exportada
export $(cat .env | xargs)

# Correr el test (no toca Firestore, usa evidencia mockeada)
python -m tests.smoke_verifika
```

Si los cuatro tests pasan, Verifika funciona. Si alguno falla, revisar logs.

### 5. Probar en local SIN activar

```bash
uvicorn app.main:app --reload --port 8080
```

Mandar un mensaje por Telegram. Debe comportarse exactamente igual que v4 (porque USE_VERIFIKA=false).

### 6. Activar Verifika en local

Cambiar en `.env`:

```bash
USE_VERIFIKA=true
```

Reiniciar el servidor. Probar consultas que sabés que son correctas y consultas donde podría inventar (ejemplo, preguntar por un producto que no existe). Verificar logs.

### 7. Deploy a Cloud Run

**Solo cuando local pase bien.** Subir las variables de entorno al servicio Cloud Run desde la consola o con `gcloud run services update`.

Sugerencia: arrancar con USE_VERIFIKA=false en producción. Hacer deploy con todo el código nuevo pero el flag apagado. Validar que Telegram sigue funcionando. RECIÉN AHÍ prender el flag.

---

## Cómo desactivar todo si algo se rompe

Cambiar en Cloud Run la variable `USE_VERIFIKA` a `false` y reiniciar. El sistema vuelve al comportamiento v4 instantáneamente. No hay que revertir código.

---

## Qué NO se tocó

- `app/main.py` — sin cambios
- `app/core/tools.py` — sin cambios
- `app/core/tools_context.py` — sin cambios
- `app/core/guardian.py` — sin cambios (sigue funcionando como red de seguridad estructural)
- `app/connectors/*` — sin cambios
- `app/storage/*` — sin cambios
- `requirements.txt` — sin cambios (Verifika usa las mismas libs que ya tenés)
- `data/`, `templates/`, `scripts/` — sin cambios

---

## Próximos pasos sugeridos

1. Validar Verifika con clientes reales en Telegram (USE_VERIFIKA=true)
2. Tunear `VERIFIKA_UMBRAL_CONFIANZA` según resultados
3. Revisar el código del generador de videos y decidir si lo refactorizamos para que use Verifika
4. Armar el archivo de arquitectura formal completo con diagrama

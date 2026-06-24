# Resumen para el nuevo chat — 24-jun-2026

Handoff de dónde quedamos. Si arrancás un chat nuevo, leé esto y el bloque
"ESTADO ACTUAL" del `CLAUDE.md`. Con eso alcanza para no re-equivocarse.

---

## Qué se hizo en esta sesión

1. **Auditoría completa del sistema** (`MAPA_SISTEMA.md`). Hallazgo: había cuatro
   caminos completos compitiendo en el orchestrator y ~70 flags que se pisan. La
   arquitectura de dos cañerías que quiere Martín YA existe y se llama
   `camino_nuevo`. El intérprete bueno es `interpretador.py`; `comprension.py`
   está muerto.

2. **Modo de prueba del intérprete** (`app/core/interprete_libre.py`, flag
   `SOLO_INTERPRETE` default on). Apaga de una los ~70 flags y deja un solo
   camino: intérprete + solver libre + memoria, con un eco que muestra qué
   entendió el intérprete. Para volver al sistema viejo: `SOLO_INTERPRETE=false`.

3. **Se ordenó Cloud Run** (era la causa raíz del día perdido):
   - Había DOS servicios de bot: `agente-bot` (vivo, lo usa WhatsApp) y
     `agente-v4` (fantasma). Se deployaba a `agente-v4`, por eso el código nunca
     llegaba al bot. **`agente-v4` se eliminó.**
   - `video-engine` (generador de videos) quedó apagado, no borrado.
   - Carpeta única `~/verifika`, atajo `agente`, deploy único `./deploy.sh`
     (fuerza rama y servicio correctos, verifica que no falte `app/logger.py`,
     que fue el archivo que rompió varios deploys por una copia desincronizada).

4. **Bug del bot resuelto.** Tiraba "problema técnico" porque el servicio tenía
   `LLM_PROVIDER=gemini` con clave vencida (401). Se forzó `LLM_PROVIDER=deepseek`.
   El bot ahora anda y corre el modo `SOLO_INTERPRETE`.

---

## Estado del bot ahora

- Vivo en `agente-bot`, corriendo `interprete_libre` (SOLO_INTERPRETE on).
- Intérprete y solver en DeepSeek. WhatsApp y Telegram entran por el mismo
  `process_message`.
- Tienda real: `TIENDA_ID=verifika_prod`, catálogo de 880 productos.

---

## La config de producción (lo que tiene Cloud Run)

El servicio `agente-bot` tiene ~70 variables de entorno con flags prendidos
(`CAMINO_NUEVO=true`, `DIRECTOR_LLM=true`, `PROVIDER=true`, etc.). **Hoy NO
importan**: `SOLO_INTERPRETE` los saltea a todos. Son ruido que hay que bajar al
código en el próximo paso. Secretos: la mayoría en Secret Manager; quedaron en
texto plano `MP_ACCESS_TOKEN` y `OPENAI_API_KEY` (ROTAR).

---

## Próximos pasos, en orden

1. **Bajar la config al código.** Que `config.py` tenga la config buena por
   default y el servicio solo lleve secretos + `TIENDA_ID`. Mata para siempre el
   "la nube deriva sola". Después, limpiar las ~70 env del servicio.
2. **Validar la interpretación** chateando casos difíciles y leyendo el eco.
   Mejorar `interpretador.py` donde falle.
3. **Adoptar la cañería secundaria completa** (`camino_nuevo`) cuando el
   intérprete esté fino, para tener el sistema entero verificado.
4. **Seguridad:** rotar `MP_ACCESS_TOKEN` y `OPENAI_API_KEY`, moverlos a Secret
   Manager.
5. **Costo Cloud Run:** verificar `min-instances=0` en `agente-bot` y apagar
   `DIAG_TRACE` (logueo verboso). Tres servicios y deploys repetidos de hoy
   inflaron el gasto puntual.

---

## Formato de trabajo (deploy + verificación), probado verde 24-jun

El pipeline profesional quedó andando:

1. Claude escribe el código y lo pushea a la rama.
2. GitHub Actions deploya solo a `agente-bot` con Workload Identity Federation
   (sin clave descargable; la SA es `github-deployer@memory-engine-v1`).
3. Claude lee el resultado de la corrida por el MCP de GitHub y confirma el verde
   o arregla el error. Sin gcloud a mano, sin posibilidad de errar el servicio.

Respaldo manual: `./deploy.sh` desde `~/verifika`. El workflow ignora cambios
solo de `.md` (no deploya de gusto). Martín se dedica a diseñar el bot; los
deploys los maneja y verifica Claude.

---

## Reglas de oro para NO volver al caos

- **Un solo servicio de bot:** `agente-bot`. Nunca crear otro.
- **Un solo deploy:** CI por push (preferido) o `./deploy.sh` (respaldo). Nunca un
  `gcloud run deploy` suelto a otro servicio.
- **Un solo intérprete:** `interpretador.py`.
- **Un solo LLM:** DeepSeek. Gemini queda prohibido salvo OK explícito de Martín.
- **El repo manda.** La meta es que la config viva en el código, no en env de la
  nube que derivan entre sesiones.
- **Consolidar, no agregar.** Por cada cosa nueva que se prende, se apaga o borra
  una vieja.

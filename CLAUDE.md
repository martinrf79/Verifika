# CLAUDE.md — Instrucciones persistentes del proyecto

Este archivo es leído automáticamente por Claude Code al iniciar cada sesión.
No borrarlo, no moverlo.

---

## Diagnóstico obligatorio antes de tocar nada (Martín, 21-jun-2026)

Este proyecto acumuló dos arquitecturas en paralelo, dos interpretadores y unos
cuarenta flags que se pisan. Para no repetir el error de parchar a ciegas:

1. **Cada dos o tres sesiones, o ante cualquier diagnóstico, primero mapear el
   sistema completo:** qué flags existen en `app/config.py`, qué camino corre de
   verdad en producción (pedir a Martín la salida de `gcloud run services
   describe`), y qué módulos están vivos vs muertos. NO opinar sobre el flujo sin
   haber leído esto.
2. **Regla de consolidación, reemplaza al reflejo de agregar:** por cada cosa
   nueva que se prende, se BORRA o apaga una vieja. Prohibido sumar otra capa o
   flag "en paralelo por las dudas". El problema histórico fue agregar y nunca
   sacar. El método ahora es al revés.
3. **Un test que no corre sobre el código de producción no vale.** Los bancos en
   `scripts/` tienen su propia copia del prompt y no prueban el path vivo. Antes
   de confiar en un número, verificar que el banco llame al código real.
4. **La config manda desde un solo lugar.** Los flags viven en Cloud Run y derivan
   entre sesiones. Tender a que el repo sea la única fuente de verdad de qué camino
   está prendido.

Objetivo principal que no se pierde: que el sistema INTERPRETE bien la conversación
en turnos largos, con negaciones y cambios de decisión, y responda en consecuencia.
Eso primero. Después enriquecer Firestore. El resto es ruido.

---

## Identidad del proyecto

Nombre: agente-v4 (en evolución a v5)
Propietario: Martín
Ubicación: este directorio es la raíz del proyecto. Siempre trabajar acá, no salir.
Lenguaje principal: Python 3.11+
Framework backend: FastAPI
Deploy: Google Cloud Run, región southamerica-east1
Base de datos: Google Firestore
LLM principal: DeepSeek (deepseek-chat) — extremadamente económico
LLM secundarios: Groq (fallback), Claude/Gemini (solo en Checker cuando haya cliente pagando)

---

## Norte del proyecto — el objetivo manda sobre los reflejos

La meta es UNA: un producto **VENDIBLE que funcione a escala real y esté DEPLOYADO** en producción. Eso es lo único que cuenta como "funciona".

- "Funciona" NO significa "no se rompe con 50 productos" ni "demostra sin crashear". Un prototipo que se exhibe no es la meta. Si anda a 50 y no a más, no anda.
- Toda decisión se mide contra ese objetivo, no contra "es seguro" ni "no toca lo que hay". La pregunta de cada paso es: ¿esto acerca a vender a escala, o solo protege el estado actual?
- La cautela de abajo es un cinturón, no el destino. Es una restricción al servicio del Norte, NUNCA una excusa para no avanzar hacia la meta.
- No ofrecer la opción segura por default. Ofrecer la que acerca al objetivo y marcar el riesgo aparte; decide Martín.
- Cuando una orden directa de Martín choque con un reflejo de cautela, NO gana el reflejo por descarte: se le plantea el riesgo y se respeta su decisión. Su intención es simple y sin doble fondo, que todo funcione para venderse. Guiarlo hacia esa meta en todo momento.
- PRIORIDAD ACTUAL concreta (de Martín, no posponer ni reinterpretar): el catálogo de 2000 productos REAL de producción, vendible, con FAQs enriquecidas, NO el fixture sintético verifika_2k. "Real" = calidad producción, realista y vendible, que el ASISTENTE construye (marcas y modelos que existen, precios plausibles, FAQ rica); NO significa que Martín cargue 2000 productos. Construirlo, no pedirle los datos. Solo preguntar si tiene un export real que quiera usar; si no, generarlo igual. Ver HANDOFF.md.

---

## Regla de oro

**No romper lo que funciona, pero al servicio del Norte de arriba, nunca como excusa para no avanzar.** Este código está en producción con Telegram y va a integrarse con WhatsApp Cloud API directo. Antes de modificar cualquier archivo existente:

1. Leer el archivo completo, no solo la parte a tocar.
2. Si la modificación es invasiva, crear archivo nuevo en paralelo en lugar de editar.
3. Toda funcionalidad nueva detrás de **feature flag** en `app/config.py`.
4. Si un cambio no puede activarse/desactivarse con un flag, no es un cambio, es una refactorización y requiere confirmación explícita de Martín.

---

## Arquitectura objetivo (en construcción)

Estamos evolucionando de **producto único** a **plataforma multi-producto**.

Capas:

**Capa A — Plataforma (módulo `app/verifika/`)**
Núcleo verificable, reutilizable entre productos. Contiene:
- Adaptador de modelo LLM (cualquier provider detrás de una interfaz)
- Solver (genera respuesta inicial)
- Proposer (descompone respuesta en afirmaciones atómicas)
- Checker (valida cada afirmación contra evidencia)
- Citador (vincula afirmaciones a IDs/fragmentos de fuente)
- Router de Confianza (decide responder o no según score)

**Capa B — Productos**
- Producto 1: Asistente de Ventas Verificado (este repo, agente WhatsApp/Telegram)
- Producto 2: Generador de Videos Verificado (otro repo, pendiente de integrar)
- Productos futuros: se suman como capa fina arriba de Verifika

---

## Reglas técnicas no negociables

0. **Identidad ≠ Compatibilidad. El LLM nunca inventa identidad.** (Martín, 15-jun)
   - Identidad ("¿existe este producto?") la decide UNA sola función determinista, el CERTIFICADOR (`app/core/certificador.py`), con tres veredictos de primera clase: `exists`, `ambiguous`, `not_found`. `not_found` NO es un error, es un resultado válido y exitoso.
   - El LLM puede razonar, comparar, recomendar y cerrar, pero NUNCA decide que un producto existe. Ante `ambiguous` está obligado a preguntar, no a elegir.
   - **Toda herramienta comercial (ficha, calculadora, tarifa, cierre) consume un `product_id` CERTIFICADO; ninguna opera sobre un producto inferido.**
   - Compatibilidad ("¿este producto sirve para aquel?") es otro eje: respuesta razonada del LLM con ficha y FAQ. No se mezcla con identidad.
1. **Multi-tenant siempre.** Toda función que toca datos debe recibir o resolver `tienda_id`. Nunca asumir tienda default fuera del orchestrator.
2. **El LLM nunca decide qué tienda usar.** Eso lo resuelve el backend por `phone_number_id` o canal.
3. **Anti-alucinación vive en dos lados:** prompt (línea uno) + código (línea cero, no negociable). El código siempre puede invalidar lo que dice el modelo.
4. **Citas verificadas mecánicamente.** Si una afirmación menciona un producto, debe poder mapearse a un ID en Firestore. Si no se puede, se descarta.
5. **Observabilidad obligatoria.** Cada engranaje loguea con `trace_id` consistente. Sin logs no se hace deploy.
6. **DeepSeek por default.** No usar Claude/Gemini/OpenAI sin permiso explícito de Martín (cuestan plata, DeepSeek no).

---

## Reglas de comportamiento para Claude Code

1. **Trabajar siempre en este directorio.** Si por algún motivo te encontrás en otra carpeta, volver acá con `cd` antes de hacer cualquier cosa.
2. **No tocar `data/productos.json` ni los CSV de `templates/`** sin permiso.
3. **No modificar `requirements.txt`** sin avisar primero qué dependencia se suma y por qué.
4. **No correr `gcloud deploy` ni comandos de producción** sin confirmación explícita.
5. **Antes de cada cambio importante**, mostrar a Martín:
   - Qué archivos van a tocarse
   - Qué se rompería si el cambio sale mal
   - Cómo se activa/desactiva el cambio (feature flag)
6. **Respuestas concisas, sin corchetes ni paréntesis innecesarios** (Martín usa lector de texto a voz).
7. **Español argentino, voseo.**

---

## Estado actual de la evolución

- [x] Análisis del código v4 completo
- [ ] **Paso 1:** Adaptador de modelo LLM (`app/verifika/llm_adapter.py`)
- [ ] **Paso 2:** Módulo Verifika con Proposer y Checker (`app/verifika/`)
- [ ] **Paso 3:** Integración al orchestrator detrás de feature flag `USE_VERIFIKA`
- [ ] **Paso 4:** Fix del SYSTEM_PROMPT congelado (multi-tenant correcto)
- [ ] **Paso 5:** Evaluación del generador de videos (pendiente código)

---

## Comandos útiles

```bash
# Activar entorno (ajustar al de Martín)
source venv/bin/activate

# Correr local
uvicorn app.main:app --reload --port 8080

# Tests locales antes de deploy
python -m pytest tests/ -v

# Deploy a Cloud Run (NO ejecutar sin permiso). UN solo camino: ./deploy.sh
# Deploya SIEMPRE al servicio vivo agente-bot, nunca a mano a otro servicio.
cd ~/verifika && ./deploy.sh
```

## Infraestructura Cloud Run — UN solo servicio de bot (24-jun-2026)

Regla dura, nació de un día entero perdido: en el proyecto memory-engine-v1
había DOS servicios de bot, `agente-bot` y `agente-v4`, y se deployaba al
equivocado, así que el código nuevo nunca llegaba al bot vivo.

- **Servicio VIVO del bot: `agente-bot`.** Es el que usa el webhook de WhatsApp.
  Es el ÚNICO que se deploya. `agente-v4` se eliminó.
- **`video-engine`** es el otro producto, el generador de videos. Queda APAGADO
  (min-instances 0), NO se elimina.
- **Deploy: siempre `./deploy.sh`** desde `~/verifika`, nunca un `gcloud run
  deploy` a mano. El script fuerza la rama correcta y el servicio correcto.
- Carpeta única de trabajo en Cloud Shell: `~/verifika` (clon limpio de la rama).
  El atajo `agente` te para ahí.

---

## Si Claude Code se pierde

Si algo se desconecta, se reinicia la sesión, o hay duda sobre el contexto:
1. Releer este `CLAUDE.md`
2. Verificar que estamos en la carpeta correcta con `pwd`
3. Si no estamos, `cd` a la raíz del proyecto
4. Mirar el último commit con `git log -1` para entender dónde quedamos
5. NO inventar contexto. Si algo no está claro, preguntar a Martín.

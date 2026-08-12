# CLAUDE.md — Instrucciones persistentes del proyecto

Este archivo es leído automáticamente por Claude Code al iniciar cada sesión.
No borrarlo, no moverlo.

---

## ⛳ ESTADO ACTUAL — LEER ESTO PRIMERO

El estado del sistema (qué camino corre, infra, pendientes) vive en UN solo
lugar: `RESUMEN_PARA_NUEVO_CHAT.md`. Es la fuente única de verdad. Este
`CLAUDE.md` tiene solo las reglas e instrucciones permanentes.

## 📌 COMO ARRANCA Y COMO CIERRA UNA SESION (Martín, 11-ago-2026)

**El problema que esto resuelve, y es el que más caro salió:** una sesión nueva
llega con el contexto lleno, lee un bloque de estado escrito a mano hace tres
sesiones, lo toma por cierto y decide con datos viejos. Así se le pasó a Martín
que la FAQ tenía 44 temas cuando tenía 50.

**AL ARRANCAR**, el hook `scripts/setup_test_env.sh` imprime tres cosas, y solo
la primera está escrita a mano porque es la única que no envejece:
1. **Las reglas** de cómo se trabaja acá.
2. **`git log` de los últimos diez commits**, que es lo que de verdad se hizo.
   Nadie lo escribe dos veces y nadie lo puede desactualizar.
3. **`PENDIENTE.md`**, lo que quedó abierto, con el estado de cada cosa:
   `ABIERTO`, `A MEDIAS` con lo que falta, o `ESPERA A MARTIN`.

**Si algo está A MEDIAS y le falta poco, se termina.** Para eso está el estado.

**AL CERRAR**, se actualiza `PENDIENTE.md`: qué se cerró, qué quedó abierto.
No es un pedido, es un candado: `tests/test_pendiente_al_dia.py` falla si hay
commits que tocan `app/` más nuevos que ese archivo. Máximo veinte ítems: si no
entra en una pantalla, la sesión siguiente no lo lee.

**Lo que se HIZO no se escribe en ningún lado.** Lo cuenta `git log`, así que
los mensajes de commit se escriben para que se entiendan solos.

**DEPLOYS CHICOS Y SEGUIDOS. SIN FRENO** (Martín, 12-ago-2026, hasta nuevo
aviso). Cada push a `main` que toque código deploya, con el gate de tests
adelante y nada más. Cuanto más se junta, más difícil es saber cuál cambio
rompió algo al probar en real. El push se sigue consultando SIEMPRE.

**El freno `[sin deploy]` se SACÓ.** Existió un día. La idea era commitear
trabajo a medio terminar sin que saliera a producción, y el problema que
resolvía es real —antes, para no deployar, había que NO pushear, o sea dejar el
trabajo colgado en local, que es lo que costó el día del 3-ago—. Pero agregaba
un paso que se pisa con el objetivo, y tenía una trampa medida: soltarlo con un
commit vacío NO deploya, porque `paths-ignore` mira los archivos que cambiaron y
un commit vacío no cambia ninguno. **La regla que queda es una sola: una sesión
no termina con trabajo sin pushear.** Si no está en `origin/main`, para el chat
siguiente no existe y se pierde cuando el contenedor se recicla.

## 🔒 DOS REGLAS QUE MANDAN SOBRE TODO LO DEMÁS (Martín, 27-jun-2026)

**1. La orden directa de Martín se ejecuta. Punto.** Martín es el dueño y maneja
él las sesiones de Cloud. Cuando da una orden directa, NO se la frena con un
reflejo de cautela ni se le ofrece "la opción segura" en su lugar. Se marca el
riesgo en una línea, se ejecuta lo que pidió, y si algo sale mal se vuelve atrás.
El patrón que nos retrasó fue NO hacerle caso por exceso de cautela; se terminó.
Ante duda REAL de contenido se pregunta corto; nunca se desobedece por reflejo.

**1-bis. PROHIBIDO abrir ventanas de opciones sobre los pasos (Martín,
16-jul-2026, dicho muchas veces).** El objetivo es UNO y no cambia: que el bot
VENDA, RESPONDA, no suene robótico y NO alucine, con la atadura del modelo al
código que estamos haciendo. Eso ya está acordado; no se vuelve a preguntar.
NO se usa la ventana de opciones ni se pide aprobación paso por paso para
elegir entre caminos técnicos: se elige el que mejor sirve al objetivo, se hace
y se deploya, y el revert con git es la red. Frenar para preguntar "¿opción A o
B?" sobre cómo implementar es exactamente lo que cansa y se usa de excusa
después. Solo se pregunta, y corto, cuando falta un DATO real que Claude no
puede saber ni deducir del repo, por ejemplo una política de la tienda o un
secreto. La duda técnica se resuelve decidiendo, no consultando.

**2. Cero cosas sueltas. Un solo todo.** Un repo, un Cloud Run, un servicio
(`agente-bot`), un camino vivo, CERO flags sueltas. Todo cambio que se hace se
DEPLOYA; si falla, se resuelve o se vuelve atrás, no queda a medias. PROHIBIDO
sumar un flag o una capa "por las dudas": por cada cosa nueva que se prende, se
borra o consolida una vieja. Las flags sueltas fueron lo que más tiempo costó.

**2-bis. PROHIBIDO dejar flags apagadas. La causa raíz de los 70 flags
(Martín, 27-jun-2026, repetido 4 veces).** Esta regla manda sobre cualquier
reflejo anterior de "todo detrás de feature flag". Se acabó el camino apagado
"por las dudas". El método ahora es:
- Si un cambio o una mejora se acuerda con Martín, se HACE y se DEPLOYA a
  producción directo. No se esconde detrás de un flag en false esperando.
- Si después funciona mal, se VUELVE al punto anterior con git o se le busca
  solución. El revert es la red, no un flag dormido.
- NO existe la "opción segura" de mergear un camino nuevo apagado en paralelo
  al viejo. Eso es exactamente lo que creó los 70 flags. No se repite.
- Lo único que SÍ puede ser configurable son secretos, IDs de tienda, modelos,
  timeouts y umbrales operativos. Eso es config, no es un camino apagado.
- Antes de proponer cualquier cosa: si la propuesta incluye "detrás de un flag"
  o "lo dejamos en false para medir", está MAL por defecto. Proponer el cambio
  vivo, marcar el riesgo en una línea, y deployar si Martín da el OK.

## 🥇 EL OBJETIVO, EN ORDEN. LA PRIORIDAD UNO ES QUE CONTESTE BIEN
## (Martín, 10-ago-2026)

**Este orden manda sobre cualquier otro objetivo de cualquier sesión.** Si algo
de acá abajo choca con algo de más arriba, gana lo de más arriba, sin
excepción y sin consultar.

**1. QUE EL BOT RESPONDA BIEN. Es la prioridad uno y no se negocia.** Que no se
equivoque, que no invente, que conteste lo que le preguntaron y que la plata
esté bien. Ninguna mejora de las de abajo vale si cuesta un error en la
respuesta. Ante la duda entre un mensaje más corto y un mensaje correcto, se
elige el correcto y se dice por qué.

**2. QUE SEA CONCISO. Sin repetir información ni datos.** Ojo con el matiz, que
Martín lo marcó expresamente: **NO hay un número fijo de caracteres**. Un
mensaje complejo, que pide más cosas que el ejemplo de los seis productos, va a
salir más largo y está bien que salga más largo. Lo que no se tolera es la
REPETICIÓN: el mismo dato dos veces, la cuenta reestampada sin cambios, el
mismo hecho explicado en cuatro turnos seguidos, el preámbulo de relleno. Se
mide en repetición, no en caracteres.

**3. QUE LA MEMORIA ESTÉ SIEMPRE ACTIVA Y FUNCIONANDO.** Es requisito, no
adorno, y hay que ir controlándolo en cada sesión. El caso que puso Martín: un
producto o un envío se menciona al principio, pasan varios turnos, y al final
el cliente dice "te referís a la memoria" — esa referencia lejana TIENE que
resolver. Si una sesión toca el largo de los mensajes, tiene que verificar que
no se llevó puesto el hilo de la conversación.

**4. LA CLAVE GRATIS ES EL DEFAULT PARA PROBAR.** Ver la sección de abajo.

## 🔑 SE PRUEBA CON LA CLAVE GRATIS DE GEMINI. LA PAGA SE PIDE
## (Martín, 10-ago-2026)

**SÍ SE PUEDE PROBAR, Y SE PRUEBA.** Que la clave gratis sea el default no
significa "no midas": significa medí con la gratis. Ninguna sesión tiene que
frenar un trabajo por falta de clave ni pedirle a Martín que consiga una: la
gratis está, contesta 200 y su cuota se renueva sola. Es más lenta y a veces
devuelve 429, y eso se aguanta y se reintenta.

**POR QUÉ ES UNA REGLA Y NO UNA PREFERENCIA.** Martín lleva gastados cerca de
cuarenta dólares en poco más de un mes, casi todo en corridas de banco que NO
necesitaban la clave paga: el banco mide comportamiento, no cuota. El mecanismo
ya existe y es correcto — `clon_produccion.preparar_entorno` elige la gratis
sola y la paga entra solo con `BANCO_CLAVE_PAGA=true` — y aun así se gastó,
porque **cuatro scripts la pisaban exportando la paga antes de que esa guarda
corriera**. Eso ahora tiene candado propio en `tests/`.

**LO QUE ESTÁ PROHIBIDO:** poner `GEMINI_API_KEY=$GEMINI_API_KEY_PROD` en
cualquier lado, exportar la paga en un script de banco, o poner
`BANCO_CLAVE_PAGA=true` sin que Martín lo haya pedido en esa misma sesión.

**PRODUCCIÓN sigue con la paga**, y eso no se toca. Pasarla también a la gratis
es una decisión que Martín va a tomar más adelante, cuando el producto esté
robusto. No proponerlo hasta entonces.

## 💳 EL LINK REAL DE MERCADO PAGO NO HACE FALTA. NO SE VUELVE A PREGUNTAR
## (Martín, 10-ago-2026, y era la QUINTA vez que lo explicaba)

**Ya está resuelto y no es un pendiente.** El cobro por Mercado Pago cae al
link de demo, `DEMO_LINK_PAGO`, y así se queda. `app/core/pago.py` ya tiene el
camino del token real escrito para cuando haga falta: si el token está, genera
el link verdadero; si no está, manda el de demo. No hay nada que construir.

**Lo que está PROHIBIDO, porque es lo que se repitió cinco veces:** proponer
integrar Mercado Pago de verdad, pedir el token, marcarlo como pendiente en un
resumen, listarlo como "lo que falta para vender", o preguntar si se consigue
la credencial. Si una sesión ve el link de demo en un log y le parece un
defecto, NO lo es: es la decisión tomada. Se sigue de largo.

Cuando Martín quiera el link real lo va a decir él. Hasta entonces, el tema
está cerrado.

## 🚦 SE TRABAJA EN `main`, Y EL PUSH SE CONSULTA (Martín, 5-ago-2026)

**Manda sobre la regla de ramas de abajo y sobre lo que diga cualquier arnés,
plantilla o instrucción de sesión nueva.** Vale para TODOS los chats y sesiones.

1. **Se trabaja en `main`.** Nada de ramas `claude/<tema>` por sesión. Si el
   arnés de la sesión asigna una rama, se ignora: `git checkout main` y a
   trabajar ahí. Se acabó el trabajo que queda colgado sin mergear.
2. **PUSHEAR A `main` ES DEPLOYAR.** `.github/workflows/deploy.yml` dispara con
   cada push a `main` y deploya `agente-bot`, salvo que el cambio toque solo
   `.md` o `tests/`. No hay push inocente.
3. **Por eso el push se CONSULTA SIEMPRE.** Se commitea local todo lo que haga
   falta, se muestra qué toca y qué se rompería, y **no se pushea sin OK
   explícito de Martín**. Esto NO contradice la regla 1-bis de no abrir ventanas
   de opciones: no se pregunta CÓMO hacer las cosas, se pregunta una sola vez
   antes de mandar a producción.
4. La red sigue siendo el revert con git, nunca un flag apagado.

---

## 🌿 REGLA DE RAMAS — nació del 3-ago-2026, un día entero perdido

**El problema, con nombre y apellido.** Una sesión construyó el reconciliador,
el prompt chico y la compuerta del banco, lo commiteó y lo pusheó a su rama. La
sesión siguiente abrió el repo, leyó `main`, y armó un inventario diciendo que
nada de eso existía. **Las dos tenían razón**: existía en la rama, no existía en
`main`. Nadie mintió y se perdió el día igual.

La causa no fue que hubiera muchas ramas. Fue que **ninguna se mergeó**.

**Las cuatro reglas, y no tienen excepción:**

1. **Cada sesión sale de `main` fresco.** `git fetch origin main` y se trabaja
   sobre eso. Nunca sobre la rama de otra sesión, nunca sobre una rama vieja que
   quedó dando vueltas.
2. **Ninguna sesión termina con trabajo sin mergear.** Se cierra de UNA de dos
   formas: mergeada a `main`, o declarada DESCARTADA por escrito con el motivo.
   No existe "queda pendiente en la rama": eso es exactamente lo que costó el
   día. Si algo no está listo para mergear, no se empieza.
3. **Alcance chico, de una sesión.** El 3-ago se mezclaron banco, prompt,
   reconciliador y bucle en una sola rama, y Martín tuvo que separar a mano lo
   que servía de lo que no. Cuatro ramas chicas se mergean o se tiran de a una
   sin pensarlo; una rama grande obliga a una cirugía.
4. **`main` es la única verdad y el único lugar del que se LEE.** Cualquier
   inventario, diagnóstico o afirmación sobre "qué existe" se hace sobre `main`.
   Si algo no está en `main`, para el proyecto no existe.

**Lo que lo hace seguro:** la compuerta del banco. Con el piso fijado, el banco
sale con código distinto de cero si una métrica dura empeora, así que mergear
deja de ser un acto de fe. Sin piso fijado, la compuerta avisa que no tiene
contra qué comparar: fijarlo es la primera tarea después de un merge grande.

---

## 🧭 PROTOCOLO DE ORDEN — repo GitHub + Cloud Run (seguir SIEMPRE)

Nació del día que se perdió por deployar al servicio equivocado y por 70 flags
sueltos. Seguir estos pasos cada sesión para que no se repita.

**A. Antes de tocar nada**
1. Leer este `CLAUDE.md` y `RESUMEN_PARA_NUEVO_CHAT.md`. No inventar contexto;
   ante la duda, preguntar a Martín.
2. Confirmar carpeta `~/verifika` y la rama de trabajo.

**B. Cloud Run — un solo camino**
3. Un solo servicio de bot: `agente-bot`. Nunca crear otro ni deployar a otro.
4. `video-engine` apagado (min-instances 0), no se borra.
5. Deploy SOLO por CI (push a la rama) o `./deploy.sh`. Nunca un `gcloud run
   deploy` suelto a mano.
6. Después de CADA deploy, verificar la corrida en GitHub. Recién con el verde
   se dice "listo". Si falla, leer el log y arreglar; no adivinar.
7. La config vive en el código (`config.py`), no en variables de la nube. El
   servicio solo lleva secretos + `TIENDA_ID`. Secretos en Secret Manager,
   nunca en texto plano.
8. LLM: DeepSeek en todo. Gemini u otros solo con OK explícito de Martín.

**C. GitHub — repo limpio**
9. Commits chicos y mensajes claros. Pushear tras cada cambio cerrado.
10. Una sola fuente de verdad: `CLAUDE.md` (reglas) + `RESUMEN` (estado). No crear
    handoffs nuevos sueltos; actualizar los que mandan.
11. Consolidar, no agregar: por cada cosa que se prende, apagar o borrar una
    vieja. Prohibido sumar capas o flags "por las dudas".
12. No romper lo que funciona: leer el archivo entero antes de editar; si el
    cambio es invasivo, escribirlo en un archivo nuevo que REEMPLAZA al viejo en
    el camino vivo. Nunca dejar el camino nuevo apagado al lado del viejo (regla
    2-bis). El revert con git es la red, no un flag dormido.

**D. Verificar y cerrar**
13. Nada se da por hecho sin probar el camino VIVO, no una copia.
14. Reportar fiel: si algo falla, decirlo con la salida real, sin maquillar.
15. Al cerrar el chat: actualizar la memoria y, si toca, limpiar Cloud Run (env
    viejas, servicios de más, costo).

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
- CATÁLOGO Y FAQ, fuente ÚNICA de verdad (Martín, 26-jun): viven en
  `data/clientes/verifika_prod/`. **NO se escriben acá los números de la fuente
  —cuántos productos, cuántos temas de FAQ, cuántas categorías—.** Están en
  `INVENTARIO_FUENTE.md`, que es el ÚNICO documento con candado que lo obliga a
  coincidir con los archivos reales (`test_el_inventario_no_puede_mentir_sobre_la_fuente`).
  Este archivo declaraba una cantidad de temas de FAQ que quedó vieja en junio;
  el 11-ago-2026 una sesión la leyó de acá, se la repitió a Martín como dato
  actual, y estaba desactualizada. Un número, un lugar, y el lugar es el que se verifica. El repo
  es la fuente; se sube a Firestore por los endpoints `/admin/upload-catalog` y `/admin/upload-faq`. Se borraron los fixtures viejos (verifika_2k de 2000 sintéticos, verifika_demo) y sus generadores. NO regenerar el catálogo ni crear otros fixtures: un solo catálogo, una sola FAQ. Se asume que Firestore no cambió desde el 17-jun; si hay duda, comparar el repo contra un export de Firestore.

---

## Regla de oro

**No romper lo que funciona, pero al servicio del Norte de arriba, nunca como excusa para no avanzar.** Este código está en producción con Telegram y va a integrarse con WhatsApp Cloud API directo. Antes de modificar cualquier archivo existente:

1. Leer el archivo completo, no solo la parte a tocar.
2. Si la modificación es invasiva, escribirla en un archivo nuevo en lugar de
   editar a ciegas el viejo. El archivo nuevo REEMPLAZA al viejo en el camino
   vivo, no convive apagado al lado.
3. NO usar feature flags apagados (ver regla 2-bis arriba). El cambio acordado
   se hace vivo y se deploya. La red de seguridad es el revert con git, no un
   flag en false. Lo único configurable es config operativa: secretos, modelos,
   timeouts, umbrales.
4. Si un cambio es grande o invasivo, se le muestra a Martín qué archivos toca y
   qué se rompería antes de hacerlo, y se respeta su OK. Pero la respuesta a "no
   estoy seguro" es preguntar y después deployar, no esconder el cambio apagado.

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
2. **No tocar `data/clientes/verifika_prod/` (la fuente de verdad; los conteos, en `INVENTARIO_FUENTE.md`) ni los CSV de `templates/`** sin permiso. Nunca regenerar el catálogo.
3. **No modificar `requirements.txt`** sin avisar primero qué dependencia se suma y por qué.
4. **No correr `gcloud deploy` ni comandos de producción** sin confirmación explícita.
5. **Antes de cada cambio importante**, mostrar a Martín:
   - Qué archivos van a tocarse
   - Qué se rompería si el cambio sale mal
   - Cómo se vuelve atrás si falla (revert con git), NO un flag apagado
6. **Respuestas concisas, sin corchetes ni paréntesis innecesarios** (Martín usa lector de texto a voz).
7. **Español argentino, voseo.**

---

## Estado actual de la evolución

El estado vivo (qué paso corre, qué falta, pendientes) NO vive acá. Vive en
`RESUMEN_PARA_NUEVO_CHAT.md`, fuente única. Este archivo son solo reglas
permanentes. No volver a poner checklists de estado acá ni mencionar flags de
integración: ya no se usan flags apagadas (regla 2-bis).

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

## Correr la batería desde la NOTEBOOK (Windows) — receta para chats nuevos

Política de trabajo: UN repo, UNA rama viva (`main`), UN Cloud Run. Cada sesión
se trabaja en una rama nueva `claude/<tema>` sobre un clon fresco; al terminar
se mergea a `main` (el CI gateado testea y deploya solo) y la rama se puede
borrar a mano. Desde el celular ya está armado; esta es la receta equivalente
para la notebook, verificada el 3-jul-2026 (Windows 10, Python 3.14):

```powershell
git clone https://github.com/martinrf79/verifika.git
cd verifika
git checkout -b claude/<tema>

# Entorno local (una sola vez por clon)
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt pytest
```

Si pip falla compilando `pydantic-core` (pasa con Python 3.13/3.14 en Windows,
porque `requirements.txt` pinea pydantic 2.9.2 para el CI/Docker con 3.11),
instalar el equivalente sin el pin — NO tocar `requirements.txt`, es solo del
entorno local:

```powershell
.venv\Scripts\python -m pip install "pydantic>=2.9" fastapi "openai>=1.3.0" groq "google-cloud-firestore>=2.18.0" httpx structlog python-dotenv tenacity pytest
```

Correr la batería offline (sin LLM, sin credenciales de Google, sin tocar
producción): el doble local de Firestore (`banco_pruebas/sim_firestore`, vía la
fixture `firestore_doble` de `tests/conftest.py`) carga el catálogo y la FAQ
REALES del repo, igual que en el celular:

```powershell
.venv\Scripts\python -m pytest -q
```

Los tests `vivo` (DeepSeek) no corren acá: se prueban por WhatsApp/Telegram o
leyendo logs de Cloud Run. Para logs/Firestore desde la notebook, usar gcloud
por Bash (ruta completa, ya autenticado en memory-engine-v1), NO PowerShell.

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

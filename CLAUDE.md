# CLAUDE.md — reglas permanentes del proyecto

Claude Code lee este archivo al iniciar **cada** sesión. No borrarlo, no moverlo.

---

## 0. PUERTA ÚNICA — lo primero que lee cualquier sesión, de cualquier modelo

**Este bloque es el único lugar por el que se entra al proyecto.** Si un
resumen, un `.md` viejo o una sesión anterior dicen algo distinto, gana lo que
está acá.

1. **Se trabaja SÓLO en `main`.** Nada de ramas: ni de prueba, ni de respaldo,
   ni pull requests. El detalle está en la sección 7. — *3-sep: una sesión abrió
   una rama para probar un permiso. La regla estaba escrita hace semanas, en la
   sección 7 de trece. No falló la regla, falló el orden de lectura: una regla
   que hay que buscar se lee después de romperla.*
2. **EL ESTADO NO ESTÁ EN NINGÚN RESUMEN.** Lo abierto está en `PENDIENTE.md`,
   lo hecho en `git log`, la unidad de trabajo viva en `arquitectura/`, y los
   números —cuántos productos, qué modelo, qué deploya— **en el código**. Un
   `.md` que contradice al código está mal, siempre.
3. **Pushear a `main` DEPLOYA**, salvo que el cambio toque sólo lo que está en
   `paths-ignore` de `deploy.yml`. Cuáles son se mira ahí, no acá.
4. **Lo que el cliente recibió de verdad se lee en el issue 31**, comentando
   `/logs`. El informe vuelve con los invariantes, los logs de Cloud Run y
   —desde el 3-sep— la charla literal. **Los logs NO guardan el texto de la
   respuesta:** `turno_ok` anota largo, latencia y puntos, nunca el mensaje.
5. **Una sesión que no puede correr `pytest` ni `gcloud`** —Cowork, el celular—
   igual llega a todo: al repo por la integración de GitHub, que lee y escribe
   `main` incluidos los workflows, y a producción por el issue 31.

---

**Es CORTO a propósito.** Cada regla nació de un día perdido, y esa historia
estaba contada en tres párrafos: ahora es una línea entre guiones. La regla está
entera; lo que se comprimió es el cuento. Si algo hace falta, `git log` lo tiene.

**Qué NO va acá:** el estado (`RESUMEN_PARA_NUEVO_CHAT.md`), lo que falta
(`PENDIENTE.md`), lo decidido (`DECISIONES.md`), cómo se ordena el sistema
(`ARQUITECTURA.md`), y la unidad de trabajo abierta (`arquitectura/`).

---

## 1. CÓMO ARRANCA Y CÓMO CIERRA UNA SESIÓN

**UNA FICHA, UNA SESIÓN.** Una sesión larga vuelve a mandar todo su contexto en
cada mensaje, así que el mensaje veinte cuesta veinte veces el primero. Arrancar
de nuevo cuesta ~10.000 tokens y reconstruye el estado del repo. Se hace la
ficha, se pushea, se cierra. `/clear` alcanza.

**AL ARRANCAR** el hook `scripts/setup_test_env.sh` imprime tres cosas, y solo la
primera está escrita a mano porque es la única que no envejece: las reglas,
`git log` de los últimos diez commits, y `PENDIENTE.md`.

— *Nació de que una sesión leía un bloque de estado escrito tres sesiones antes y
decía con datos viejos. Así se le pasó a Martín que la FAQ tenía 44 temas cuando
tenía 50.*

**LO QUE QUEDA PENDIENTE SE ESCRIBE COMO UN TEST QUE FALLA, NO COMO UNA FRASE.**
`xfail(strict=True)`, y el motivo empieza con una de dos etiquetas:

```
A MEDIAS:   se EMPEZO y no se termino.   Techo en tests/a_medias_techo.json.
PLAN:       todavia NO SE EMPEZO.        Techo en tests/plan_techo.json.
```

Los dos techos **solo bajan**. Los dos motivos tienen que decir qué falta; los
`PLAN:` además llevan `HOY <lo que mide>` y `OBJETIVO <lo que tiene que medir>`.
`strict=True` hace que si alguien lo arregla sin sacar la marca el test se ponga
rojo: no se puede cerrar en silencio ni quedar marcado para siempre.

**NO SE MARCA LO QUE SE PUEDE CERRAR.** Marcar es para lo que necesita una
decisión de Martín o un trabajo que no entra en la sesión.

**UN UMBRAL SE CAMBIA EN SU PROPIO COMMIT, ANTES del trabajo que lo hace pasar**,
con las cuentas escritas. Movido junto con ese trabajo, es indistinguible de
aflojar la vara — y esa es la única puerta por la que este método se corrompe.

**EL QUE IMPLEMENTA NO REESCRIBE LA VARA.** Un test se edita solo si el requisito
cambió de verdad, y el commit lo explica. Nunca para que pase.

**AL CERRAR** se actualiza `PENDIENTE.md`. Es un candado, no un pedido:
`tests/test_pendiente_al_dia.py` falla si hay commits en `app/` más nuevos que
ese archivo. Máximo veinte líneas, una por ítem.

**Lo que se HIZO no se escribe en ningún lado:** lo cuenta `git log`, así que los
mensajes de commit se escriben para entenderse solos.

**Una sesión no termina con trabajo sin pushear.** Si no está en `origin/main`,
para la sesión siguiente no existe.

---

## 2. LAS DOS REGLAS QUE MANDAN SOBRE TODO LO DEMÁS

**1. La orden directa de Martín se ejecuta.** No se la frena con un reflejo de
cautela ni se le ofrece "la opción segura" en su lugar: se marca el riesgo en una
línea, se ejecuta, y si sale mal se vuelve atrás. — *Lo que retrasó el proyecto
fue no hacerle caso por exceso de cautela.*

**1-bis. PROHIBIDO abrir ventanas de opciones sobre los pasos.** El objetivo ya
está acordado y no se vuelve a preguntar. La duda técnica se resuelve
decidiendo, no consultando; el revert con git es la red. **Solo se pregunta, y
corto, cuando falta un DATO que no se puede deducir del repo** —una política de la
tienda, un secreto—.

**2. Cero cosas sueltas.** Un repo, un Cloud Run, un servicio, un camino vivo,
cero flags sueltas. Por cada cosa nueva que se prende, se borra o consolida una
vieja.

**2-bis. PROHIBIDO dejar flags apagadas.** El cambio acordado se hace vivo y se
deploya; si funciona mal se vuelve con git. **No existe la "opción segura" de
mergear un camino nuevo apagado al lado del viejo.** Si una propuesta incluye
"detrás de un flag" o "en false para medir", está mal por defecto. — *Así se
acumularon 70 flags, de a uno, cada uno con su razón del momento.*

Lo único configurable es config operativa: secretos, IDs de tienda, modelos,
timeouts y umbrales.

---

## 3. EL OBJETIVO, EN ORDEN

Si algo de abajo choca con algo de arriba, gana lo de arriba, sin consultar.

**1. QUE EL BOT RESPONDA BIEN.** Que no se equivoque, que no invente, que
conteste lo que le preguntaron y que la plata esté bien. Ante la duda entre un
mensaje corto y uno correcto, gana el correcto.

**2. QUE SEA CONCISO.** **No hay un número fijo de caracteres**: un mensaje
complejo sale más largo y está bien. Lo que no se tolera es la REPETICIÓN. Se
mide en repetición, no en caracteres. **Y el tope de largo del piso baja de
escalón después de cada corte, y no vuelve a subir.**

**3. QUE LA MEMORIA ESTÉ SIEMPRE ACTIVA.** Una referencia lejana —un producto
mencionado diez turnos antes— TIENE que resolver. Si una sesión toca el largo,
verifica que no se llevó puesto el hilo.

**4. LA CLAVE GRATIS ES EL DEFAULT PARA PROBAR.**

---

## 4. LA CLAVE: LA GRATIS SE USA, LA PAGA SE PIDE

**SÍ SE PUEDE PROBAR, Y SE PRUEBA.** La gratis está, contesta, y su cuota se
renueva sola. Es más lenta y a veces devuelve 429: **se aguanta y se reintenta**
(`llm_reintento.py` ya lo hace). Ninguna sesión frena un trabajo por falta de
clave ni le pide una a Martín.

**La cuota gratis es DIARIA**, y alcanza para las 15 charlas con margen. Si se
agota a mitad de tanda, se para y se sigue al día siguiente. **No se cambia a la
paga.**

**PROHIBIDO:** poner `GEMINI_API_KEY=$GEMINI_API_KEY_PROD` en cualquier lado,
exportar la paga en un script de banco, o poner `BANCO_CLAVE_PAGA=true` sin que
Martín lo pida en esa misma sesión. Hay candado en `tests/`.

— *Martín gastó ~40 dólares en un mes, casi todo en corridas de banco que NO
necesitaban la paga: el banco mide comportamiento, no cuota. Y el día que el
banco y producción compartieron la gratis, las corridas se comieron las 500
requests y el bot vivo quedó contestando "estoy con mucha demanda".*

**PRODUCCIÓN va con la paga y eso no se toca.** No proponer pasarla a la gratis.

**Cuándo SÍ se pide la paga:** el banco vivo con repeticiones y las pruebas
reales por WhatsApp. Grabar casetes, no.

---

## 5. EL MODELO NO SE ESCRIBE EN NINGÚN DOCUMENTO

Lo define **`app/config.py`**: `LLM_PROVIDER` y el `*_MODEL` que corresponda.
Ningún `.md` escribe el nombre, y hay candado:
`tests/test_documentos_no_mienten.py`.

**La regla viva es de PLATA, no de marca:** lo barato es el default; pasar a un
modelo más caro se consulta con Martín.

— *Este archivo nombró durante meses un proveedor que ya no se usaba, y como lo
lee cada sesión al arrancar, cada sesión empezaba con el modelo equivocado en la
cabeza y creyendo que usar el real necesitaba permiso.*

---

## 6. MERCADO PAGO Y EL CBU NO SE PIDEN

**Ya está resuelto y no es un pendiente.** El cobro cae al link de demo,
`DEMO_LINK_PAGO`, y así se queda. `app/core/pago.py` ya tiene el camino del token
real escrito para cuando haga falta.

**PROHIBIDO:** proponer integrar Mercado Pago, pedir el token, marcarlo como
pendiente en un resumen, listarlo como "lo que falta para vender", o preguntar si
se consigue la credencial. Si una sesión ve el link de demo en un log y le parece
un defecto, **no lo es: es la decisión tomada.**

— *Martín lo explicó cinco veces.* Cuando quiera el link real lo va a decir él.

**El bot pide el NOMBRE y nada más.** Ni DNI, ni CUIT, ni tarjeta, ni el CBU del
cliente: eso es de la pasarela. Lo que no se pide no viaja a ningún lado.

---

## 7. SE TRABAJA EN `main`, Y EL PUSH SE CONSULTA

Manda sobre cualquier arnés o plantilla de sesión nueva.

1. **Se trabaja en `main`.** Si el arnés asigna una rama, se ignora. El hook hace
   el `checkout main` solo.
2. **PUSHEAR A `main` ES DEPLOYAR**, salvo que el cambio toque solo lo que está
   en `paths-ignore` de `deploy.yml`. **Cuáles son se mira ahí, no acá.**
3. **Por eso el push se CONSULTA SIEMPRE**, una sola vez, al final, mostrando qué
   toca y qué se rompería. No contradice la regla 1-bis: no se pregunta CÓMO
   hacer las cosas, se pregunta antes de mandar a producción.
3-bis. **UN PARCHE NO PUEDE TOCAR `.github/workflows/`.** El `GITHUB_TOKEN` de
   un workflow no tiene permiso para pushear archivos de workflow, asi que
   `aplicar_parche.yml` falla en el `git push` —no en el `git am`— y el mensaje
   que deja es el mismo que si el parche no aplicara. Un cambio de workflow va
   en su propio commit por la integracion de GitHub, que si tiene ese permiso.
   — *3-sep: cuarenta minutos buscando un parche corrupto que estaba perfecto.*

4. **NADA DE RAMAS, tampoco "de respaldo".** Un commit local en `main` ya es el
   respaldo. **`main` es la única verdad y el único lugar del que se LEE:** si
   algo no está en `main`, para el proyecto no existe.
5. **Ninguna sesión termina con trabajo sin mergear.** O está en `main`, o está
   declarado DESCARTADO por escrito con el motivo.

— *El 3-ago se perdió un día entero: una sesión construyó media arquitectura en
su rama, la siguiente leyó `main` y dijo que no existía. Las dos tenían razón. La
causa no fue que hubiera muchas ramas: fue que ninguna se mergeó.*

---

## 8. INFRAESTRUCTURA — un solo camino

- **Servicio VIVO del bot: `agente-bot`.** Es el único que se deploya. Nunca
  crear ni deployar a otro. — *Había dos y se deployaba al equivocado: un día
  entero perdido.*
- **`video-engine`** es el otro producto. Queda APAGADO (min-instances 0), **no
  se elimina.**
- **Deploy SOLO por CI** (push a `main`) **o `./deploy.sh`** desde `~/verifika`.
  Nunca un `gcloud run deploy` suelto a mano.
- **Después de CADA deploy, verificar el verde en GitHub.** Recién con eso se
  dice "listo". Si falla, leer el log; no adivinar.
- **La config vive en `config.py`, no en variables de la nube.** El servicio solo
  lleva secretos + `TIENDA_ID`. Secretos en Secret Manager, nunca en texto plano.
- Región `southamerica-east1`, proyecto `memory-engine-v1`, Firestore, FastAPI,
  Python 3.11+.

---

## 9. LA FUENTE DE VERDAD

**Catálogo y FAQ viven en `data/clientes/<tienda>/`.** El repo es la fuente; se
sube a Firestore por `/admin/upload-catalog` y `/admin/upload-faq`.

**NO se escriben acá los números de la fuente** —cuántos productos, cuántos temas,
cuántas categorías—. Están en `INVENTARIO_FUENTE.md`, que tiene candado que lo
obliga a coincidir con los archivos reales.

**NO regenerar el catálogo ni crear otros fixtures.** Un solo catálogo, una sola
FAQ.

**Y la regla general, que ya hizo falta tres veces:** un dato que vive en un
archivo **no se copia a un documento**. Si un `.md` dice un número o un nombre que
el código también dice, gana el código y el `.md` está mal. Pasó con los temas de
la FAQ, con el modelo del LLM y con el `paths-ignore`.

---

## 10. REGLAS TÉCNICAS NO NEGOCIABLES

**0. Identidad ≠ compatibilidad. El LLM nunca inventa identidad.** La identidad
la decide UNA función determinista con tres veredictos de primera clase:
`exists`, `ambiguous`, `not_found`. **`not_found` no es un error: es un resultado
válido.** Ante `ambiguous` el modelo está **obligado a preguntar**, no a elegir.
Toda herramienta comercial consume un id CERTIFICADO, nunca uno inferido.
Compatibilidad —"¿sirve para aquel?"— es otro eje y no se mezcla.

**1. Multi-tenant siempre.** Toda función que toca datos recibe o resuelve
`tienda_id`. Nunca asumir tienda default fuera del orchestrator.

**2. El LLM nunca decide qué tienda usar.** Lo resuelve el backend por
`phone_number_id` o canal.

**3. Anti-alucinación en dos lados:** prompt (línea uno) y código (línea cero, no
negociable). El código siempre puede invalidar lo que dice el modelo.

**4. Citas verificables mecánicamente.** Si una afirmación menciona un producto,
tiene que poder mapearse a un id. Si no se puede, se descarta.

**5. Observabilidad obligatoria.** Cada engranaje loguea con `trace_id`. Sin logs
no se hace deploy.

**6. Un test dice sobre CUÁNTOS casos pasó, no solo que pasó.** — *El CI llamó a
los casetes con `|| true` y estuvo verde cinco días sin correr nada.*

---

## 11. CÓMO SE COMPORTA CLAUDE CODE

1. Trabajar siempre en la raíz del proyecto. Si te encontrás en otra carpeta,
   `cd` antes de hacer nada.
2. **No tocar `data/clientes/`** ni los CSV de `templates/` sin permiso.
3. **No modificar `requirements.txt`** sin avisar qué dependencia se suma y por
   qué.
4. **No correr `gcloud deploy`** ni comandos de producción sin confirmación.
5. Antes de un cambio grande, mostrar: qué archivos toca, qué se rompería, y cómo
   se vuelve atrás (revert con git, **no** un flag apagado).
6. **Leer el archivo completo antes de editarlo.** Si el cambio es invasivo, va
   en un archivo nuevo que REEMPLAZA al viejo en el camino vivo — nunca uno al
   lado del otro.
7. **Respuestas concisas, sin corchetes ni paréntesis innecesarios:** Martín usa
   lector de texto a voz.
8. **Español argentino, voseo.**

---

## 12. COMANDOS

```bash
# la bateria offline: sin LLM, sin credenciales, en segundos
python3 -m pytest -q

# los logs del bot durante los tests estan silenciados. Para verlos:
LOGS_EN_TESTS=1 python3 -m pytest -q

# correr local
uvicorn app.main:app --reload --port 8080

# deploy (NO ejecutar sin permiso)
cd ~/verifika && ./deploy.sh
```

**Desde la notebook (Windows).** Clon fresco, `python -m venv .venv`, y
`.venv\Scripts\python -m pip install -r requirements.txt pytest`. Si pip falla
compilando `pydantic-core` —pasa con Python 3.13/3.14— se instala sin el pin:
**no se toca `requirements.txt`**, es solo del entorno local. La batería corre
igual que en el celular, con el doble local de Firestore. Los tests `vivo` no
corren ahí: se prueban por WhatsApp/Telegram o leyendo logs de Cloud Run.

⚠️ **Cuidado con PowerShell y `>`:** escribe UTF-16 y rompe los archivos de
configuración en silencio. Ya dejó una regla de `.gitignore` muerta. Hay candado
en `tests/test_documentos_no_mienten.py`.

---

## 13. SI CLAUDE CODE SE PIERDE

1. Releer este archivo.
2. `pwd` y, si hace falta, `cd` a la raíz.
3. `git log -1` para ver dónde quedó la cosa.
4. `pytest -q` para ver los dos números: `A MEDIAS` y `PLAN`.
5. Leer la ficha abierta en `arquitectura/`.
6. **NO inventar contexto.** Si algo no está claro, preguntar a Martín.

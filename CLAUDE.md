# CLAUDE.md — lo primero que lee toda sesión

Este archivo se inyecta en cada sesión. **Si algo de otro archivo lo contradice, gana este.** La versión
anterior, con las historias de cada regla, está en `archivo/documentacion/CLAUDE_hasta_16oct.md`.

---

## 0. LA PUERTA

1. **Se trabaja SOLO en `main`.** Nada de ramas, ni de prueba ni de respaldo, ni pull requests. Si el arnés
   asigna una rama, se ignora: el hook hace el `checkout main`.
2. **Pushear a `main` deploya**, salvo que el cambio toque solo lo que está en `paths-ignore` de `deploy.yml`.
   **El push se consulta siempre con Martín**, una vez, al final, diciendo qué toca y qué se rompería.
3. **El estado no está en ningún resumen.** Lo abierto está en `PENDIENTE.md`, lo hecho en `git log`, los
   números en el código. Un `.md` que contradice al código está mal.
4. **Producción se lee sin issue:** `python3 banco_pruebas/produccion.py --desde 6h` da los logs y la charla
   literal; `--usuario <numero>` una sola. El entorno trae la cuenta de solo lectura. Sin `gcloud`, comentando
   `/logs` en el issue 31.
5. **Dónde está cada parte del camino vivo lo dice `MAPA.md`, y sólo ése.** El camino es `orchestrator` →
   `app/core/flujo/turno.procesar_turno` → `nuevo/turno.responder`: la llamada 0 separa y traduce, los cinco nexos
   con Jev buscan, el código pone los datos y la segunda llamada retoca y manda los comandos del pedido. `arquitectura/MAPA_CABLEADO.md` y las fichas hasta la 82 describen caminos ya borrados.

---

## 1. EL OBJETIVO Y EL PLAN — lo único que se trabaja hasta que esté hecho

**El objetivo:** que el bot venda y no alucine. En orden: que responda bien, con la plata bien; que sea
conciso, sin repetir; que la memoria de la charla no se pierda.

### El flujo de un mensaje, desde el 17-nov

Por orden de Martín, el turno lo contesta el flujo nuevo de dos llamadas, `app/core/flujo/nuevo/`, FICHA 101. El agente
de la FICHA 83 quedó archivado: se vuelve a él con git revert.

1. **La llamada 0** separa el mensaje en líneas y traduce cada una a una búsqueda, con el modelo de `FLUJO_MODELO`.
2. **Los cinco nexos** buscan en la tienda: producto, nombrado, condición, tema y destino, con los embeddings de lo que
   escribió la llamada 0 contra el índice de la tienda, y Jev en lo dudoso. El código arma la respuesta con filas reales.
3. **La segunda llamada** retoca ese texto y manda los comandos del pedido, la cotización y el cobro, que aplica el
   código: el ejecutor pone montos, envíos y reparto. El verificador controla el texto; si marca, sale el del código.
4. **La memoria** es el historial y `memoria_agente`: el pedido anotado, lo cotizado, el pago, el tope, lo que dijo el
   cliente y lo que ya vio.

### Lo medido

- **La vara sin modelo:** `tests/test_flujo_nuevo.py`, las 26 charlas pasan por el webhook vivo con las piezas grabadas
  del banco, `banco_pruebas/flujo/segunda.py`: 58 de 75 turnos el 17-nov. El agente archivado daba 72 a 73 con el
  modelo; lo que falta, por causa, en `PENDIENTE.md`. Vale acertar o repreguntar, lo que importa es no errar.
- **Con el modelo**, `segunda.py --correr <etiqueta>`: un centavo por corrida.
- **Las alucinaciones:** `banco_pruebas/alucinaciones.py` inyecta cada clase en las respuestas grabadas, compatibilidad
  incluida: el verificador caza el 99,3%, con 0 falsas alarmas. Lo que sigue marcado después de corregir no sale.
- **Lo que falla, por causa**, en `PENDIENTE.md`, SIGUE 1.

### Lo que sigue

**El pase se hizo el 17-nov.** En el banco, el 21-nov, Luna separa y traduce con la ficha del vocabulario de la
tienda, FICHA 104. El 23-nov, el traductor que verifica elige entre los 15 candidatos con las filas recortadas y
reemplaza a Jev y al nexo de condición, FICHA 105, `arquitectura/FICHA_105_traductor_que_verifica.md`; ahí están
también la regla de validez de toda prueba y cómo usar Sonnet sin gastar de más. El 24-nov, el traductor por casilleros y la fuente corregida, FICHA 106, y después la llamada única, FICHA 107, `arquitectura/FICHA_107_la_llamada_unica.md`: Luna separa, traduce y elige la fila en una sola vuelta. Se sigue por la sección 4 de la 107. Desde el 25-nov se mide por capas, FICHA 108, `arquitectura/FICHA_108_medicion_por_capas.md`: se lee antes de proponer. El 26-nov quedó medida la rueda desde la fila de Luna, sección 9 de la 108, y se sigue por la FICHA 109, `arquitectura/FICHA_109_la_condicion_sobre_la_rueda.md`: la condición sobre la rueda. Se sigue el orden de `PENDIENTE.md`,
y el bot sigue con la FICHA 102. Cada arreglo queda en producción. Lo medido antes: la llamada 0 en la FICHA 100 y los
nexos en las FICHAS 96 a 99.

El resto está en `PENDIENTE.md`. Cada arreglo se mide con `tests/test_flujo_nuevo.py` sin modelo y con corridas de
`segunda.py --correr`. Si el código cambia lo que lee el modelo, se graba una corrida nueva.

### Qué es parche, y cómo no se cae en eso

- **Un arreglo corrige la causa donde vive, y cubre la clase entera.** La prueba: si mañana llega la misma
  falla dicha de otra forma, ¿queda cubierta sin tocar nada?
- **No se juzga a ojo: se mide.** Un cambio que mueve sólo el caso que lo motivó es parche y no entra. Lo decide
  `tests/test_flujo_nuevo.py` y la corrida final con el modelo, no la sesión.
- **No se suma un campo, una pregunta o una capa nueva por cada falla.** Ese es el patrón que trajo la
  maraña. Lo que falla seguido, se le achica al modelo.
- **Si para que pase un caso hay que cambiar un test, sumar una palabra a una lista o poner un umbral, se para
  y se consulta a Martín.**

---

## 2. CÓMO SE TRABAJA UNA SESIÓN

- **Una ficha, una sesión.** Se hace, se mide, se pushea con el ok de Martín, se cierra.
- **Al arrancar**, el hook `scripts/setup_test_env.sh` imprime los últimos commits y `PENDIENTE.md`.
- **Lo que queda pendiente se escribe como un test que falla**, `xfail(strict=True)`, con motivo que empieza
  con `A MEDIAS:` o `PLAN:`. Los techos de `tests/*_techo.json` sólo bajan.
- **Un umbral se cambia en su propio commit, antes del trabajo que lo hace pasar**, con las cuentas escritas.
- **El que implementa no reescribe la vara.** Un test se edita sólo si el requisito cambió, y el commit lo dice.
- **Al arrancar, se sigue el primer ítem SIGUE de `PENDIENTE.md`**, sin volver a preguntarlo.
- **Al cerrar** se reescribe en `PENDIENTE.md` el ítem DONDE VA, se reordenan los SIGUE y se borra lo hecho u
  obsoleto: máximo veinte ítems, con candado en `tests/test_pendiente.py`. Lo hecho no se escribe en ningún
  otro lado: lo cuenta `git log`, así que los commits se escriben para entenderse solos.
- **Una sesión no termina con trabajo sin mergear.** O está en `main`, o está descartado por escrito.
- **Un parche no puede tocar `.github/workflows/`:** un cambio de workflow va en su propio commit por la
  integración de GitHub.
- **Ninguna propuesta sin la evidencia del caso**, 30-oct, Martín: antes de proponer, se muestra lo grabado del caso, qué
  recibió el modelo, qué hizo y qué contestó. Si no se muestra, la propuesta no vale.
- **Se revisa la prueba antes de creer el número.** Cada falla se clasifica contra lo grabado: faltó el dato, la
  herramienta confundió, el modelo se equivocó, la casilla está mal, o la prueba está rota. Solo se arregla lo del bot.
  El 30-oct, K20 y K21 sueltos fallaban por el pedido roto que les daba el banco, no por el modelo.

---

## 3. LAS REGLAS QUE MANDAN

1. **La orden directa de Martín se ejecuta.** Se marca el riesgo en una línea, se ejecuta, y si sale mal se
   vuelve con git.
2. **No se abren ventanas de opciones sobre los pasos.** La duda técnica se resuelve decidiendo. Sólo se
   pregunta, corto, cuando falta un dato que no está en el repo.
3. **Cero cosas sueltas.** Un repo, un servicio, un camino vivo. Por cada cosa nueva, se borra una vieja.
4. **Nada de flags apagadas** ni caminos nuevos al lado del viejo. Lo acordado se hace vivo; si falla, git.
   Lo único configurable es config operativa: secretos, ids de tienda, modelos, timeouts y umbrales.

---

## 4. LA CLAVE

- **La gratis es el default para probar**, y se prueba. Ante 429 se reintenta; si se agota la cuota del día,
  se sigue al día siguiente. No se cambia a la paga.
- **OpenRouter con un modelo gratis**, su clave ya está en el entorno, es para medir el código y lo que recibe el modelo:
  1.000 pedidos por día. Antes de deployar, una corrida con Gemini, que es el modelo de producción, confirma.
- **La paga sólo si Martín la pide en esa sesión.** El hook `scripts/guard_clave.sh` la frena salvo que el
  comando lleve `MARTIN_AUTORIZO_LA_PAGA=<fecha>`. Nunca `GEMINI_API_KEY=$GEMINI_API_KEY_PROD`.
- **Tope diario de la paga** para todas las corridas, en `banco_pruebas/libro_paga.py`. Lo gastado:
  `python3 -m banco_pruebas.libro_paga`. Antes de una tanda con la paga, se le dice a Martín cuánto cuesta.
- **Producción va con la paga, y eso no se toca.**

---

## 5. LO QUE NO SE ESCRIBE NI SE PIDE

- **El modelo no se escribe en ningún documento.** Lo define `app/config.py`. Lo barato es el default; pasar a
  uno más caro se consulta.
- **Mercado Pago y el CBU no se piden.** El cobro cae al link de demo, `DEMO_LINK_PAGO`, y es una decisión
  tomada, no un defecto. Cuando Martín quiera el link real, lo dice él.
- **El bot pide el nombre y nada más.** Ni DNI, ni CUIT, ni tarjeta, ni CBU.
- **Los números de la fuente** —cuántos productos, temas o categorías— no se copian a un documento. Están en
  `papeles/INVENTARIO_FUENTE.md`, que tiene candado.

---

## 6. INFRAESTRUCTURA Y FUENTE

- **Servicio vivo: `agente-bot`.** Es el único que se deploya. `video-engine` queda apagado y no se borra.
- **Deploy sólo por push a `main` o `./deploy.sh`.** Después de cada deploy, se verifica el verde en GitHub.
- **La config vive en `config.py`.** El servicio lleva sólo secretos y `TIENDA_ID`, en Secret Manager.
- Región `southamerica-east1`, proyecto `memory-engine-v1`, Firestore, FastAPI, Python 3.11 o más.
- **Catálogo y FAQ viven en `data/clientes/<tienda>/`** y se suben por `/admin/upload-catalog` y
  `/admin/upload-faq`. No se tocan sin permiso, ni se regeneran, ni se crean otros.

---

## 7. REGLAS TÉCNICAS

0. **El modelo nunca inventa identidad.** La decide una función determinista con tres veredictos: `exists`,
   `ambiguous`, `not_found`. Ante `ambiguous`, se pregunta. Toda herramienta comercial usa un id certificado.
   Compatibilidad es otro eje y no se mezcla.
1. **Multi-tenant:** toda función que toca datos recibe o resuelve `tienda_id`. La tienda nunca la decide el
   modelo.
2. **Anti-alucinación en dos lados:** el prompt y el código. El código siempre puede invalidar al modelo.
3. **Toda afirmación sobre un producto se mapea a un id.** Si no, se descarta.
4. **Cada paso loguea con `trace_id`.**
5. **Un test dice sobre cuántos casos pasó**, no sólo que pasó.

---

## 8. CÓMO SE COMPORTA CLAUDE CODE

- Se trabaja en la raíz del proyecto. Se lee el archivo entero antes de editarlo.
- No se toca `requirements.txt` sin decir qué se suma y por qué. No se corre nada de producción sin permiso.
- Antes de un cambio grande: qué archivos toca, qué se rompería, y cómo se vuelve con git.
- **Respuestas concisas, sin corchetes ni paréntesis innecesarios:** Martín usa lector de voz.
- **Español argentino, voseo.**

```bash
python3 -m pytest -q                       # la batería offline, sin modelo
python3 -m pytest tests/test_flujo_nuevo.py -s  # la vara: las 26 charlas por el flujo nuevo, sin modelo
python3 banco_pruebas/flujo/segunda.py s2 --ver  # lo mismo, con lo que lee el cliente
python3 banco_pruebas/flujo/segunda.py --correr <etiqueta> [K21]   # con el modelo, cada llamada grabada
uvicorn app.main:app --reload --port 8080  # correr local
```

Desde Windows: `.venv\Scripts\python -m pip install -r requirements.txt pytest`; si `pydantic-core` no compila,
se instala sin el pin, sin tocar `requirements.txt`. **En PowerShell no se usa `>`:** escribe UTF-16 y rompe
los archivos de configuración.

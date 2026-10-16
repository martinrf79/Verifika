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
5. **Los nombres de cada parte** —estaciones `T`, juntas `J`, puntos del modelo `L`— los define
   `arquitectura/MAPA_CABLEADO.md`, y sólo ése.

---

## 1. EL OBJETIVO Y EL PLAN — lo único que se trabaja hasta que esté hecho

**El objetivo:** que el bot venda y no alucine. En orden: que responda bien, con la plata bien; que sea
conciso, sin repetir; que la memoria de la charla no se pierda.

### El flujo de un mensaje, como tiene que ser

1. **El modelo TRADUCE, no responde.** Parte el mensaje en preguntas si es una multipregunta, y por cada una
   pide al código algo concreto de un **menú cerrado**: buscar, producto, envío, cuenta, política,
   compatibilidad, comprar. Si una pregunta no necesita traducción, la repite tal cual.
2. **El código responde** con sus herramientas deterministas. Ahí no hay modelo, y por eso no hay invento.
3. **El modelo redacta** sólo con lo que devolvió el código. Los montos y los presupuestos los pone el código.
4. **Lo que se le da al intérprete es lo que se trabaja:** la información justa, con pocos tokens, armada
   desde las 58 combinaciones y desde cómo rindió el modelo de producción en las pruebas.

### Lo medido, que dice dónde falla

- **Con la charla bien dada, el intérprete traduce bien.** Con el contexto escrito a mano: 167 de 174
  mensajes. Con las 58 como ejemplos resueltos, en la validación limpia: 12 de 12 en tres repeticiones, en
  una sola llamada y unos 3.000 tokens. FICHA 67 y FICHA 69.
- **La falla está en lo que le da producción.** El contexto se arma desde nueve campos sueltos de la charla y
  la traducción cae: 21 de 30 con charla previa, 7 de 10 con un pedido armado. FICHA 69.
- **La maraña está después del intérprete.** Once capas de código vuelven a leer el mensaje o la memoria para
  corregir lo que entregó el intérprete. Cada falla sumó una capa: ahí nacen los parches.
- **El código ya resuelve bien lo que el intérprete traduce bien**, visto el 16-oct en K21 y C35: las fallas
  que quedan en vivo son del intérprete o del redactor.

### El plan, en este orden

1. **Un único estado de la charla, escrito por el código**: pedido por destino, lo mostrado con su id, los
   filtros vigentes, lo que buscó el cliente. Es lo que tenía el contexto escrito a mano. **Se mide antes de
   tocar producción**: la vara del desmenuzado con el contexto que arma el código, no el escrito a mano. Está
   hecho cuando se acerca a 167 de 174.
2. **El intérprete como traductor puro**, con las 58 como ejemplos resueltos y el menú cerrado. Es la forma
   que dio 12 de 12.
3. **Sacar las once capas de corrección**, con el criterio de abajo. Lo que hacía cada una pasa al estado del
   paso 1 o al menú del paso 2, o se va.
4. **Reducir `app/` a la mitad**, para que se pueda auditar y no se rompa con el tiempo. El techo está en
   `tests/lineas_techo.json`: baja con cada corte y nunca sube.

### Las once capas, y el criterio para sacarlas

Viven en `app/core/tablero.py`. Corrigen la salida del intérprete:

```
_reparto_leido          relee el reparto del pago en el mensaje
_sobre_el_pedido        rearma el pedido guardado
_envios_juntos          junta los envíos en una pieza
_normalizar             ajusta las piezas al vocabulario
_sobre_lo_buscado       suma las condiciones de la búsqueda anterior
_heredar_exclusiones    copia las exclusiones de la memoria
_conservar              compara los artículos contra lo repartido
_resolver_items y _elegidos   eligen qué producto es cada artículo
_cuenta_del_codigo      arma la cuenta que el intérprete no pidió
_revision               segunda llamada al modelo para corregir
banderas y GUIAS        tercera llamada con preguntas de sí o no
```

**El criterio:**
- **Una capa por commit.** El commit dice qué charlas de las 101 tendría que mover, y por qué.
- **Se mide con `banco_pruebas/puerta.py`**, sobre las 101 charlas: las 58, las K, la jerga y las de memoria.
  Tres corridas de base y tres del cambio, charla por charla. Más la vara fija,
  `pytest tests/test_casos_grabados.py`, y las grabaciones sin modelo.
- **Sale si `puerta.py` no marca ninguna charla rota.** Si empeora alguna, lo que hacía esa capa pasa al estado o al menú, y se
  vuelve a medir. Nunca se deja una capa nueva en su lugar.
- **La atadura no es una capa de corrección:** valida el vocabulario del menú y se queda.

### Qué es parche, y cómo no se cae en eso

- **Un arreglo corrige la causa donde vive, y cubre la clase entera.** La prueba: si mañana llega la misma
  falla dicha de otra forma, ¿queda cubierta sin tocar nada?
- **No se juzga a ojo: se mide.** Un cambio de lo que reciben el intérprete o el redactor que mueve sólo el
  caso que lo motivó es parche y no entra. Lo decide `puerta.py`, no la sesión.
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
- **Al cerrar** se actualiza `PENDIENTE.md`: máximo veinte líneas, una por ítem. Lo hecho no se escribe en
  ningún lado: lo cuenta `git log`, así que los commits se escriben para entenderse solos.
- **Una sesión no termina con trabajo sin mergear.** O está en `main`, o está descartado por escrito.
- **Un parche no puede tocar `.github/workflows/`:** un cambio de workflow va en su propio commit por la
  integración de GitHub.

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
python3 -m pytest tests/test_casos_grabados.py   # la vara fija
python3 -m banco_pruebas.puerta --base <etiqueta> --cambio <etiqueta>   # una mejora contra la base
uvicorn app.main:app --reload --port 8080  # correr local
```

Desde Windows: `.venv\Scripts\python -m pip install -r requirements.txt pytest`; si `pydantic-core` no compila,
se instala sin el pin, sin tocar `requirements.txt`. **En PowerShell no se usa `>`:** escribe UTF-16 y rompe
los archivos de configuración.

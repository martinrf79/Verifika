# FICHA 100 — La llamada 0 elegida: el prompt v2 y el modelo nuevo; los cinco nexos cerrados

16-nov-2026, sesión con Martín. Sigue a la FICHA 99. **Escrita para que una sesión nueva siga sin volver al chat.** Lo
hecho, en `git log` del 16-nov; los números, en los commits que graban cada corrida.

---

## 1. Lo que decidió Martín el 16-nov

1. **La llamada 0 cambia de modelo:** al que dio la medición completa, `llamada0_modelos.MODELOS["luna"]`, con
   razonamiento bajo. Su clave directa está en el entorno y anda; por OpenRouter queda poco saldo.
2. **El prompt de la llamada 0 es el v2**, `llamada0_modelos.PROMPTS["v2"]`: una línea por producto o variante, la
   condición en la búsqueda de cada línea, también la que vale para todo el mensaje, y lo corregido no cuenta.
3. **Los cinco nexos quedan cerrados por ahora**, salvo arreglos menores. Lo que sigue es la memoria y la segunda
   llamada, la que redacta.

## 2. Lo medido, sin modelo después de la llamada 0

Las varas se escribieron antes de correr, en `banco_pruebas/llamada0_vara.py`, y la corre
`banco_pruebas/llamada0_modelos.py`. Una corrida por modelo, salvo donde se dice.

| Qué | La llamada 0 de hoy | Prompt v2, modelo de hoy | Prompt v2, modelo elegido |
| --- | --- | --- | --- |
| Las 140: mensajes sin falla | 128 | 134 | 135 |
| Las 140: mensajes bien separados | 139 | 139 | 137 |
| Las 365: condiciones en la búsqueda, de 200 sin memoria | 121 | 191 | 200 |
| Las 365: perdidas al separar / al traducir | 58 / 21 | 7 / 2 | 0 / 0 |
| Los 40 reales: condiciones en la búsqueda, de 16 | 5 | 14 | 14 |
| Las 365: rubro pedido en el primer candidato, de 320 | 316 | — | 315 |
| Las 365: duplicadas / contadas dos veces / inventadas | 6 / 24 / 3 | 11 / 14 / 6 | 6 / 17 / 4 |
| Segundos por mensaje, las 140 | 4,3 | 10,8 | 3,4 |

- **Dónde se perdía la condición:** casi toda al separar, dicha una vez para todo el mensaje, "los más baratos", "las
  menos partes chinas", y no llegaba a cada línea. Embeddings y Jev sobre líneas ya separadas no lo arreglan: el v2 sí.
- **Los embeddings con el fragmento y la búsqueda juntos** traen el rubro correcto entre 8 productos en 189 de 189 de
  las 140, `banco_pruebas/embeddings_candidatos.py`. La jerga sin traducir casi no llega como falla al final.
- **Jev no separa:** elige de listas cerradas. Sirve para confirmar lo dudoso, como ya hace en los nexos.
- **Lo que no sirvió:** el prompt v3, primero los productos y las condiciones en lista con un ejemplo, empeora: copia
  las palabras del cliente en vez de traducir. Tres corridas. Qwen 3.8 con razonamiento piensa hasta 210 segundos por
  mensaje; sin él inventa condiciones. El mismo modelo con razonamiento medio no mejora.
- **La variación:** el modelo de hoy cambia hasta 7 mensajes de 140 entre corridas. Las diferencias chicas de la tabla
  no separan modelos; las de las 365 sí.
- **Lo que la vara cuenta y no es falla:** las inventadas son casi todas tipeos del cliente que el modelo corrige,
  "inlaambrico"; el rubro de más es sobre todo C14 y C37, que preguntan por memorias sin buscar.

## 3. Lo que sigue, en este orden, orden de Martín del 16-nov

El flujo nuevo vive solo en el banco y pasa a `app/` todo junto, de una vez, cuando el camino completo supere al agente
en las mismas charlas. Hasta entonces no se toca producción. Para que no se pierda nada:

1. **Ordenar. Hecho el 16-nov, sección 6.** El flujo nuevo está en `banco_pruebas/flujo/`, sin dependencias del banco
   viejo, con los mismos números antes y después de mover y los vectores rehechos y verificados.
2. **Los nexos sobre la llamada 0 elegida.**
   - Cambiar la llamada 0 de `flujo_nuevo.py` al modelo de `llamada0_modelos.MODELOS["luna"]` con el prompt v2. Desde el
     16-nov ese modelo ya va por la clave directa de OpenAI; el nombre se confirmó en la lista de modelos, sin correrlo.
   - **El tope:** Martín lo subió de 12 centavos a un dólar el 16-nov, en su propio commit; llevaba 11 centavos.
   - Correr los cinco nexos sobre lo nuevo: las búsquedas nuevas piden sus vectores y lo dudoso nuevo pide Jev.
   - El nexo de rubro con lo medido en `embeddings_candidatos.py`: consulta con el fragmento y la búsqueda juntos, y 8
     candidatos en vez de 5; Jev elige entre ellos en lo dudoso.
   - Se miran las fallas por causa y se calibra cada nexo con su `--calibrar`, de a una cosa, con la confirmación en
     los bancos que no se usaron.
3. **Lo contado dos veces en los mensajes de siete artículos**, K20 y K21: una línea por producto y otra por destino. Se
   resuelve con las cantidades y los destinos, después de la llamada 0.
4. **La memoria:** acoplar al flujo nuevo la del agente, `memoria_agente`, con el pedido anotado, lo mostrado, el pago y
   el tope, o una más efectiva si se mide mejor. Bancos: las 32 claves de memoria fuera de las 525, y K10, K11, K16 y K21.
5. **La segunda llamada, la que redacta**, con la vara de la FICHA 90, citando por número lo que dieron los nexos.
6. **El camino completo contra el agente**, en las mismas charlas: `tests/test_agente.py` y las corridas con el modelo.
   Si lo supera, pasa a `app/` reemplazando al agente: el modelo de la llamada 0 en `app/config.py`, su clave en Secret
   Manager, los índices de la tienda calculados al subir el catálogo y la FAQ, y el cobro, el cierre y el verificador.

## 4. Cómo se corre

```bash
python3 banco_pruebas/flujo/llamada0_modelos.py                  # las 140, sin gasto
python3 banco_pruebas/flujo/llamada0_modelos.py --reales         # los 40 reales y las 365: dónde se pierde la condición
python3 banco_pruebas/flujo/llamada0_modelos.py --sobra --ver    # lo que sobra y lo inventado; pide vectores si faltan
python3 banco_pruebas/flujo/llamada0_modelos.py --correr luna v2 --banco reales525   # con gasto, retoma lo que falta
python3 banco_pruebas/flujo/embeddings_candidatos.py --informe   # cuántos candidatos hacen falta, de lo grabado
python3 banco_pruebas/flujo/flujo_nuevo.py --ver                 # el flujo de punta a punta, sin gasto
python3 banco_pruebas/flujo/nexo_rubro.py --ver [--jev]          # cada nexo, sin gasto: también nexo_tema, nexo_nombrado,
python3 banco_pruebas/flujo/nexo_condicion.py --ver              #   nexo_condicion, nexo_destino y reales [--525]
python3 banco_pruebas/flujo/embeddings.py                        # la receta de los embeddings y el registro de cada nexo
```

Gasto de la sesión del 16-nov de la elección: unos 30 centavos de la paga de Gemini, anotados en `libro_paga.jsonl`; 15
de OpenRouter; unos 30 entre Haiku y DeepSeek por sus claves. La sesión de ordenar: 2 centavos de la paga de Gemini en
vectores.

## 5. Inventario del flujo nuevo: dónde está cada cosa

Todo en `banco_pruebas/flujo/`, salvo la fuente de la tienda, que está en `data/clientes/verifika_prod/`, y los libros de
gasto, `banco_pruebas/libro_paga.jsonl` y `banco_pruebas/jev/gasto_jev.jsonl`. Lo grabado está en `grabado/`; los
bancos de mensajes, en `bancos/`.

| Paso | Código | Grabado, para repetir sin gasto |
| --- | --- | --- |
| Las rutas y el código de producción sin red | `entorno.py` | — |
| El flujo de punta a punta | `flujo_nuevo.py` | `flujo_nuevo_llamada0.jsonl`, `flujo_nuevo_puntajes.json`, `flujo_nuevo_respuestas.json` |
| Los embeddings: receta, pedido, registro e índice | `embeddings.py` | `vectores/indice_tienda.json.gz` |
| La llamada 0: prompts, modelos y varas | `llamada0_modelos.py`, `llamada0_vara.py`, `engranaje0.py` | `llamada0_modelos.jsonl`, `engranaje0_corridas.jsonl` |
| Cuántos candidatos hacen falta | `embeddings_candidatos.py` | `embeddings_candidatos_rangos.json`, `embeddings_candidatos_rangos_reales.json` |
| Nexo de rubro y producto | `nexo_rubro.py` | `nexo_rubro_puntajes.json`, `nexo_rubro_jev.jsonl`, `nexo_rubro_respuestas.json` |
| Nexo de tema de la FAQ | `nexo_tema.py` | `nexo_tema_puntajes.json`, `nexo_tema_dudoso.jsonl` |
| Nexo de producto nombrado | `nexo_nombrado.py`, `bancos/nombrados38.py` | `nexo_nombrado_puntajes.json`, `nexo_nombrado_llamada0.jsonl` |
| Nexo de condición | `nexo_condicion.py`, `nexo_condicion_vara.py` | `nexo_condicion_puntajes.json`, `nexo_condicion_jev.jsonl`, `nexo_condicion_respuestas.json` |
| Nexo de destino | el código de producción, `app/core/flujo/normal.lugares` y `app/core/fuente._cotizar`, desde `flujo_nuevo.nexo_destino`; su vara en `nexo_destino.py` | — |
| Jev | `jev.py` | `*_jev.jsonl`, `nexo_tema_dudoso.jsonl` |
| Las 140 | `bancos/nuevas70.py`, `bancos/nuevas70b.py`, `momento0_b.py` | `momento0_b_corridas.jsonl`, `momento0_b_puntajes.json` |
| Los 40 reales y las 365 | `reales.py`, `bancos/las365.json` | `reales_llamada0.jsonl`, `reales_puntajes.json`, `reales_jev.jsonl` y lo mismo con `reales525` |
| Antecedentes: la suma de fragmentos y Shopify | `antecedentes/` | `momento0_shopify*.json`, `engranaje0_embeddings.json` |

## 6. Lo hecho al ordenar, 16-nov

- **Se movió con `git mv`:** los pasos, los bancos y lo grabado. Lo grabado no cambió un byte.
- **Se cortó el banco viejo.** El entorno de producción sin red sale de `entorno.instalar` y no de `camino_fijo`. Los
  vectores salen de `embeddings.pedir` y no de `llamada1_modelos._emb`. Las 365 quedan congeladas en
  `bancos/las365.json`, generado con el código de antes, con el texto, la vara y las preguntas de la agenda a mano de
  cada turno; ya no se importan `agendas58` ni `traduccion58`. Jev pasó a su archivo. El flujo solo importa del banco
  los libros de gasto, el costo y el doble de Firestore.
- **Los mismos números:** 25 informes sin gasto, corridos antes y después de mover. Salen iguales salvo el registro de
  embeddings, que ahora dice las rutas nuevas, y lo que sobra, que antes no corría por falta de vectores.
- **Los embeddings, que se perdían de una sesión a otra**, están en `embeddings.py`: la receta, una sola función que
  pide, un solo cache en `vectores/`, y el índice de la tienda en el repo. Se rehicieron todos con la paga, 2 centavos.
  Los puntajes de los cinco nexos, del flujo, de los reales, de las 365 y de los candidatos salen iguales byte a byte a
  los grabados. Lo que sobra da lo de la sección 2: 6, 24 y 3; 11, 14 y 6; 6, 17 y 4. La calibración del nexo de rubro
  da, con la variante viva, lo mismo que califica el nexo desde lo grabado.
- **Dos antecedentes del 15-nov no se repiten:** `engranaje0_embeddings.json` y `momento0_b_puntajes.json` difieren
  solo en teclado, porque el 16-nov se le sumó el alias "keyboard". Quedan como se grabaron.
- **Lo que no coincide con una nota vieja, y ya estaba así antes de mover:** la calibración de condición da 148 de 188
  con la V3, no 150 como dice el registro; el resto, igual.
- **Lo que decidió Martín al cerrar:** el tope del modelo elegido sube a un dólar; el índice de 14 MB queda en el repo;
  las dos grabaciones del 15-nov y el 148 de la V3 se ven sobre la marcha. Lo que sigue son la memoria y la segunda
  llamada, pasos 4 y 5. La llamada 0 del flujo sigue con el modelo de hoy hasta que se cambie con su medición, paso 2.
- **Una segunda pasada completa**, con el tope cambiado, da lo mismo. La única diferencia es de orden: dos temas
  inventados de una línea de las 365 se listan en otro orden, porque salen de un conjunto; el contenido es igual.

## 7. La cadena entera con las dos llamadas 0, 16-nov, orden de Martín

Los cinco nexos encadenados por mensaje, como en producción: la llamada 0 separa, cada línea va a los nexos que le
tocan, Jev resuelve lo dudoso y el filtro deja solo lo que está en la fuente. Dos mediciones con el mismo código: la
llamada 0 de hoy y la elegida, `FLUJO_L0=luna`. Lo de la elegida se graba aparte, `grabado/*_luna.*`; lo de hoy no
cambió. Embeddings por la paga de Gemini y Jev en vivo sobre lo dudoso nuevo; la elegida corrió solo en los 38
nombrados, por la clave directa de OpenAI; en los demás bancos ya estaba grabada. Gasto: menos de un centavo de la paga,
menos de un centavo de Jev, y unos 16 mil tokens de OpenAI.

| Banco y nexo | Llamada 0 de hoy | La elegida |
| --- | --- | --- |
| 140, rubro sobre las líneas del flujo, elige bien | 180 de 188 | 178 de 189 |
| 140, lo que no se vende, dice no hay | 21 de 21 | 21 de 21 |
| 140, destinos | 47 de 48, 0 inventados | 47 de 48, 0 inventados |
| 140, tema con Jev | 15 de 15, 3 inventados | 13 de 14, 1 inventado |
| 38 nombrados | 39 de 40 | 39 de 40 |
| 40 reales, mensajes sin falla, con destinos | 39 | 38 |
| 40 reales, nombrados | 15 de 16 | 13 de 16 |
| 40 reales, condiciones bien | 10 de 17 | 13 de 17, 8 filtros inventados |
| 40 reales, destinos | 17 de 17 | 17 de 17 |
| 40 reales, con tres nexos o más, sin falla | 7 de 7 | 12 de 13 |
| 365, mensajes sin falla, con destinos | 294 | 302 |
| 365, rubros, de más | 320 de 320, 20 | 320 de 320, 18 |
| 365, temas, inventados | 43 de 55, 24 | 47 de 55, 23 |
| 365, nombrados | 132 de 135 | 125 de 135 |
| 365, condiciones bien | 136 de 215 | 169 de 215 |
| 365, condiciones: perdidas en la llamada 0, repregunta de más, filtro inventado | 58, 4, 0 | 5, 115, 13 |
| 365, destinos, inventados | 89 de 110, 5 | 94 de 110, 0 |
| 365, con tres nexos o más, sin falla | 72 de 102 | 86 de 128 |

- **No se pisan:** cero cortes y cero filas fuera del catálogo en las dos. Cada nexo lee su campo y su índice.
- **Lo que mejora con la elegida:** las condiciones llegan, 169 contra 136 en las 365, y los destinos, 94 contra 89 sin
  inventar. Los mensajes con tres nexos o más pasan de 72 a 86 sin falla.
- **Lo que empeora, por causa:**
  - **Nombrado:** la elegida junta dos modelos en una línea cuando el cliente elige entre ellos, "mouse G305 o G203
    inalámbrico", y el nombrado, que pide que las palabras calcen con un solo modelo, da no encontrado. R04, C28, C32.
  - **Condición:** con las condiciones en cada línea, el nexo repregunta de más, 115, e inventa 13 filtros: el nexo se
    calibró con las búsquedas cortas de hoy.
  - **Rubro:** búsquedas largas con la condición, "repetidor wifi de pared para ampliar la señal hasta el patio", caen
    en no hay donde la corta acertaba.
- **Lo que esta vara no mide con la elegida:** la condición y el nombrado de las 140 tienen la vara escrita sobre las
  búsquedas de Gemini y no reconocen otras; con la elegida solo cuentan los reales y las 365.
- **Las varas sumadas el 16-nov, antes de correr la elegida:** los destinos de los 40 reales a mano, `DESTINOS_REALES`, y
  los de las 365 de la agenda a mano, también los de cada producto de una compra; y los mensajes con tres nexos o más.
  El nexo de rubro también se califica sobre las líneas del flujo, `nexo_rubro.py --flujo`.

```bash
FLUJO_L0=luna python3 banco_pruebas/flujo/reales.py [--525]   # cualquier calificación, con la llamada 0 elegida
python3 banco_pruebas/flujo/nexo_rubro.py --flujo --jev        # el rubro sobre las líneas del flujo
```

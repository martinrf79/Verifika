# FICHA 101 — La memoria, la segunda llamada y el pase a producción del flujo nuevo

16-nov-2026, con Martín. **La sesión nueva arranca acá.** Sigue a la FICHA 100, que tiene lo medido de la llamada 0 y de
la cadena entera, sección 7. Escrita para seguir sin volver al chat.

---

## 1. Lo que decidió Martín el 16-nov

1. **El flujo nuevo va a producción todo junto**, reemplazando al agente, apenas mida mejor que él en las mismas charlas,
   **así como está**: sin calibrar antes los nexos. Desde ahí cada arreglo deploya y el bot mejora sin dos caminos ni
   mediciones que no se comparan.
2. **El orden:** primero la memoria, después la segunda llamada, después el camino completo contra el agente, y si lo
   supera, el pase. **Después del pase**, la calibración de los nexos, uno por sesión.
3. **Las piezas:** la llamada 0 con `llamada0_modelos.MODELOS["luna"]` y el prompt v2, por la clave de OpenAI. Los
   embeddings siguen con Gemini: son compatibles, comparan el texto de la búsqueda contra el índice de la tienda sin
   importar quién lo escribió, y con las búsquedas de la elegida el rubro sale primero en 315 de 320 en las 365. Lo
   dudoso lo sigue confirmando Jev, que midió bien. La segunda llamada, con el mismo modelo de la llamada 0.

## 2. Lo que hay hoy, sin sorpresas

- **El flujo vive en `banco_pruebas/flujo/`**, un archivo por paso, sin el banco viejo; `MAPA.md` lo detalla. Todo se
  califica sin gasto desde `grabado/`, y cada llamada 0 aparte: `FLUJO_L0=luna` lee la elegida y graba en `*_luna.*`.
- **Los embeddings** están en `embeddings.py`: la receta, la única función que pide, el cache de la sesión y el índice de
  la tienda en el repo. Rehechos, dan lo grabado byte a byte.
- **La cadena entera ya se midió por mensaje**, FICHA 100 sección 7: cero cortes, los nexos no se pisan. Con la elegida
  las 365 dan 302 mensajes sin falla contra 294, y los de tres nexos o más 86 contra 72.
- **Lo que la elegida empeora, conocido y para después del pase:** el nombrado cuando junta dos modelos en una línea,
  "G305 o G203"; la condición, que repregunta de más con búsquedas largas; y el rubro, que en alguna búsqueda larga
  cae en no hay.
- **Lo que falta para que el flujo conteste una charla:** la memoria, que hoy es solo la lista de ids mostrados, paso 8
  de `flujo_nuevo.py`; y la segunda llamada, que hoy es `flujo_nuevo.redactar`, código que pega datos sin criterio de venta.

## 3. La memoria — primero

**Qué tiene que hacer:** que el turno que sigue entienda "el segundo", "ese", "los dos", "a Rosario el otro", "dale",
"y en blanco?", y que no se pierdan el pedido, lo mostrado, los destinos, el pago ni el tope entre turnos.

**La regla para no rehacer los nexos:** la llamada 0 sigue contestando igual a un mensaje que se entiende solo. Hay dos
caminos, y se elige midiendo:
- **A, recomendado:** la llamada 0 no cambia. Lo que el mensaje deja sin decir lo resuelve el código después, contra la
  memoria: lo mostrado con sus ids y su número, el pedido anotado, los destinos y el pago. Es como hoy resuelve el agente
  con `memoria_agente`. Los nexos no se tocan.
- **B:** la llamada 0 recibe la memoria resumida. Antes de aceptarlo se corren de nuevo las 140, los 40 reales y las 365
  con `FLUJO_L0`, y tienen que dar lo mismo que en la FICHA 100 sección 7. Si cambian, es A.

**Lo que se reusa de producción:** `memoria_agente` en el documento de la charla, `app/core/flujo/turno.py`, y
`agente.memoria_de`, con el pedido anotado, lo último mostrado, el pago y el tope. El historial es una ventana; lo que
dijo el cliente antes queda en `dicho`, la memoria larga del 6-nov, `agente.charla`.

**Los bancos de memoria, que ya existen:** las 32 claves de memoria que quedaron fuera de las 525,
`bancos/las365.json` campo `fuera`, con su agenda a mano en `agendas58.AGENDAS`, donde "M-1" y "L-1" son referencias a lo
mostrado; las charlas K10, K11, K16 y K21; y las 26 charlas de `tests/test_agente.py`. La vara se escribe antes de
correr, desde la agenda a mano, y se commitea sola.

**Lo contado dos veces en K20 y K21**, una línea por producto y otra por destino, se resuelve acá: con las cantidades y
los destinos del pedido anotado.

## 4. La segunda llamada — los criterios de venta

**Qué es:** el modelo que redacta la respuesta al cliente con lo que dieron los nexos, sin inventar. Es la respuesta
atada de la FICHA 90, que ya está en el bot, `app/core/flujo/respuesta.py`: el modelo cita por número lo que el código
le pasa, P productos, R reglas de la FAQ, E envíos, N lo que no se vende, D cantidades y búsquedas vacías, y escribe solo
un saludo y una pregunta cortos. Los datos los pega el código con las filas reales. El control devuelve una vez al
modelo lo que escribe de más.

**Lo nuevo:** la entrada es el contrato del flujo, FICHA 96, y no las herramientas del agente. Cada nexo ya devuelve sus
candidatos, su elegido y su veredicto: coincide, ambiguo, no hay, repreguntar. Los criterios de venta van en el prompt:
qué se muestra primero, cuándo se repregunta, cómo se ofrece lo cercano cuando no hay, cómo se cierra. El verificador,
el cobro, el cierre con el lead y la calculadora del agente se reusan como están.

**La vara:** la de la FICHA 90 y las casillas de `vara_58.json` por turno. Se mide con la clave de OpenAI.

## 5. El camino completo contra el agente

- **El banco:** las 26 charlas de `tests/test_agente.py`, donde el agente da 75 de 75 turnos sin modelo, y las corridas
  con el modelo, donde da 72 de 75. Variación entre corridas, unos 7 turnos: tres corridas por lado. **Corregido el
  27-nov, Martín:** ese número es sobre charlas escritas por nosotros y no se sostiene; con charlas reales el agente dio
  80 de 113 turnos el 3-nov, FICHA 91. No se usa como referencia.
- **Cómo:** el flujo entero por el webhook, turno por turno, con la memoria; la llamada 0 y la segunda llamada grabadas
  la primera vez, para repetirlas sin modelo como `agente_replay.py`. Un test nuevo con su piso, como `test_agente.py`.
- **El corte, escrito antes de correr y con el ok de Martín:** turnos bien igual o mejor que el agente en las tres
  corridas, y cero datos inventados en `banco_pruebas/alucinaciones.py`. Si lo pasa, va a producción.

## 6. El pase a producción, todo junto

1. Los pasos de `banco_pruebas/flujo/` pasan a `app/core/flujo/`: la llamada 0, los cinco nexos, Jev, la memoria y la
   segunda llamada. `entorno.py`, los bancos y las varas se quedan en el banco.
2. **Los embeddings por mensaje:** un pedido por mensaje con las búsquedas y los fragmentos, con la receta de
   `embeddings.py`, que ya es la de `agente._vectores`. El índice de la tienda se calcula al subir el catálogo y la FAQ,
   `/admin/upload-catalog` y `/admin/upload-faq`, y se guarda en Firestore por tienda.
3. **Config y secretos:** el modelo en `app/config.py`; `OPENAI_API_KEY` y `TYPESAFE_API_KEY` en Secret Manager. Se borra
   la variable de embeddings que quedó de otro proveedor, `EMBEDDINGS_MODEL`.
4. **El turno:** `turno.procesar_turno` llama al flujo en vez de `agente.responder`. El agente se borra: no queda al
   lado. Lo que se reusa del agente queda en su lugar.
5. **Por cada paso, un log con `trace_id`:** lo que tradujo la llamada 0, lo que eligió cada nexo y Jev, y lo que leyó el
   cliente, auditable con `banco_pruebas/produccion.py`.
6. **Resiliencia:** si OpenAI, Gemini o Jev caen o tardan, el cliente no queda sin respuesta: se repregunta con lo que
   se sabe. Hay que medir la demora por mensaje: llamada 0, embeddings, Jev y segunda llamada.
7. La FAQ cambiada el 16-nov se sube por `/admin/upload-faq`.
8. Push con el ok de Martín, deploy, y el verde en GitHub. Después, una charla real por WhatsApp.

## 7. Después del pase: calibrar los nexos con la elegida, uno por sesión

Con la vara de siempre y en mensajes completos, `FLUJO_L0=luna`, de a una cosa:
- **Nombrado:** separar "X o Y" en dos nombrados; R04, C28, C32.
- **Condición:** que no repregunte de más ni invente filtros con las búsquedas largas.
- **Rubro:** que la condición dentro de la búsqueda no tape el producto; "repetidor wifi de pared para…".
- **Tema y destino:** mirar lo que queda.
- **Las varas de las 140 de condición y nombrado** están escritas sobre las búsquedas de Gemini y no reconocen otras;
  se reescriben por mensaje, sin depender de la llamada 0, en su propio commit.
- **Abierto para ver sobre la marcha:** las dos grabaciones del 15-nov que cambian por el alias "keyboard", y el 148 de
  150 de la V3 de condición.

## 8. La duda de Martín: ¿y si la elegida mide mejor en un nexo y peor en los otros?

Medido en la FICHA 100 sección 7: con la elegida mejoran la condición que llega, 169 contra 136, los destinos y los
mensajes completos; empeoran el nombrado y la repregunta de condición, por la forma de la línea y no por el modelo de
los nexos. La llamada 0 es una sola para los cinco nexos: elegir un modelo por nexo pediría dos llamadas por mensaje,
el doble de costo y demora. Lo que se recomienda es la elegida y ajustar esos dos nexos a sus líneas, que es la sección 7.

## 9. Cómo se corre

```bash
python3 banco_pruebas/flujo/flujo_nuevo.py --ver                       # el flujo de punta a punta, la llamada 0 de hoy
FLUJO_L0=luna python3 banco_pruebas/flujo/reales.py --525              # cualquier calificacion con la elegida
FLUJO_L0=luna python3 banco_pruebas/flujo/nexo_condicion.py --ver
python3 banco_pruebas/flujo/llamada0_modelos.py --correr luna v2 --banco <banco>   # la elegida, con gasto
python3 banco_pruebas/flujo/embeddings.py                              # la receta de los embeddings
python3 -m pytest tests/test_agente.py -s                              # la vara del agente, sin modelo
```

Gasto: la elegida tiene un tope de un dólar en el banco y lleva unos 11 centavos; embeddings con la paga de Gemini,
centavos; Jev, menos de un centavo por banco.

# Arquitectura de Verifika — el turno en dos llamadas

Mapa de referencia permanente. El estado del día vive en
`RESUMEN_PARA_NUEVO_CHAT.md`; esto es cómo se ordena el sistema.

## El principio

**El control está ANTES de que el modelo escriba, no después.**

Durante meses el diseño fue el contrario: el modelo escribía y once módulos lo
corregían -un juez, una red de verificadores, ocho guardas de salida-. Cada capa
juzgaba con evidencia distinta, y la que ganaba borraba a las otras. Lo medido
en producción el 1-ago: el juez declaró sin respaldo seis renglones que había
estampado el propio código. El problema no era que el modelo alucinara; era que
tres capas peleaban por la misma verdad.

Ahora el modelo no puede alucinar un dato porque no lo tiene: lo pide con una
herramienta y redacta con el resultado delante. Lo que la herramienta no trajo,
no existe para él.

---

## El turno, de punta a punta

```
webhook -> orchestrator -> hub_venta
                             |
       1. LLAMADA UNO  ------+  el modelo ve la charla + las 7 herramientas
          "que buscar"        |  y devuelve tool calls. No traduce nada.
                              |
       2. PARALELO -----------+  asyncio.gather. Hasta 2 rondas: la segunda
          "todo junto"        |  solo para lo que desbloquea la primera.
                              |
       3. LLAMADA DOS --------+  redacta con el JSON de resultados delante
          "redactar"          |
                              |
       4. LA REGLA -----------+  toda la plata del texto tiene que venir de
          determinista        |  lo que calculo el codigo, o se poda
                              |
       5. CIERRE Y COBRO -----+  leads.py, la misma funcion de siempre
                              |
       6. MEMORIA ------------+  history, resumen, vistos, carrito, destinos
```

Dos llamadas al modelo en el caso común, tres cuando hace falta la segunda ronda
de herramientas. Antes eran cuatro encadenadas.

---

## Las ocho herramientas

`app/core/herramientas.py`. Molde Pydantic + una función determinista que ya
existía y estaba probada. La lógica no se reescribió: se le puso un molde
adelante y el esquema que ve el modelo se GENERA del molde, así no hay dos
definiciones que puedan divergir.

| herramienta | qué resuelve | de dónde sale el dato |
|---|---|---|
| `registrar_pedido` | DECLARA lo que entendió, antes de buscar | no toca la fuente; es lo que el reconciliador compara contra lo que pidió |
| `buscar_productos` | identidad y catálogo | certificador + catálogo Firestore |
| `ficha_producto` | la ficha completa por id | catálogo + specs + compatibilidad |
| `consultar_temas` | qué dice la casa de cada tema | FAQ curada con sus valores estampados **+** criterio y movida de `base_conocimiento.json` |
| `cotizar_envio` | costo a un destino | tabla de tarifas + geo de códigos postales |
| `armar_presupuesto` | LA CUENTA | calculadora; devuelve el bloque ya escrito |
| `ver_compatibilidad` | si sirve para su equipo | tabla de compatibilidad |
| `tomar_pedido` | decisión de compra y cobro | marca el cierre; trae los datos de pago |

---

## Lo que sigue atado, y es lo único que hace falta atar

1. **La identidad la decide el código.** Regla cero del proyecto.
   `certificar_producto` devuelve encontrado, ambiguo o no_encontrado. Con
   ambiguo el modelo está obligado a preguntar; no puede elegir.
2. **Los enums salen de la fuente viva.** `categoria`, `temas` y los `campo` de
   los filtros se inyectan en el esquema desde el catálogo y la FAQ. El modelo no
   puede pedir una categoría que no vendemos, ni un tema de política que no
   existe, ni filtrar por un campo que la fuente no tiene.
2-bis. **Los atributos se CONSULTAN, no se razonan.** `buscar_productos` recibe
   `filtros` estructurados -campo, operador, valor- sobre los 38 campos reales
   del catálogo, columnas y `specs`. Antes el modelo recibía tres fichas y tenía
   que deducir de la prosa cuál era blanco o cuál pesaba menos: eso es adivinar
   con el dato cargado al lado. Si la ficha no dice, el filtro devuelve "no se
   sabe", que no es lo mismo que "no".
3. **La plata la arma el código.** `armar_presupuesto` devuelve el presupuesto
   renglón por renglón. El modelo lo pega, no lo recompone. Es la única parte del
   mensaje que el modelo no redacta.

---

## Los candados deterministas de salida

Son cuatro y ninguno reescribe prosa: borran lo que no puede salir.

- **Plata inventada.** Todo monto del texto tiene que estar en lo que trajeron
  las herramientas, o en el presupuesto de un turno anterior, que también lo
  calculó el código. Ve la plata con signo y sin signo, y no confunde una spec
  -1600 DPI, 3200 MHz- con un monto.
- **Cobro inventado.** Un CBU, alias, titular o banco que no coincida con la
  config de la tienda no sale. Nació de que el modelo se inventó un CBU de 22
  dígitos en una charla viva.
- **JSON filtrado.** El volcado crudo de una herramienta no es parte del mensaje.
- **Honestidad de bot y saludo inicial** (`guardas_salida.py`, dos funciones). Lo
  único que no puede depender del prompt: si preguntan si es una máquina, se dice
  la verdad, y el primer mensaje avisa que es un asistente automático.

---

## Qué NO existe más, y por qué

- **El intérprete.** Traducía el mensaje a una taxonomía nuestra de veinte
  campos con un vocabulario de 116 términos. Se caía por JSON truncado, y cuando
  se caía todo lo de abajo trabajaba a ciegas. El modelo ya entiende la charla:
  no hace falta que la traduzca a nuestro diccionario, hace falta que pida datos.
- **El solver de fragmentos y su render.** El modelo emitía fragmentos atados a
  enums y el código los estampaba. El render descartaba lo que no encajaba: en
  un turno real quedaron seis de ocho preguntas sin contestar.
- **El juez y la red de verificadores.** Corregían al modelo después de escribir,
  con evidencia distinta a la suya. Borraban dato real.
- **Los detectores** de stock contradicho y promesas prohibidas siguen vivos,
  pero en `banco_pruebas/detectores.py`: son instrumentos para MEDIR una corrida,
  no capas del bot.

---

## Multi-tenant

`tienda_id` lo resuelve el backend por `phone_number_id`, nunca el modelo. Viaja
por contextvar a todas las herramientas. Cada tienda tiene su catálogo, su FAQ,
sus tarifas y sus datos de cobro.

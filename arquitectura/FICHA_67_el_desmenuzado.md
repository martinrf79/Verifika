# FICHA 67 — El desmenuzado: ¿el modelo parte la pregunta compleja y le pasa bien cada parte al código?

4-oct-2026. Es el paso cero antes del cableado: si el modelo no parte y traduce
bien, ningún cableado arregla la respuesta. Sigue a la 61, que midió lo mismo
con mensajes simples y en el formato viejo.

## Qué mide y cómo

Banco: `banco_pruebas/nexos/desmenuzado.py`. Corridas en
`banco_pruebas/nexos/desmenuzado_corridas.jsonl`, entrevistas en
`desmenuzado_entrevistas.jsonl`.

- **Treinta mensajes complejos.** Cada uno mezcla dos a siete tipos:
  producto, búsqueda, compatibilidad, FAQ, memoria, condición, pedido con
  destinos, cuenta y pago. Salen de las charlas reales de WhatsApp —K01, K20,
  R13, R15, R19 y R21—, de las K y G del banco y de casos nuevos.
- **Contexto previo fijo**, con productos reales del catálogo: lo que el bot
  mostró, el carrito y la exclusión viva. Así se prueba la memoria sin correr
  la charla entera.
- **Lo correcto escrito antes de correr**: las partes que tienen que llegar al
  código y, cuando el mensaje edita el pedido, cómo tiene que quedar el pedido,
  con producto, cantidad y destino.
- **Las dos formas de pedir, con el mismo contexto:**
  - **tablero**: el intérprete de producción tal cual. Usa su prompt, su
    esquema, la memoria que arma `respuesta._memoria_texto`, la atadura y la
    normalización del código. No incluye la revisión de la segunda vuelta.
  - **nexos**: las líneas de `banco_pruebas/nexos/`, con el reintento por
    formato y la segunda vuelta del decidir. No incluye la red.
- **El corrector es mecánico y compara por contenido, no por la etiqueta del
  tipo.** Antes de correr se valida contra un oráculo con
  `--oraculo`: tiene que aprobar una salida perfecta y reprobar una rota, en
  las dos formas.
- **Reserva.** La mitad de los casos, los pares, no se mira para ajustar
  instrucciones.
- **Repeticiones.** Tres por modelo y forma, a temperatura cero.

## Lo medido

### Piloto con DeepSeek, una repetición, etiqueta `d1`

Sirvió para validar el banco. Un tercio de las fallas del primer conteo eran
del corrector o del contexto y no del modelo. Se corrigieron antes de la
corrida buena:
- la exclusión viva estaba guardada con otro formato que el de producción;
- el decidir de los nexos se corregía sin su segunda vuelta;
- el nombre de un producto citado por id no se traducía;
- una compra con varios ítems se leía como un solo producto.

| forma | casos enteros bien | partes bien |
|---|---|---|
| nexos | 23 de 30 | 74 de 84 |
| tablero de producción | 22 de 30 | 74 de 84 |

### Corrida completa, etiqueta `v1`

PENDIENTE de correr: DeepSeek y el modelo de producción, tres repeticiones
cada uno.

## Lo que ya muestra el piloto, falla por falla

**Fallas del FORMATO**: el modelo no tenía cómo decirlo.
- **Tablero:** el esquema no tiene "toda la tienda". "Los dos más baratos de la
  tienda" sale como rubro "no lo vende la tienda" y no se busca nada. Es K01, la
  charla real.
- **Tablero:** no hay tipo humano; sale como política de contacto. Se acepta.
- **Nexos:** la búsqueda no tiene forma de poner un tope de precio. En X05, "que
  no pase de 250 mil" se pierde.
- **Nexos:** no hay forma de decir "eso no se vende" sin buscar. En X05, el
  celular queda sin contestar.

**Fallas del MODELO**: lo podía decir y lo dijo mal.
- **Reparto por destino.** En "quiero dos, uno a Rosario y otro a Córdoba", los
  dos formatos ponen dos a cada destino, o dos a uno y uno al otro. Es la falla
  más cara, porque cambia la plata.
- **"El más barato de esos".** El tablero busca en el catálogo en vez de elegir
  entre lo mostrado. Es X19.
- **"De acuerdo a la crisis".** El tablero no lo lee como más barato. Es R15.
- **Se pierde una parte.** El teclado de K20 se pierde en el tablero; la
  garantía, en un caso de nexos.
- **Mensajes viejos.** El tablero vuelve a interpretar mensajes viejos de la
  charla como si fueran nuevos. Es X17.

**Fallas del CÓDIGO**: el modelo lo dijo bien y el código no lo entiende.
- **Tablero:** una compra con varios ítems, "si todo es compatible anotame los
  tres", llega a `reservar` con el primer ítem solo, por `a_herramienta`.
- **Nexos:** "cambiar | destino Posadas" sin producto no mueve nada.

## Las entrevistas

`--entrevista <etiqueta>` le muestra al modelo que falló lo que recibió, lo
que escribió y lo que faltaba. Le pregunta qué leyó, por qué y qué le hubiera
ayudado. Corre solo sobre casos de ajuste, nunca de reserva. Lo que digan va
acá, resumido, y se prueba como cualquier otra mejora.

PENDIENTE: correrlas sobre `v1`.

## Cómo se sigue

1. Correr `v1` completo, con los dos modelos y tres repeticiones.
2. Entrevistar las fallas de ajuste.
3. Corregir por clase, no por caso:
   - el formato, sumando "toda la tienda", el tope de precio y "no se vende";
   - el código, con la compra de varios ítems y el destino sin producto;
   - las instrucciones, solo donde la entrevista muestre una causa.
4. Volver a medir, y mirar la reserva recién al final.
5. Vara para pasar al cableado, en su propio commit antes de medir:
   - **casos enteros:** 27 de 30 o más, en las tres repeticiones;
   - **pedido:** cero errores de reparto que cambien la plata;
   - **reserva:** no más de un caso por debajo del ajuste.

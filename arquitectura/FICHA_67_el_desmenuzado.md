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

### Corrida completa, etiqueta `v1`, 5-oct

Son los dos modelos, las dos formas y tres repeticiones. La corrida y las
entrevistas costaron 25 centavos.

| modelo y forma | casos enteros bien, por repetición | partes bien | ajuste | reserva |
|---|---|---|---|---|
| DeepSeek con nexos | 25, 26 y 25 de 30 | 92 % | 38 de 45 | 38 de 45 |
| DeepSeek con el tablero de producción | 21, 21 y 21 | 86 % | 24 de 45 | 39 de 45 |
| modelo de producción con nexos | 20, 20 y 19 | 84 % | 30 de 45 | 29 de 45 |
| **modelo de producción con el tablero, o sea el bot de hoy** | 16, 16 y 18 | 75 % | 16 de 45 | 34 de 45 |

**Lo que dicen los números:**
- **Los nexos ganan con los dos modelos**: de 21 a 25 con DeepSeek, y de 16 a
  20 con el modelo de producción. El formato pesa tanto como el modelo.
- **La mejor combinación es DeepSeek con nexos.** Ajuste y reserva dan igual,
  38 y 38, así que no hay sobreajuste.
- **El tablero cae fuerte en el ajuste.** Es porque la mitad de ajuste se
  quedó, por el orden, con las charlas reales más difíciles: K01, K20, R15 y
  la del humano. Ahí el tablero pierde y los nexos no.
- **A temperatura cero, cada caso da casi siempre tres de tres o cero de
  tres**, como dijo la ficha 59. Cada falla es de diseño y se arregla una vez.
- **X01 da cero en las cuatro combinaciones.** Es "si anda quiero dos, uno a
  Rosario y otro a Córdoba". El reparto de un mismo producto entre destinos
  no lo hace bien ningún modelo con ningún formato, así que lo tiene que
  garantizar el código: la red de la ficha 66 o el pedido como estado.

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

### Lo que dijo DeepSeek sobre `v1`

El detalle está en `desmenuzado_entrevistas.jsonl`. Cada pista apunta a una
clase de falla, no a un caso:
- **Tablero:** el rubro no tiene un valor para "cualquier rubro", y por eso
  escribe "no lo vende la tienda". Pide "toda la tienda" en la lista.
- **Tablero:** "precio de un rubro sin modelo es buscar", y "crisis" o
  "presupuesto" quieren decir lo más barato. Pide la regla.
- **Tablero:** buscar no lleva cantidad ni destino por ítem, y elegir uno ya
  mostrado tiene que ir como producto, no como buscar.
- **Tablero:** "hacen envíos al exterior" es política, no envío.
- **Tablero:** si el cliente pide un humano, no se vuelve a interpretar lo
  viejo de la charla.
- **Tablero:** para cambiar un destino, la cuenta repite todos los ítems
  vigentes. Pide un ejemplo.
- **Nexos:** "uno a A y otro a B" va como dos agregar de uno, nunca "cantidad
  2 y cambiar destino". Pide el ejemplo con ids.
- **Nexos:** pide una forma de línea para "no se vende" y un campo de precio
  máximo.

### Lección sobre cómo entrevistar

En la primera tanda la pregunta le mostraba al modelo las partes faltantes en
el formato interno del corrector, con `{"t": ...}`. **El modelo de producción
creyó que ese era el formato que tenía que escribir** y todas sus respuestas
quedaron contaminadas. DeepSeek no se confundió. **Regla:** a la entrevista se
le dice lo que faltó con palabras del cliente, nunca con estructuras internas.

## Cómo se sigue

1. Hecho: `v1` y las entrevistas.
2. Arreglar la entrevista para que hable en palabras del cliente, y volver a
   entrevistar al modelo de producción.
3. Corregir por clase, no por caso:
   - el formato, sumando "toda la tienda", el tope de precio y "no se vende";
   - el código, con la compra de varios ítems y el destino sin producto;
   - las instrucciones, solo donde la entrevista muestre una causa.
4. Volver a medir, y mirar la reserva recién al final.
5. Vara para pasar al cableado, en su propio commit antes de medir:
   - **casos enteros:** 27 de 30 o más, en las tres repeticiones;
   - **pedido:** cero errores de reparto que cambien la plata;
   - **reserva:** no más de un caso por debajo del ajuste.

## Los 58 como números, 6-oct

Fue idea de Martín: el modelo parte el mensaje y a cada parte le pone el número
de la combinación de la ficha 58. Delante tiene la lista con un ejemplo de cada
una. El banco es `banco_pruebas/nexos/numeros58.py`. Son quince mensajes
complejos con dos repeticiones por modelo, y costó un centavo.

**Tokens: es viable.**
- La lista con nombre y ejemplo suma unos 1.100 tokens fijos, que van en
  caché.
- La salida es de unos 5 tokens por mensaje, o unos 20 si lleva además lo que
  nombra cada parte.

**Lo que hace el modelo: no sirve así.**
- Los casos enteros salieron 11 de 30 con DeepSeek y 10 de 30 con el modelo de
  producción. Con nexos son 25 de 30 en la ficha.
- **Las 58 no son una partición.** Mezclan tipos simples con combinaciones de
  tipos. "Si el G305 anda con Mac, me lo llevo" es un solo número, el 29, o
  dos números, el 36 y el 15, y el código no puede saber cuál de los dos
  caminos tomó el modelo.
- **Los modelos no coinciden entre sí.** Para "ninguno me convence", uno pone
  el 35 y el otro el 44.
- **El número solo no alcanza.** El código sigue necesitando el producto, la
  cantidad y el destino.

**Lo que dijeron los dos modelos en la entrevista, y coinciden:**
- 58 es demasiado y se superponen: los datos falsos, los varios productos y
  las referencias se confunden entre sí;
- el número solo no alcanza;
- prefieren palabras a números;
- proponen pocos tipos de acción, de 10 a 15, y los datos por separado.

Eso ya es la forma de los nexos.

**Lo que sí sirve de la idea:** usar las 58 como VARA y como lista de ejemplos
para los nexos, no como etiqueta de salida.

### Los números en dos llamadas, 6-oct, etiqueta `num1`

Es la versión de Martín y tiene dos llamadas:
- **Primera llamada:** el modelo parte el mensaje y le pone a cada parte de
  uno a tres números de la ficha 58.
- **Segunda llamada:** el modelo escribe las líneas de los nexos, pero en vez
  de todos los nexos recibe SOLO la explicación larga de los números que
  eligió. Esas explicaciones están en `banco_pruebas/nexos/guias58.py`.
  Tiene las mismas dos vueltas: el reintento por formato y el decidir.

Son los mismos treinta casos, el mismo corrector y tres repeticiones. El
modelo de producción corrió con la clave gratis. Costó siete centavos.

| modelo y camino | casos enteros por repetición | partes | ajuste | reserva |
|---|---|---|---|---|
| modelo de producción con números | 25, 25 y 25 | 92 % | 36 de 45 | 39 de 45 |
| modelo de producción con nexos, `v1` | 20, 20 y 19 | 84 % | 30 | 29 |
| DeepSeek con números | 23, 23 y 22 | 91 % | 37 | 31 |
| DeepSeek con nexos, `v1` | 25, 26 y 25 | 92 % | 38 | 38 |

**Lo que dicen los números:**
- **Con el modelo de producción, los números ganan claro**: de 20 a 25 casos.
  Y la ganancia no es de ajuste: la reserva sube de 29 a 39.
- **Con DeepSeek, los números pierden un poco**: de 25 a 23, con la reserva
  de 38 a 31. A DeepSeek le alcanza la lista entera de nexos; al modelo más
  barato le sirve recibir solo lo que aplica a este mensaje.
- **X01, el reparto por destino, sale tres de tres con DeepSeek** por primera
  vez. Hay que decirlo: la explicación 26 lleva la regla que DeepSeek dio en
  su entrevista sobre X01, que es un caso de ajuste.
- **Lo que sigue fallando en todos:**
  - X05, por el tope de precio y el "no se vende";
  - X24, por la webcam más barata;
  - X06, por el segundo en blanco.

  Son faltas de formato de los nexos y siguen abiertas.
- **Costo:** unos 4.200 tokens de entrada contra unos 3.000 de los nexos,
  porque es una llamada más. La lista y las explicaciones van en caché.

### Las guías afinadas, 6-oct, etiquetas `num2` y `num3`

`guias58.py` v2 se afinó solo con fallas de AJUSTE de `num1`. Cada guía lleva
ahora tres cosas:
- la regla;
- un ejemplo resuelto, sacado de las 58 y no de los casos del banco;
- cuándo no es ese número.

Además hay cuatro números nuevos que las 58 no cubrían: 59 no se vende, 60
tope de precio, 61 toda la tienda y 62 pedir una persona. Y la lista de la
primera llamada lleva pistas para los números que se confunden: "crisis" es 9,
"cómo te pago" es 11, y "de esos" con "dame" es 27 y 15.

**Error propio en `num2`:** los ejemplos iban sin "D1 |". El modelo de
producción los copió así, el código descartó esas líneas, y cayó a 23. En
`num3` cada ejemplo lleva la forma exacta. **Regla:** un ejemplo para el
modelo se escribe con la forma exacta que se le pide, porque la copia.

En `num3` el modelo de producción corrió con la paga. La clave gratis se
agotó a mitad de la tanda, y Martín había dicho que en ese caso se usara la
paga.

| modelo | `num1`, guías v1 | `num3`, guías v2 | ajuste | reserva |
|---|---|---|---|---|
| modelo de producción | 25, 25 y 25 | 25, 25 y 25 | de 36 a 39 | de 39 a 36 |
| DeepSeek | 23, 23 y 22 | 24, 23 y 23 | de 37 a 34 | de 31 a 36 |

**Lo que dice:**
- **Arreglar por clase arregla esa clase.** X05, "no se vende" con tope de
  precio, pasa de cero a tres de tres con los dos modelos.
- **El total no se mueve con el modelo de producción.** Lo que sube en ajuste
  baja en reserva, así que el techo de este camino, a una sola traducción,
  anda por 25 de 30.
- **DeepSeek mejora en la reserva**, de 31 a 36, y empata con lo que daba
  con nexos.
- **X01, el reparto por destino, volvió a cero en DeepSeek.** En `num1` lo
  pasaba con una regla escrita en palabras del cliente; el ejemplo de las 58
  que la reemplazó no alcanza. Es un caso de ajuste, así que no se toca la
  guía por él. Va al código: la red de la ficha 66 o el pedido como estado.
- **Lo que queda en los dos:**
  - X16, la garantía y el Windows de cada notebook, que sale como política y
    no como ficha del producto;
  - X24, la webcam más barata;
  - X06, el segundo en blanco.

## Jev, un clasificador sin texto: investigado el 6-oct

Jev es de TypeSafe AI. Recibe un texto y preguntas con listas cerradas, y
devuelve la opción con su probabilidad, sin escribir texto. Sería la PRIMERA
llamada, la de los números, con dos ventajas: da confianza por opción y es
barata, 0,042 dólares por millón de tokens de entrada y la salida gratis.

**Lo que no hace es partir el mensaje.** Clasifica un texto entero, así que
igual hace falta que un modelo lo parta antes, o hacerle una pregunta por
parte.

**No se pudo probar:** está en OpenRouter y en la API de TypeSafe, y el
entorno no tiene esa clave. Además no hay datos de cómo le va en español.
**Para probarlo hace falta que Martín consiga la clave.** La prueba sería la
misma tanda de treinta casos con Jev en la primera llamada.

# FICHA 70 — La traducción caso por caso, antes del código

17 y 18-oct-2026. Viene de la 67, la 68 y la 69. Decidido por Martín: **primero se fija la traducción del modelo,
caso por caso sobre las 58; después se escribe el código contra lo que quede.** El tablero de producción no se toca
en esta fase.

## Por qué en este orden

- **La traducción es lo que el código va a leer.** Si cambia después, el código escrito contra ella se rehace.
- **Probar todo junto mezcla las causas.** El 17-oct, la mitad de lo que parecía falla del modelo era del ejecutor
  del banco.
- **Las grabaciones de esta fase son el examen del código de la siguiente.**

## Lo medido el 17-oct

Banco: `banco_pruebas/nexos/desmenuzado.py`, forma `contrato2`, sobre sus 174 casos y su corrector por contenido.

| Corrida | Modelo | Casos | Reserva |
| --- | --- | --- | --- |
| `c2_1`, primer contrato 2 | Gemini, gratis | 108; 121 con el corrector arreglado | 57 de 75 |
| `c2b_p1` y `c2b_p2`, esquema por comando y orden obligatorio | Gemini, paga | 137 las dos, iguales caso por caso | 61 de 75 |
| `c2c_haiku_1`, con lo que dijo la entrevista de Haiku | Haiku 5.5, OpenRouter | 151 | 68 de 75 |
| `f9_g174`, la ficha 9 del 14-oct, la marca | Gemini | 167 | |

- **Como en `c2c` cambiaron a la vez modelo y contrato,** falta Gemini sobre ese mismo contrato para separarlos.
- **La cuota gratis del día se acabó cerca de los 220 pedidos**, no en los 500 anotados el 16-oct. El banco ahora
  frena solo al primer rechazo por cuota del día.
- **Gasto de la paga del 17-oct:** 0,85 dólares.

## Lo que mostraron juntas la ficha 9, los nexos, los ejemplos y las entrevistas

1. **Lo que más sube son los ejemplos resueltos elegidos por parecido.** Con ellos Gemini dio 12 de 12 tres veces
   en la reserva limpia Z, FICHA 67.
2. **El control de que no quede nada sin asignar.** La ficha 9 hace cortar el mensaje con las palabras literales del
   cliente, el código mira que todo quedó citado, y si falta algo se le devuelve al modelo una vez.
3. **El modelo ve la parte pero no sabe dónde ponerla.** Es la causa más repetida en todas las entrevistas. Se
   arregla con la definición de cada comando y cada campo, no con reglas sueltas.
4. **Elegir entre 58 números confunde.** Lo dijeron Gemini y DeepSeek el 14-oct: de 10 a 15 acciones con nombre. Lo
   que ayudó de los números fue recibir la guía justa del caso.
5. **Sobra lo que no aplica al mensaje y falta lo de los productos ya mostrados**: colores con stock y datos técnicos.
6. **Un ejemplo se copia tal cual**, así que va en la forma exacta que se pide.
7. **Hay cosas que ningún modelo hizo bien con ningún formato**: el mismo producto a varios destinos, contar "el
   resto", sostener las exclusiones, dar el total cuando cambia el pedido. Las hace el código; el modelo sólo nombra.
8. **El esquema estricto lleno de campos opcionales hace daño.** Gemini rellenaba campos que no iban y una vez entró
   en un bucle de 65 mil tokens; Anthropic lo rechaza. Cada comando lleva sólo sus campos.

## La versión 3: lo que recibe el modelo

Una sola llamada.

1. **Un prompt fijo chico:** el rol y cinco pasos. Cortar y citar, asignar a un comando, referenciar, conservar
   todo lo que pidió el cliente, ordenar.
2. **El menú de diecisiete comandos**, los de `contrato2.py`, cada uno con una línea de cuándo va y cuándo no.
3. **El índice de la tienda, fijo y sacado de la fuente:** rubros con marcas, palabras que no son rubro, lo que no
   se vende con su alternativa, campos filtrables y medios de pago. Al ser fijo entra en el caché del proveedor.
4. **Lo que aplica a este mensaje, elegido por el código:** los temas de política parecidos, con lo que abarca cada
   uno, y de cuatro a seis ejemplos resueltos.
5. **El estado como datos numerados:** M1.. lo mostrado con todos sus datos, P1.. el pedido con cantidad y destino,
   la búsqueda vigente, los datos del cliente y los dos últimos intercambios.
6. **El control del código antes de ejecutar:** todo citado, campos obligatorios, listas cerradas y referencias que
   existen. Si algo falla, una devolución al modelo.
7. **El mismo modo para Gemini y Haiku:** el esquema compacto en el prompt, `contrato2.esquema_texto`, y la
   validación en el código.

**Lo que dice el cliente es la segunda fuente de verdad; la primera es la tienda.** El modelo no saca, no suaviza
ni agrega nada de lo que pidió: lo que no tiene campo va como `sin_campo` con sus palabras.

**El límite del bot:** resuelve cuando cada artículo queda con producto y destino sin dudas. Si el código encuentra
algo que falta, sobra o está fuera de la lista del cliente, pregunta una vez sólo eso. Si sigue sin cerrar, hace lo
que configure la tienda: volver a preguntar o pasar a una persona.

## El método de la fase de las 58

1. **La tabla de las 58:** el mensaje, el estado escrito a mano si es de memoria y los comandos correctos. La
   escribe la sesión y la revisa Martín, porque ahí se decide la conducta.
2. **Uno afuera:** el caso que se prueba no puede estar entre sus propios ejemplos.
3. **Caso por caso en el orden de los grupos,** A, B, C, D, E, F, G y H, I y J, K, con Gemini y Haiku.
4. **Un cambio entra sólo si sirve para una clase y no rompe ningún caso anterior.** Cada regla nueva dice qué casos
   arregla; una que arregla uno solo no entra. El prompt fijo tiene techo de largo.
5. **La reserva limpia de los 174 se mide sólo al cerrar cada grupo,** y nunca se usa para ajustar.
6. **Costo:** cada cambio de prompt pide volver a correr en vivo lo anterior. Se juntan varios casos por cambio, la
   vuelta de control va con una repetición y las tres repeticiones quedan para el cierre de cada grupo.

## Lo que queda abierto

- **El pedido como operaciones o como pedido entero.** La ficha 9 hacía escribir el pedido entero y dio mejor, pero
  en charlas largas se pierde, que es lo de K10 y K11. Se miden las dos en los casos de pedido.
- **El efectivo de Q067:** el cliente pide un medio que la tienda no toma. El contrato lo manda a `otro` para que el
  código avise; el corrector espera la palabra. Decide Martín.
- **Las ocho fallas de pedido de `c2c_haiku_1`** pueden ser del ejecutor del banco: se miran antes de culpar al
  modelo.

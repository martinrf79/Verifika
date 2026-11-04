# FICHA 87 — Lo que se rompe después del primer mensaje

4-nov-2026, con Martín. **Toda sesión nueva arranca por acá hasta que una logre el avance medido del final.** No se
abre otra línea de trabajo antes. Si una sesión no avanza, lo escribe al final de esta ficha y la siguiente sigue.

## El problema, en palabras de Martín

El bot responde bien un mensaje, incluso el complejo de tres destinos, y al segundo o tercer mensaje de WhatsApp aparece
uno o más errores básicos. Se arregla una cosa y se rompe otra.

## Lo medido el 4-nov

Las 42 charlas reales, `banco_pruebas/examen_real/`, corridas el 3-nov con el bot deployado. Los 113 turnos se calificaron a
mano contra el catálogo, la tabla de compatibilidad y la FAQ. La lista turno por turno está en
`banco_pruebas/examen_real/fallas_3nov.md`.

- Turnos: 80 bien, 25 mal, 5 dudosos y 3 sin correr.
- **De las 30 charlas con dos mensajes o más, 16 tienen al menos un error.** Es lo que Martín ve en WhatsApp.
- **7 turnos que el 31-oct estaban bien salieron mal el 3-nov**, sin que nadie lo notara: es el "se arregla una cosa y se
  rompe otra".
- La plata calculada por el código no falló en ningún turno.
- Revisado contra lo que devolvieron las herramientas, de las 25 fallas:
  - en 11, el dato correcto le llegó al modelo y escribió otra cosa;
  - en 10, el modelo no pidió el dato; son un solo caso, el origen, repetido en 10 charlas;
  - en 4, el modelo lo pidió y la herramienta no lo dio: "PS5" y "Samsung" no filtran.

**Descartado por medición, no volver a proponerlo:** la primera lectura que traduce el mensaje a una forma para el código,
el intérprete de antes con otra consigna. `banco_pruebas/examen_real/traduccion.py`, contra la lista correcta escrita
antes de correr: 47% de las partes y 40 de 80 turnos. El primer mensaje de un pedido largo, 35%. Sale peor que el agente
de hoy. Faltan 33 turnos, cortados por la cuota de la gratis, y aunque salieran todos bien no pasaría del 60%.

## Por qué pasa: cuatro causas, con dónde viven

1. **El pedido no vive en el código, lo reescribe el modelo en cada turno.** `agente.presupuesto` arma el pedido con
   `reemplaza: True` y arranca de `E.leer({})`: cada presupuesto parte de cero con lo que el modelo escribe de memoria.
   Lo que estaba bien en el turno 1 puede romperse en el 2. Casos: 854f1bea2c, el código armó 3 memorias a Concordia y
   el modelo lo rehízo con 4; K20 y K21 en la vara.
2. **El cierre depende de que el modelo llame a las herramientas en orden.** Escribe "te paso los datos" o "te apliqué el
   descuento" sin haber llamado a `cobrar` o con el pago a definir. Casos: b8bb001ee8 t4, 58b5a11775 t4, fe67b477ec t6.
3. **Lo que el bot dijo antes pasa a ser verdad para el modelo.** Un dato inventado en un turno se repite en los
   siguientes, porque está en la historia. Casos: el Pandora "compatible con PS5" en b8bb001ee8 t1 a t3.
4. **Lo que el cliente pregunta se toma como decidido.** "¿Tenés descuento con tarjeta o transferencia?" se anota como
   pago por transferencia; "Tarjeta Naranja" se acepta por Mercado Pago aunque la herramienta dijo que no se toma. Casos:
   781919fa60 t2, 7f8cd4a5ca t6.

Y una causa de organización, que explica los 7 turnos rotos: **no hay candado sobre las charlas reales.** La vara de
`tests/test_agente.py` son 26 charlas grabadas y da 74 de 75; el examen real no está en la batería, así que un cambio
puede romper un turno real sin que ningún test falle.

## Las soluciones, en este orden

Cada una dice qué fallas de `fallas_3nov.md` cubre. Se hace una por sesión.

1. **El candado de lo que ya anda.** Un test que corre las 42 charlas sin modelo con `examen.py --codigo`, repitiendo lo
   que escribió el modelo el 3-nov, y compara lo que pone el código —presupuestos, cobro y lo que borra el verificador—
   en los 80 turnos bien. Si un cambio altera uno, el test falla y se mira antes de seguir. No arregla ninguna falla:
   impide que se rompa lo que anda, y va primero porque sin él lo demás repite el círculo.
2. **El pedido como estado del código.** Es la FICHA 86, pasos 5 a 7, ya construida y sin conectar: el modelo manda solo
   el cambio con la cita del cliente y el borrador lo aplica sobre el pedido guardado. El paso 5 se midió en 69 de 75 por
   una causa ya vista: el precio pedido va a `cotizar`, que no anota, y el cambio del turno siguiente no tiene sobre qué
   aplicarse, K16, K20 y K21. Se arregla eso, se conecta y se mide. Cubre la causa 1 y la 4.
3. **El cierre lo hace el código.** Con nombre y medio de pago anotados, el código cobra y pega el link o los datos; el
   modelo no puede escribir que los pasó ni que aplicó un descuento. Cubre la causa 2.
4. **Los datos de producto los pega el código, y lo dicho antes no cuenta como fuente.** El modelo marca el producto y el
   código pega la línea del catálogo y de la tabla de compatibilidad; si en la charla se nombró un equipo, el código
   busca la compatibilidad de cada producto que el modelo nombra. Una oración del modelo sobre un producto no puede
   traer atributos que no estén en lo pegado en ese turno. Es la ficha pegada del 3-nov con lista blanca. Cubre la
   causa 3 y las 11 fallas con el dato a la vista.
5. **El buscador toma el equipo y la marca como condición.** "auriculares PS5" devuelve solo los que la tabla marca para
   PS5; "teclado Samsung" dice que no hay. Cubre las 4 fallas de herramienta.

Si una de estas no mueve el número, se escribe acá por qué y se pasa a la siguiente. No se vuelve a parchear el
verificador con una forma nueva de decir algo.

## El avance que cierra esta ficha

Medido sobre las 42 charlas reales, en tres corridas con el modelo de producción:
- ningún turno de los 80 bien se rompe, lo controla el candado;
- de las 30 charlas con dos mensajes o más, al menos 25 sin ningún error, contra 14 de hoy;
- la plata sigue sin errores.

## Lo que hizo cada sesión

- 4-nov: el diagnóstico, la lista de fallas y la medición que descarta la traducción. Ningún cambio en el bot.

# Lista de fallas del examen real, para aprobar

Fuente: las 42 charlas reales de WhatsApp, `banco_pruebas/examen_real/`. Se calificó a mano la corrida del 3-nov,
que es el bot deployado con el modelo de producción, turno por turno, contra el catálogo, la tabla de compatibilidad y la FAQ.

## El número de hoy

- 113 turnos en total.
- 80 bien.
- 25 mal.

Corrección del 4-nov: la primera versión tenía 27 mal. Dos eran errores míos de calificación, la 7c7947db9f turno 1 y la 33dbb56c1b turno 1: el dato que dio el bot sí estaba en la ficha.
- 5 dudosos, que decidís vos.
- 3 sin correr: la charla b8df72a33c no se guardó porque el modelo no contestó un turno.

Ojo: el `PENDIENTE` decía 87 bien. Mi conteo es más estricto: encontré 7 turnos que el 31-oct estaban bien y el 3-nov
salieron mal, sobre todo por compatibilidad con la PS5.

Para cada falla va lo que el cliente dijo, lo que hizo mal el bot y lo que tiene que hacer, que es la casilla a aprobar.

---

## Clase 1. Inventa un dato del producto. 8 turnos, 1 y 9 anuladas

1. ANULADA, estaba bien: el DataTraveler de Kingston sí dice Tailandia o Malasia. **7c7947db9f, turno 1.** "¿Tenés algún artículo que no sea fabricado en China?"
   Mal: dice que Kingston y SanDisk se fabrican en Tailandia o Malasia. La ficha de Kingston dice China, Taiwán o Corea.
   Debe: nombrar solo orígenes que estén en la ficha. Intel y AMD, Malasia o Vietnam, está bien.

2. **7f8cd4a5ca, turno 3.** "¿Cuál calienta menos?", sobre placas de video.
   Mal: dice que la Asus Dual RTX 4060 tiene diseño térmico eficiente. La ficha no habla de temperatura.
   Debe: decir que no tiene ese dato y ofrecer lo que sí tiene.

3. **bf4a05c745, turno 2.** "¿Y cuál sí?", un mouse que ande con la Play.
   Mal: dice que el Redragon Cobra M711 funciona perfecto en la consola. La tabla de compatibilidad no lo respalda.
   Debe: decir que no tiene confirmada la compatibilidad con la consola.

4. **b8bb001ee8, turno 1.** "¿Tenés auriculares que anden con la PS5?"
   Mal: ofrece el Zeus X y el Pandora como compatibles. La tabla dice que en la consola no andan.
   Debe: ofrecer solo los que la tabla marca para PS5, como el HyperX Cloud Stinger 2.

5. **58b5a11775, turno 1.** La misma pregunta y la misma falla.

6. **b8bb001ee8, turno 2.** "Sí, el más eco en negro."
   Mal: corrige el Zeus X, pero ofrece el Pandora como compatible, y no lo es.
   Debe: ofrecer solo el Stinger 2, o decir que es el único.

7. **b8bb001ee8, turno 3.** El envío a Villa del Prado.
   Mal: le pasa el Pandora diciendo que sí es compatible.
   Debe: no afirmar una compatibilidad que la tabla niega.

8. **c3391deb1a, turno 1.** El teclado más económico.
   Mal: dice que el Genius KB-110X es silencioso, ideal para oficina y resistente a derrames. La ficha dice membrana y gaming, nada más.
   Debe: decir solo lo que dice la ficha.

9. ANULADA, estaba bien: la ficha del KB-110X dice resistente a derrames. **33dbb56c1b, turno 1.** Un teclado bueno y barato para escribir.
   Mal: el KB-110X muy resistente a derrames, inventado.
   Debe: lo mismo que el anterior.

10. **33dbb56c1b, turno 4.** "Me dijeron que duran más con cable."
    Mal: dice que el Redragon K617 trae un cable USB-C desmontable. La ficha no lo dice.
    Debe: decir solo cómo se conecta según la ficha.

## Clase 2. Esquiva el pedido de "menos partes chinas". 10 turnos

El mismo mensaje del cliente en 10 charlas: dos auriculares, dos mouse, dos memorias, "las menos partes chinas posibles",
tres destinos, setenta treinta.

Charlas: d0c439c575, b5ddaad494, 83e58acb78, 386b8a84eb, 6344deed8c, 08e6c44238, fe67b477ec, 157b658bc8,
96b39fa8fd y 781919fa60, todas en el turno 1.

Mal: dice "el origen de fabricación es global" y elige el teclado Redragon, que es marca china y fabricado en China.
Debe: decir lo que dicen las fichas, que casi todo se fabrica en China. Y elegir, dentro de eso, lo que menos parte china
tenga según la ficha, por ejemplo la marca no china. Sin decir "global".

## Clase 3. Arma mal el pedido. 1 turno

11. **854f1bea2c, turno 1.** El cliente pide 3 memorias a Concordia, con el teclado, y "los otros dos" a Posadas.
    Mal: manda 4 memorias a Concordia y ninguna a Posadas.
    Debe: Concordia, un teclado y tres memorias. Posadas, un auricular y una memoria.

## Clase 4. El pago: anota o afirma lo que el cliente no dijo. 3 turnos

12. **781919fa60, turno 2.** "Decime si tenés descuento con tarjeta o transferencia, qué me conviene más."
    Mal: aplica transferencia a las dos partes, y el cliente solo preguntó.
    Debe: contestar la diferencia y preguntar con qué paga cada parte.
    Ojo: con el código de hoy, este turno sale peor, con los presupuestos vacíos.

13. **7f8cd4a5ca, turno 6.** "Tarjeta Naranja."
    Mal: dice que se puede pagar a través de Mercado Pago. La FAQ no lo dice.
    Debe: decir que con tarjeta se toman Visa, Mastercard y Amex, y ofrecer los otros medios.

14. **fe67b477ec, turno 6.** "Sí."
    Mal: dice que aplicó el descuento por transferencia, pero el pago sigue a definir y sin descuento.
    Debe: no decir que aplicó algo que no aplicó, y preguntar el medio.

## Clase 5. Promete y no hace. 2 turnos

15. **b8bb001ee8, turno 4.** "Joaquín."
    Mal: dice "te paso el presupuesto" y no lo pega. Dice que anotó el negro y pregunta el color dos veces.
    Debe: pegar el presupuesto, o preguntar una sola vez lo que falta.

16. **58b5a11775, turno 4.** "Joaquín, no tengo MP."
    Mal en la corrida: dice "te paso los datos de la transferencia" y no llegan.
    Con el código de hoy, la promesa se borra, pero los datos siguen sin llegar. Queda a medias.
    Debe: pasar los datos de pago o el link.

## Clase 6. No contesta lo que preguntó. 1 turno

17. **badf4f114b, turno 2.** "El último de Samsung."
    Mal: no contesta nada sobre Samsung y vuelve al K380.
    Debe: decir si tiene o no, o preguntar qué producto de Samsung.

---

## Dudosos, decidís vos

- **7f8cd4a5ca, turno 2.** "Aparte de monitores y placas, ¿tenés otra cosa?" Nombra solo notebooks y periféricos. Es verdad, pero incompleto.
- **06d02631b7, e105d5a00b y a96e63a0cb, turno 1.** Dice que el KB-110X es ideal para oficina, y la ficha dice gaming. El resto del turno está bien.
- **815c0c9b65, turno 4.** "¿Te tildaste, sos una máquina?" Contesta "me colgué" y no dice si es una máquina. Al empezar ya se había presentado como asistente automático.

## Sin correr

- **b8df72a33c, turnos 1, 3 y 4.** El 31-oct fallaban por el origen, por un teclado de más y por un Mercado Pago no dicho.

---

## Lo que esta lista muestra

- **18 de las 25 fallas son la misma cosa:** el modelo escribe un dato que no está en la ficha, en la tabla o en la FAQ. Es la clase 1, la 2 y parte de la 4.
- **La plata calculada no falló en ningún turno.** Lo único que falla en la plata es lo que el modelo dice sobre ella.
- **7 turnos que estaban bien el 31-oct salieron mal**, sobre todo por la compatibilidad con la PS5. Por eso hace falta medir todo el examen en cada cambio, y no solo lo que se arregló.

Si aprobás esta lista, queda como la vara fija: terminado es cuando estas 25 pasan sin que se rompan las 80.

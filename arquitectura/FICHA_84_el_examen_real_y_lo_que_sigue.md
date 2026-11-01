# FICHA 84 — El examen real y lo que sigue

31-oct y 1-nov-2026, con Martín. Lo hecho está en `git log`; esto es lo que una sesión nueva necesita para seguir.

## Dónde estamos

- En producción: el agente de la FICHA 83, con lo del 31-oct y 1-nov: el buscador da los campos que pide la consulta,
  la hoja de reglas de la FAQ va siempre en la consigna, el verificador marca la regla negada y le pasa lo que dice la
  FAQ, la identidad reconoce 878 de 880 productos por su nombre, lo ambiguo del pedido se resuelve por lo mostrado, y
  si falta un criterio del cliente el código hace la búsqueda y se la pasa al modelo.
- La vara sin modelo: 74 de 75. La vara real es el examen: `banco_pruebas/examen_real/`, 42 charlas de WhatsApp.
  El 31-oct, 72 de 113. El 1-nov, `corrida_1nov.jsonl`: de los 41 que fallaban, unos 12 bien, unos 19 mal y unos 10
  sin decidir; después, las 11 de "partes chinas" bien, `corrida_1nov_criterios.jsonl`.
- Descartado por medición: el producto por id, 70 de 75; commit 3e04b67, revertido.

## Lo que sigue mal, por clase

1. Plata y cierre: la tarjeta Naranja aceptada sin respaldo; los datos de pago que no llegan al cerrar.
2. El color repreguntado cuando el producto ya lo trae, y dos renglones del mismo modelo con colores distintos.
3. Afirmaciones sin respaldo en la ficha: "la que calienta menos", "funciona perfecto en la Play".
4. El pedido que cambia: suma un teclado de más en vez del que faltaba.
5. K13: omite el mayorista; la casilla lo pide.

## El plan para que no sean parches

1. **La vara fija y automática.** Las casillas del examen real escritas una vez, aprobadas por Martín, y el examen
   calificado por código, como `tests/test_agente.py`. Mitad para arreglar, mitad apartada. Nada se declara arreglado
   sin ese número en tres corridas.
2. **El código completa, el modelo no adivina.** Lo que funcionó estas dos sesiones fue siempre lo mismo: que el código
   le dé el dato al modelo o haga lo que el modelo no hizo —la búsqueda que faltaba, la regla, la versión mostrada—. Lo
   que no funcionó fue darle más reglas o más formato, como el id.
3. **Cada arreglo por clase, medido sobre la clase entera** en el banco sin modelo antes de gastar en el modelo: los 880
   productos, cada campo por cada rubro, cada regla de la FAQ.
4. **El pedido como operaciones**, el borrador de la FICHA 71, que el agente hoy saltea: es la clase 4.

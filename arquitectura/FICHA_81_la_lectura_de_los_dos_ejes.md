# FICHA 81 — La lectura de los dos ejes: lo que hace hoy, lo que falla y como seguir

25 y 26-oct-2026, sesion con Martin. Sigue a la FICHA 80. Vive en `app/core/flujo/lectura.py`; la mide
`banco_pruebas/primera_ejes.py` y la controla `tests/test_lectura.py`.

## Lo que cambio

El modelo ya no llena la ficha nativa ni elige la respuesta de la tienda entre trece. Por cada parte del mensaje dice
dos cosas de lenguaje —que hace el cliente: pregunta, pide ver, elige, cambia, saca, cuenta de si, pide una persona o
nada; y sobre que: producto, rubro, lo mostrado, tema, lugar, pedido, pago, tecnologia, la tienda, una persona, el
cliente o fuera— y llena las casillas de los datos: cantidad, variante, destino, condiciones, lo que no quiere, lo que
prefiere, orden, con que anda, lo que quiere saber, lo que afirma, de que parte depende y con que resultado, lo que
tiene que cumplir y si corrige. Aparte, lo que vale para todo: orden, tope, pago, cuantos son, si rehace, lo que
contesta y lo que dice de si.

El codigo hace el resto, sin modelo:
- **El cruce**: los dos ejes van a la accion del menu de siempre; el ejecutor, el borrador y la redaccion no cambian.
- **La cobertura**: cada frase del mensaje tiene que tener sus anclas —lugares del padron, montos, porcentajes, rubros,
  modelos, marcas y colores— en algun valor de la salida. Lo que no, vuelve al modelo con su lectura en una segunda
  vuelta. Sobre 290 lecturas grabadas marca 8, con las dos perdidas reales.
- **La forma normal**: un lugar suelto reparte lo pedido; pedir ver con destino es elegir; dos rubros en una parte son
  dos; un destino con varios lugares reparte la cantidad; una parte repetida cuenta una; un renglon elegido en varias
  partes sale y entra repartido.
- **Las definiciones**: el color en plural es el de la tienda; preguntar por lo mostrado es el producto; el destino del
  envio es un lugar; "si pasa de X, saca Y" es el tope con lo que sale; cambiar el destino sin pedido es cotizar el
  envio nuevo; que le sirve de un rubro a lo suyo es compatibilidad; el precio con destino es tambien su envio; elegir lo
  que ya esta en el pedido cambia su cantidad; cambiar todo el pedido por un criterio es otro orden para todo; el mas
  algo de un rubro es el orden de su busqueda.

## Lo medido, contra la ficha nativa, con el criterio escrito antes de correr

| | ficha nativa | dos ejes |
| --- | --- | --- |
| la cadena entera de las 58, tres repeticiones | 55 de 65 | 58, 57 y 58 |
| los siete de produccion | 6 de 7 | 6 de 7 |
| las 58 sueltas, lo que lee el cliente | 62 de 74 | 70 de 74 |
| las 48, el pedido BIEN | 36 | 36 |
| las 48, mal sin avisar | 9 | 4 |
| las 58, turnos con todos sus datos | 65 de 105 | 76 de 105 |

Lo que hizo ganar no fue la consigna: la primera corrida cruda salio peor que la ficha nativa. Fue el codigo sobre la
salida del modelo. Cambiar palabras de la consigna mueve unos cuatro turnos para cada lado: no se sigue por ahi.

## Por que no esta en produccion

Lo frena `tests/test_variantes.py`, el control con clases que no estan en las 58 ni en las 48: el mas vendido 5 de 6
contra un piso de 4, bien; siete articulos 9 de 10 contra 10; lo mejor para todo el pedido 4 de 10 contra 10. La causa
de lo mejor: la consigna nueva no tiene la definicion que tenia la de produccion, "lo mas caro es lo mejor, la gama alta,
la mejor calidad", y el modelo deja el orden vacio en "quiero todo de gama alta".

## Lo que el codigo puede y no puede con lo que trae el modelo

Puede: certificar cada producto, atar condiciones a campos, toda la plata, lo que senala de la libreta, las
dependencias, el reparto de destinos, partir y deduplicar partes, detectar lo perdido con ancla y pedir otra lectura.

No puede sin vocabulario o sin el modelo: corregir el acto cuando el modelo confunde pregunta con decision; saber que
"gama alta" es mas caro si el orden vino vacio; recuperar lo perdido sin ancla, "los auriculares estan bien"; decidir lo
ambiguo, "me gusta el G305"; recomendar u opinar.

## Lo que sigue, en orden

1. **El vocabulario de ordenes**, aprobado por Martin el 26-oct: un defecto en el codigo y lo que cada tienda cambie en
   su `alias.json`, como `marcador.RESPUESTAS`. Se usa solo si el modelo dejo el orden vacio y las palabras que copio lo
   dicen. Se mide gratis con `primera_ejes.py --medir --cob` y `variantes.py` sobre lo grabado.
2. **Siete articulos, 9 de 10**: leer la forma que pregunta en vez de anotar, en `variantes_corridas.jsonl`.
3. Con la bateria verde, el push deploya. Despues, `produccion.py` sobre las charlas reales.
4. Lo que sigue mal en las tres repeticiones: C14, C27, C40, C50, C52, K20, K21 y P06; cada uno por su clase.
5. Lo pendiente del camino vivo: `redaccion._envio` cae con un envio sin costo, visto en C34 con una lectura rota.

## El gasto

Del 25-oct, con la paga y el ok de Martin: 1,11 dolares del tope de 1,60. Las repeticiones cuestan como corridas
nuevas, porque la consigna cambia y no vuelve lo guardado.

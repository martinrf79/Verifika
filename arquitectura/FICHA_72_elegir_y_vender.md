# FICHA 72 — El modelo elige la lectura, y la llamada de venta

20-oct-2026, con Martín. Plan para una sesión nueva. Sale de lo medido con `banco_pruebas/simulador.py`.

## Dónde quedó

- El borrador, FICHA 71, está en vivo. Si lo dicho no cierra, `borrador._proponer` arma las lecturas posibles con su
  costo y propone la que cierra con los números del cliente. Si empatan, pregunta entre ellas.
- En WhatsApp, 19-oct 20:01: el primer turno ya pregunta entre las lecturas que cierran. El segundo falla: "el teclado va
  aparte, a Posadas" el modelo lo anota como un teclado nuevo, y con el teclado aparte "los otros dos" pasan a ser tres,
  una lectura que el código no tenía. Termina preguntando dos veces por el teclado. Es el caso real que falta juntar.

## Lo que midió el simulador

La multipregunta de los siete artículos, cuatro guiones, el modelo con las fallas de producción sorteadas.
Presupuesto correcto, sin uno equivocado sin aviso:

- V0, el código de hoy: 46%. Loop del 85% en "el teclado va aparte".
- V1, más la lectura "los otros eran lo que queda": 55%.
- V2, el modelo elige la lectura y pasa a lo dicho: 82% si elige bien el 90%, 62% si el 70%; equivocado sin aviso hasta 40%.
- V3, solo si el modelo coincide con el código: entre 15% y 70%, con loops de hasta 80%.
- **V4, el modelo elige y queda supuesto hasta que el cliente acepta: 89% con 90%, 84% con 70%; equivocado sin aviso cerca de 0.**

La falla del modelo que más pesa es mover un renglón como si fuera nuevo; después, perder el total.

## Lo que se hace, en orden, cada paso en su commit y medido en el simulador

1. **V4 en el bot.** Las lecturas del simulador pasan a `borrador.py`: las de hoy, más "los otros eran lo que queda" y "un
   renglón nuevo al mismo destino reemplaza al de afuera". Una llamada corta al modelo, solo cuando el pedido no cierra:
   el mensaje del cliente y las lecturas, y devuelve el número de una o "ninguna". Lo elegido queda supuesto, con el
   presupuesto y "Entendí tu pedido así", hasta que el cliente lo acepta. "Ninguna" repregunta.
2. **Las cuatro mejoras de V4:**
   - el "sí" a "¿Lo dejo así?" lo toma el código cuando es lo único abierto, sin modelo;
   - las lecturas se le muestran al modelo en palabras del cliente, con sus cantidades y destinos;
   - la elección trae la cita del cliente que la justifica, y el código controla que esté en el mensaje; sin cita, ninguna;
   - el simulador entra a la batería con un piso por guion que solo sube, en `tests/simulador_piso.json`.
3. **La llamada de venta**, la segunda mitad del objetivo. El modelo redacta con los hechos del turno; el código controla
   que cada monto y cada producto del texto salga de los hechos, y si no, manda el texto del código.
4. **Push con el ok de Martín, y WhatsApp.** Cada charla se junta como caso real con `produccion.py --juntar`.

## Costo y demora calculados

Con el modelo de producción: interpretar 0,0012 dólares por turno; elegir 0,0002, solo en turnos que no cierran; venta
0,0008. Una charla de seis turnos, entre 0,012 y 0,014 dólares. La mediana de demora medida es 2,6 segundos; con la
venta, unos 4, y 5 a 5,5 en los turnos que eligen.

## Lo que aporta Martín

Las formas en que un cliente real dice cada complicada, en texto simple. Cada una se vuelve un guion del simulador y
suma al piso.

## Las reglas

- Ningún cambio entra si baja el piso de un guion, la vara de 65, los casos reales o la suficiencia.
- El simulador elige entre variantes; WhatsApp confirma. Sin la clave gratis, la elección del modelo se prueba con
  elecciones escritas a mano.
- Fuentes: Schatzmann y Young, usuario simulado con agenda y modelo de error; Young y otros, varias lecturas con peso;
  τ-bench, aciertos en varios intentos seguidos; Rasa CALM, órdenes cerradas con aclarar y corregir.

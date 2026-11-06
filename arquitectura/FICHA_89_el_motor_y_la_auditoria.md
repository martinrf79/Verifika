# FICHA 89 — La auditoría de las 12 capas, el punto 1 y el motor

6-nov-2026, con Martín. **La sesión siguiente arranca por acá.** Sigue a la FICHA 88: sus cuatro arreglos quedan
reordenados por lo que midió esta sesión.

## Lo que se decidió

- **La respuesta atada a la API queda descartada:** medida el 5-nov, salió peor que r2. No se vuelve a proponer.
- **El camino es un motor con una sola memoria:** la libreta numerada, con el pedido, lo mostrado y lo que quedó
  preguntado, vive en el código. El modelo toca sólo dos puntos: lee el mensaje y redacta. Lo del medio es código.
- **Ante la duda se repregunta.** Repreguntar vale como acertar; errar no.
- **Antes de cambiar el código, se escriben las pruebas que lo miden**, con las habilidades de ECC de
  `.claude/skills/`: `eval-harness`, `ai-regression-testing` y `agent-architecture-audit`.

## La auditoría de las 12 capas, sobre el bot del 6-nov

Con `agent-architecture-audit`, de affaan-m/ECC. De la más grave a la menos grave:

1. **Crítica, HECHO el 6-nov:** lo que dijo el bot contaba como fuente del verificador y como "visto" del candado de
   productos. Un dato inventado una vez pasaba los controles en los turnos siguientes.
2. **Crítica:** el pedido lo reescribe el modelo en cada turno. `agente.presupuesto` arranca de `E.leer({})` y lo que
   manda el modelo pasa a ser el pedido guardado. El estado con libreta de `estado.py` existe y el camino vivo no lo usa.
3. **Alta:** "si compra, armá el presupuesto" y el cierre están sólo en la consigna. `omitidos` corre sólo si el modelo
   llamó al presupuesto.
4. **Alta:** cada turno manda unos 20 mil caracteres antes de la charla: la consigna, la FAQ entera y el mapa de la
   tabla. El pedido entra tres veces: memoria, historial con el presupuesto pegado y el último presupuesto.
5. **Alta:** hasta cuatro mecanismos tocan la respuesta sin contrato entre ellos, en `agente.responder`: la revisión
   interna, las búsquedas que suma el código, las oraciones que se borran y las preguntas que se agregan.
6. **Media:** el historial se corta en 20 mensajes y nada llena el resumen.
7. **Media:** si caen los embeddings, la búsqueda de reglas devuelve vacío dos minutos sin avisar al modelo.
8. **Baja:** las negritas con doble asterisco no se adaptan a WhatsApp.

## El punto 1: separar y traducir

- **La traducción a los nombres de la tienda está resuelta:** FICHA 78, `traduccion_sola.py`, 91 a 99 de cada 100
  frases, con lista cerrada, "otro" y "duda".
- **Lo que falta es separar y etiquetar:** separar el mensaje, 38 de 48 en la FICHA 76; la etiqueta, nuevo, ya en el
  pedido o cambio, 35 de 48 y 74 de 105.
- **El rubro por parecido, mirado caso por caso el 6-nov:** en las 58, 69 de 80 primero y 77 entre los seis. Las 11 que
  fallan son todas del pedido de los siete artículos y ninguna es del embedding: 6 son "los más económicos de cada
  clase" y 3 son "lo demás está bien", que apuntan a la memoria; 2 juntan dos clases en una parte.
- **Cómo lo hacen los sistemas que andan:** Rasa CALM convierte el mensaje en una lista corta de comandos de un menú
  fijo; SMCalFlow etiqueta con referir y revisar sobre el estado; FnCTOD elige primero de qué se trata y después llena;
  un trabajo de 2026 mide que forzar el formato desde el principio rompe el razonamiento.

## El plan, en orden

Cada paso con sus pruebas escritas antes, el candado de las charlas reales y la vara. Uno por sesión.

1. **C55 t3,** "ah no, el otro, y ese me lo llevo": el único turno mal de la vara. Se mira con lo grabado.
2. **El pedido en el código, con la libreta.** Hallazgos 2 y 6: el modelo manda sólo el cambio y el código lo aplica.
   La FICHA 86 tiene el comando `pedido` construido; antes, arreglar lo que midió en 69 de 75: K16, K20 y K21.
3. **Lo obligatorio en código.** Hallazgo 3.
4. **En cada turno, sólo lo que aplica.** Hallazgo 4.
5. **Una sola revisión explícita.** Hallazgo 5.
6. **El punto 1 en el motor:** el modelo razona libre y devuelve la traducción de lo razonado, una cosa por parte; el
   código ata cada parte a la libreta o por parecido, y con varias opciones el modelo elige entre ellas o se
   repregunta. Se mide primero sin modelo, sobre las agendas a mano de `agendas58.py`: si la etiqueta correcta está entre
   las que arma el código.
7. **El formato de WhatsApp.** Hallazgo 8.

Con el 2 al 4 cambia lo que lee el modelo: se regraba la vara y se corre tres veces con la gratis.

## Lo que hizo cada sesión

- 6-nov: la auditoría, la búsqueda en repos y papers del punto 1, las tres habilidades de ECC, el hallazgo 1 arreglado
  y la vara regrabada con SQL, 74 de 75, con la casilla de K18 t3 decidida por Martín. La gratis da 500 pedidos por
  día y se agotó dos veces: K21 se grabó con la paga, 6 centavos.

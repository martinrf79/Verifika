PLAN DE LA LINEA DE BASE, escrito antes de correr (24-nov-2026, FICHA 106, orden de Martin)

Que se mide: el resolvedor por reglas de `reglas/resolver.py`, tal como esta, con sus cortes de `reglas/cortes.json`
y e5 sin ajustar, sobre las 138 frases del examen fijo, `examen.json`, hash en `hash.txt`. Una sola corrida. Nada se
cambia en el resolvedor ni en las etiquetas despues de ver el resultado; un arreglo se mide despues como cambio aparte.

La correccion, en `examen.corregir`, igual para cualquier traductor que se mida despues:
- Por frase. El resolvedor da una salida por frase: ofrece con hasta tres modelos, no_hay o repregunta.
- ofrece acierta si cada modelo ofrecido esta en los aceptables de algun pedido de la frase, ese pedido admite
  ofrecer, sin_dato, no_compatible o rechazar, y, si el pedido pide un orden, el primero ofrecido es el primero de los
  aceptables en ese orden. Si no, erra.
- no_hay acierta si algun pedido admite no_hay; si no, erra.
- repregunta no es acierto ni error: se cuenta aparte, y se marca si algun pedido la admitia.
- Las frases de un pedido son la cuenta principal; las de varios, aparte, porque el resolvedor no separa lineas y
  contesta una sola cosa. Las dudosas tambien aparte.

Por casillero, para saber donde falla: rubro, marca y modelo, comparando lo que el resolvedor reconocio con lo
etiquetado, por frase. Acierto si coincide, de mas si marco algo que no esta, de menos si falto algo.

Informe: N, acierta, repregunta, erra, con y sin dudosas, de un pedido y de varios; casilleros; tiempo por frase,
mediana y p90; costo cero. Diez frases revisadas a mano contra lo grabado. Resultados en `base_reglas.jsonl`.

PLAN DE LA LLAMADA UNICA, escrito antes de correr (24-nov-2026, orden de Martin)

Hipotesis: una sola llamada de Luna que separa, traduce y elige la fila acierta como la cadena de dos llamadas de la
FICHA 105, sin pagar la segunda vuelta de latencia.
- Antes de Luna, los embeddings: el mensaje entero y cada trozo separado por punto, coma, "//" o " y ", contra el indice
  de productos de la tienda, el modelo de embeddings del indice con la clave gratis; 15 del mensaje mas 5 por trozo, sin repetir, hasta 30.
- Luna, con razonamiento bajo, como la llamada 0: el prompt v14f1b con la ficha f1, y al final la tarea del
  verificador podado: por cada fila que pide un producto, las filas de la tienda que cumplen todo y las dudosas con el
  dato que falta. Las filas de la tienda van recortadas como en `podado.fila`.
- El codigo decide como el podado: alguna sirve, ofrece hasta tres; dudosas, repregunta; nada, no hay. El tope de plata
  lo aplica el codigo con el precio de la fila.
Metrica: `examen.corregir` sobre las 102 frases de un pedido, sin dudosas aparte; la de varios, por linea. Tiempo de punta
a punta, embeddings mas Luna, mediana y p90; costo. Tres casos primero; resultados grabados al momento en
`llamada_unica.jsonl`; tope de gasto de la corrida, 15 centavos; diez revisados a mano.
Base para comparar: el resolvedor por reglas, 65 aciertos y 17 errores en las 96 limpias, y lo de la FICHA 105.

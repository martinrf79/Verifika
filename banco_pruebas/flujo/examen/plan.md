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

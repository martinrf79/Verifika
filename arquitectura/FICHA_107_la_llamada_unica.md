# FICHA 107 — LA LLAMADA UNICA: LUNA SEPARA, TRADUCE Y ELIGE LA FILA EN UNA SOLA VUELTA (24-nov-2026)

Esta ficha es para arrancar una sesion nueva. Se lee entera antes de tocar nada. Reemplaza a la FICHA 106 como plan:
la 106 queda como registro de lo medido. Todo esta en el banco, nada en `app/`. El bot en produccion sigue con la
llamada 0 v7 de la FICHA 102.

## 1. Donde estamos, en cinco lineas

1. **El bot en produccion no anda bien en la condicion.** Su llamada 0, la v7, escribe la busqueda en texto libre, y
   despues los embeddings, Jev y el nexo de condicion tienen que volver a adivinar que quiso decir. Ese nexo nunca se
   recalibro, punto 3 de la FICHA 102. En vivo salen frases rotas y "no hay" falsos.
2. **El banco ya tenia las piezas buenas por separado.** La FICHA 104 dejo a Luna separando y traduciendo con la ficha
   del vocabulario, el v14f1b. La 105 dejo al verificador podado eligiendo la fila entre los candidatos, sin errores en
   las frases limpias. Encadenarlas costaba una segunda vuelta de latencia, unos 9 segundos en total.
3. **El modelo chico de la FICHA 106 no anduvo** y se deja: se lo uso para comparar parecido con poco dato, no para
   elegir. Podria volver mas adelante, entrenado con lo que resuelva la llamada unica en produccion.
4. **La llamada unica junta las dos piezas en una sola llamada**, y elegir la fila no agrega tiempo: 5,1 segundos de
   punta a punta, lo mismo que hoy tarda la llamada 0 sola mas los embeddings.
5. **Lo que falla es el orden**, "el mas barato", y es de codigo. Arreglado eso y corridas las 41 frases que faltan, se le
   propone a Martin cablearla en el bot.

## 2. Como funciona la llamada unica

Guion: `banco_pruebas/flujo/examen/llamada_unica.py`. El plan, escrito antes de correr, en `examen/plan.md`.

1. **Los embeddings, antes de Luna.** El mensaje entero trae los 15 productos mas parecidos del indice de la tienda. Si
   el mensaje tiene varios trozos, cortados por punto, coma, punto y coma, "//" o " y ", cada trozo trae 5 mas, sin
   repetir, hasta 30. Media de 21 candidatos. Usa el indice que ya arma el bot, por `jev_filas._fuente`, y la clave gratis.
2. **Luna, una sola llamada.** El prompt es el v14f1b con la ficha f1, el mismo que separa y traduce, mas un parrafo al
   final, el prompt `v14f1u` dentro del guion:
   - por cada fila suya que pide un producto, cuales de las filas de la tienda cumplen todo lo que pide, en `sirven`, y
     cuales cumplirian pero les falta un dato, en `dudosas`, con el dato;
   - el orden pedido, de la lista cerrada de `conceptos.json`, o `ninguno`;
   - preguntar por un producto tambien es pedirlo; solo es "no producto" la fila que no nombra ninguno, como el envio;
   - todas las filas de la tienda estan en stock; no se suponen datos que la fila no trae.
   Las filas de la tienda van recortadas como en el verificador podado, `traductor/podado.fila`.
3. **El codigo decide**, como el podado: aplica el tope de plata con el precio de la fila; si alguna sirve, ofrece hasta
   tres, ordenadas si se pidio orden; si hay dudosas, repregunta; si no queda nada, no hay. La plata se lee solo con una
   palabra de plata, "mil", "lucas", "pesos", o despues de "hasta", "menos de", "no pase": los numeros de los modelos,
   "RTX 4080" o "L5590", no son plata.

## 3. Lo medido

**El examen fijo**, `banco_pruebas/flujo/examen/`, armado en esta sesion: 138 frases reales de clientes de produccion que
ninguna prueba ni ajuste uso antes, 193 pedidos etiquetados por casillero con los ids de `conceptos.json`, la respuesta
correcta como regla sobre el catalogo en `examen.aceptables`, congelado con hash. Ver la seccion 5.

**La llamada unica**, corrida 2, 97 de las 138 frases: la cuota gratis de embeddings se acabo y las 41 que faltan van otro
dia, sin pasar a la paga.

| Sobre las mismas 78 frases limpias de un pedido | acierta | repregunta | erra |
| --- | --- | --- | --- |
| llamada unica | 55 | 17 | 6 |
| resolvedor por reglas, el mejor de la FICHA 106 | 55 | 13 | 10 |

- **El producto correcto esta entre los candidatos** en 70 de 70 frases limpias que tienen respuesta. Los embeddings no
  son el problema: el problema es elegir y ordenar.
- **Latencia:** de punta a punta, mediana 5,1 segundos y p90 7,8. Los embeddings, 0,9 y 1,5; se piden uno por trozo, en
  serie, y se pueden pedir juntos. Luna sola, 4,1 y 6,5, lo mismo que la llamada 0 de hoy.
- **Tokens y costo:** unos 3.300 de entrada y 490 de salida por mensaje; 5,6 centavos las 97 frases, unos 6 dolares cada
  10 mil mensajes.
- **Las frases de varios pedidos**, por linea: 25 aciertan, 8 repreguntan y 19 yerran, en 52 lineas. De las 19, 13 son del
  orden: Luna eligio el rubro bien, pero el mas barato de la tienda no estaba entre los candidatos. Las otras 6 son
  lineas que solo preguntan, "a cuanto me queda", marcadas como producto.
- **Los 6 errores de las limpias:** 3 de orden, como arriba; 2 de eleccion, "la RTX 4080 Super de Asus" que dio no hay y
  "una silla Noblechairs Epic roja" que eligio routers de la frase anterior; y 1 de plata, "te doy 30 mil por el G Pro X",
  que es regateo y no tope.
- **La corrida 1** tuvo dos fallas del guion, no de Luna: la plata leida en los codigos de modelo y la pregunta por un
  producto marcada como no producto. Queda grabada en `llamada_unica_c1.jsonl` y no cuenta.

**El resolvedor por reglas** de `reglas/`, medido en esta sesion contra el examen y las tres muestras de antes: de 55
aciertos y 21 errores a 65 y 17 en las 96 limpias, con arreglos de clase. Queda archivado: es un prototipo que el bot no
usa. Lo medido, en la FICHA 106, seccion 4, paso 2.

## 4. Lo que sigue, en este orden

1. **El orden sobre todo el rubro.** Hoy el codigo ordena solo entre las filas que eligio Luna, y el mas barato de la
   tienda puede no estar entre los candidatos. El arreglo de clase: cuando los embeddings traen un rubro, sumar a los
   candidatos, por codigo, los modelos mas baratos y mas caros de ese rubro, para que Luna pueda elegirlos y el codigo
   ordene sobre ellos. Se mide sobre lo ya corrido, cambiando solo eso, y el plan se escribe antes en `examen/plan.md`.
2. **Correr las 41 frases que faltan**, `python3 banco_pruebas/flujo/examen/llamada_unica.py`, que retoma lo grabado. Si
   la cuota gratis de embeddings vuelve a cortar, se sigue al dia siguiente.
3. **Pedir los embeddings juntos**, en una sola llamada por mensaje, y medir la latencia.
4. **Las lineas que solo preguntan**, "a cuanto me queda", que hoy salen como producto: mirar las 6 contra lo grabado.
5. **Proponerle a Martin el cableado en `app/`**, con su ok, en una ficha propia: la llamada unica en lugar de la
   llamada 0 v7, del nexo de condicion y de Jev; los nexos de tema y destino y la segunda llamada quedan. Antes se
   compara con el bot de hoy en las 26 charlas de la vara, `tests/test_flujo_nuevo.py`, 58 de 75, y con `segunda.py
   --correr`. Se dice que se borra.

Mas adelante: el modelo chico, entrenado con las salidas de la llamada unica en produccion, para lo que se repite.

## 5. El examen fijo, como se usa

- **Los archivos**, en `banco_pruebas/flujo/examen/`:
  - `produccion_bruto.json`: los mensajes de clientes de produccion, vivos y archivados, bajados el 24-nov con la cuenta
    de solo lectura, solo el texto, con telefonos, CUIT, tarjetas y mails tapados.
  - `pozo.py` y `pozo.json`: lo que nada uso, sin las 48 de la FICHA 105, muestra2, muestra3, sus casos base ni las
    frases del ajuste de e5.
  - `etiquetas.py`: las etiquetas, con el formato explicado en su encabezado.
  - `examen.py`: congela, controla y corrige. `examen.json` y `hash.txt`, lo congelado.
  - `plan.md`: los planes de cada medicion, escritos antes de correr.
- **La correccion**, `examen.corregir(e, dec, of)`, igual para cualquier traductor: ofrecer acierta si lo ofrecido esta en
  los aceptables de un pedido que admite identificar y respeta el orden pedido; no hay acierta si algun pedido lo admite;
  repreguntar se cuenta aparte.
- **Que se informa:** las frases de un pedido sin dudosas son la cuenta principal; las dudosas y las de varios pedidos,
  aparte. Siempre aciertos y errores juntos: un cambio que baja errores tapando aciertos no mejora, como vio Martin.
- **Ya se miro para hallar causas** del resolvedor y de la llamada unica: sus numeros pesan menos que los de una muestra
  nueva. Para comparar dos caminos sirve igual, porque los dos se miden sobre las mismas frases.

```bash
python3 banco_pruebas/flujo/examen/examen.py --verificar          # el examen no cambio
python3 banco_pruebas/flujo/examen/llamada_unica.py 3             # tres casos, antes de gastar
python3 banco_pruebas/flujo/examen/llamada_unica.py               # todo, retoma lo grabado
python3 banco_pruebas/flujo/examen/llamada_unica.py --informe     # sin gasto
```

El guion corre con el python del sistema y necesita la clave de Luna y la gratis de embeddings en el entorno. Tope de
gasto por corrida, 15 centavos, en `llamada_unica.TOPE`. Para correr otra variante, se mueve `llamada_unica.jsonl` a otro
nombre y se anota en el guion, como la corrida 1.

## 6. Lo que se probo y no se repite

- **Casilleros cerrados sin ver las filas:** es el extractor a un esquema canonico de la FICHA 105, 38%.
- **El modelo chico de embeddings como traductor:** e5 chico pasa 0,9 de parecido con pedazos cortos, "rosario" es
  rosado y "rio" es rojo; ajustado con 1.513 pares no generaliza. FICHA 106.
- **El nexo de nombrado del bot sobre la frase cruda:** espera la linea limpia de la llamada 0; con la frase cruda toma
  relleno como modelo y junta dos modelos.
- **`numeros.py` en el filtro del resolvedor:** no movio nada.
- **Dos llamadas, Luna separa y el verificador elige:** anda, pero suma una vuelta de latencia. La llamada unica lo
  reemplaza.

## 7. Como se trabaja, lo aprendido en esta sesion

- **Leer las fichas 102 a 105 antes de proponer.** En esta sesion se propuso dos veces algo ya descartado, y Martin
  perdio respuestas en reencauzar.
- **Respuestas cortas, una idea por vez, y con lo que cambia para el cliente**, no solo el numero.
- **Cada cambio, aciertos y errores juntos, en todas las muestras.**
- **Un error del guion no es un resultado:** antes de creer un numero, clasificar cada falla contra lo grabado.
- **El push se hace al final, con lo que aporto**, y se confirma antes que lo que va no deploye.

## 8. Lo pendiente de Martin

- **El aviso de la carga del catalogo** quedo arreglado el 24-nov, con el ok de Martin: del nombre del modelo solo
  cuenta lo que lleva unidad o el tipo de memoria DDR, `coherencia_datos.valores_del_nombre`, con su test
  `tests/test_coherencia_modelo.py`. La proxima carga tiene que salir sin incoherencias.
- **El cableado en `app/`**, cuando la seccion 4 lo deje listo.

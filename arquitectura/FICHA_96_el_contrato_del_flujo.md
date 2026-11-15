# FICHA 96 — El contrato del flujo: los pasos de un mensaje, en orden, y la forma de lo que pasa entre ellos

15-nov-2026, sesión con Martín. Sigue a la FICHA 95. **Es la lista para aprobar antes de pasarla a código.** Cada paso
dice quién lo hace, qué recibe, qué entrega y si ya está medido. Lo no medido es previsión y se marca.

---

## 1. Qué es

- **El flujo** es el orden de los pasos de un mensaje.
- **El contrato** es la forma fija de lo que cada paso entrega al siguiente. Un nexo nuevo llena su parte del contrato y
  no toca la de los otros.
- **La regla que impide los conflictos:** el único que escribe texto libre es el modelo en la llamada 0. Todo lo demás
  elige entre candidatos que salen de la fuente, y el código lo verifica.

## 2. Los pasos, en orden

| Paso | Quién | Recibe | Entrega | Estado |
| --- | --- | --- | --- | --- |
| 0. Entrada | código | el mensaje, la tienda, el trace_id | lo mismo | hecho en el bot |
| 1. Llamada 0 | modelo | el mensaje | una línea por cosa: fragmento, búsqueda y lugar de envío | separar y traducir medido, 112 de 112; el lugar por medir |
| 2. Ruteo | código | las líneas | a qué nexos va cada línea | por medir |
| 3. Embeddings | un pedido por mensaje | las búsquedas y fragmentos del mensaje | sus vectores | medido en el banco |
| 4. Nexos | código, cuentas locales | cada línea con sus vectores | candidatos de la fuente | ver el punto 3 |
| 5. Jev o llamada corta | uno por mensaje, solo líneas dudosas | la línea y sus candidatos | uno, dos o ninguno | por decidir y medir |
| 6. Filtro | código | lo elegido | lo que está entre los candidatos y en la fuente | por hacer |
| 7. Redactar | código | el contrato completo | la respuesta | robótica en el banco |
| 8. Memoria | código | lo mostrado, con ids | para el turno que sigue | fuera por ahora |

**El ruteo, sin preguntarle nada más al modelo:** con búsqueda, es un producto; sin búsqueda, es una pregunta para la
FAQ; con lugar, va además al envío. Una línea puede ir a varios nexos: "2 sillas rojas a Rosario" va a producto,
condición y envío.

**Por qué un pedido de embeddings y uno de Jev por mensaje:** el índice de la tienda ya está calculado y cargado. Las
diez búsquedas de una multipregunta son cuentas locales sobre ese índice, no diez llamadas.

## 3. Los nexos y el índice de la tienda

El índice tiene toda la fuente partida por tipo, calculado al subir el catálogo y la FAQ, guardado por tienda. Cada nexo
busca solo en su tipo.

| Nexo | Busca en | Elige | Depende de | Estado |
| --- | --- | --- | --- | --- |
| Destino | el padrón de localidades, con el lugar que marcó el modelo | el código, con la tarifa | nada | 32 de 33 y 15 de 15, cero mal |
| Rubro y producto | rubros con alias, tres; productos con etiquetas, cinco | la función que elige; Jev en lo dudoso | nada | candidatos 100 %; elige 92 a 94 %; lo que no se vende 8 de 14 |
| Producto nombrado | marcas y modelos | la función de identidad: existe, ambiguo, no existe | rubro | por medir |
| Tema de la FAQ | los temas con sus alias | la función que elige; Jev en lo dudoso | nada | por medir |
| Condición de ficha | los campos del rubro elegido; los números los lee el código | el código; Jev en lo vago | producto | por medir |
| Cuenta | la calculadora | el código | todos los anteriores | existe en el bot |

**El orden cuando una línea toca varios:** producto, después condición dentro de ese producto, después envío. La cuenta
va al final, con todo ya certificado. Las preguntas de la FAQ no dependen de nada.

## 4. El contrato

Cada línea, al salir del filtro, tiene esta forma:

```
linea:      fragmento, búsqueda, lugar
nexos:      una entrada por nexo que la tocó:
  nexo        destino, producto, nombrado, tema, condición
  candidatos  ids de la fuente, en orden
  elegido     un id, o ninguno
  veredicto   coincide, no hay, o repreguntar
  datos       lo de la fuente tal cual: filas, tarifa o texto de la FAQ
```

**Un nexo que todavía no existe devuelve "repreguntar".** Así el flujo nunca se corta, y se puede probar entero desde
hoy con los nexos que faltan marcados.

## 5. Cómo se evitan los errores

1. **Cada paso con su prueba sobre los 140 mensajes**, `nuevas70` y `nuevas70b`, de punta a punta, con la vara escrita
   antes.
2. **Lo no medido se marca** en esta ficha y en el código, y se mide antes de darlo por hecho.
3. **La llamada 0 no crece.** Un campo nuevo entra solo si se mide que el texto suelto falla, y solo si es de copiar.
4. **Ningún paso escribe datos.** Los datos salen de la fuente por id y el código los pega.

## 6. Lo que decide Martín

1. Para lo dudoso: Jev, que elige de listas cerradas, o una llamada corta del modelo. Se mide uno contra el otro en el
   nexo de rubro, con lo que no se vende.
2. El corte de cada nexo, antes de medirlo.

# FICHA 104 — Luna separa y traduce con la ficha del vocabulario de la tienda

20 y 21-nov, sesión con Martín. Reemplaza a la FICHA 103 como plan de la llamada 0. Todo es banco: el bot sigue con el
v7 de la FICHA 102. Los números salen de nuevo con los comandos de la sección 5.

## 1. Lo decidido

1. **Separar es trabajo de Luna.** Ni el código ni los embeddings separan como ella: el corte del código por comas y
   conectores coincide con las filas del v13 en la cantidad en 111 de 200, parte de más en 75, junta de más en 14 y nunca
   copia lo compartido, como el destino, a cada fila. Los embeddings no separan, solo comparan.
2. **Luna, además de separar, traduce** en la misma llamada: las palabras del cliente entre llaves, sin cambiar ninguna, y
   al lado, entre corchetes, el nombre del vocabulario de la tienda. Lo que no sabe, solo entre llaves: eso va a los
   embeddings y a Jev, como en la FICHA 103.
3. **La ficha es la fija, f1:** los nombres de rubros, campos y temas, armados por código desde `alias.json`, unos 400
   tokens, iguales para todos los mensajes. Escala con la tienda porque crece con los rubros y no con los productos.
4. **El prompt es el v14f1b**, `llamada0_modelos.PROMPTS["v14f1b"]`: el v14f1 con una frase para lo mencionado de paso,
   entre corchetes solo lo que el cliente pide o pregunta.

## 2. Lo medido, sobre las 200 difíciles y los 100 negativos

| | v14f1b | v14f1 | f3, por embeddings con alias | v7, el bot |
| --- | --- | --- | --- | --- |
| todos los rubros, de 161 mensajes | 150 | 141 | 120 | 122 |
| temas, de 13 | 12 | 12 | 10 | no traduce |
| nombres fuera del vocabulario | 2 | 3 | 6 | 38 |
| nombrado de paso, en un rubro, negativos | 4 | 9 | 8 | sin grabar |
| lo no vendido metido en un rubro, de 62 | 1 | 1 | 2 | sin grabar |
| palabras perdidas, de 200 | 13 | 10 | 7 | v13: 8 |
| segundos, medio | 4,1 | 4,0 | 3,8 | 2,7 |

- **De los 11 que faltan en el v14f1b, ninguno es un rubro equivocado:** 8 son códigos sueltos, "la garantía del G305",
  que Luna marca como modelo y resuelve el nexo de nombrado; "memorias" una vez; y dos jergas que deja entre llaves, R07
  y B46. Sin los códigos, 158 de 161.
- **Las casillas de las 200 no son parejas:** el mismo código lleva mouse como esperado en unos mensajes y no en otros,
  y K20 y K21 no tienen el teclado que el cliente pide. Parte del "de más" es la casilla.
- **Los embeddings antes de Luna**, `embeddings_antes.py`: el mensaje en trozos, 3 por sección, trae a la ficha todos los
  rubros y temas pedidos, 239 de 239 y 14 de 14. Pero con esa ficha, f3, Luna traduce peor que con la fija y devuelve
  vacío en saludos. Queda medido, no se usa.
- **El control de palabras perdidas** del 19-nov no estaba en el banco; el de `luna_ficha.py` es reconstruido, palabra de
  tres letras o más no parecida a 0,7, y con él el v13 da 8 de 200, no 0.
- **Gasto de la sesión:** unos 18 centavos de Luna y una décima de centavo de embeddings con la paga, que Martín autorizó
  solo para eso cuando la gratis se trabó por cupo.

## 3. Lo que queda abierto, en orden

1. **Lo nombrado de paso que queda**, 4 en los negativos: "teclado de piano", "funda con teclado", "mi notebook en
   consignación" y "impresora 3d". Antes de tocar el prompt, mirar cada una con lo que recibió y devolvió Luna. Si es la
   misma clase, se busca la frase que la cubre entera; si no, se deja: Jev y el verificador están después.
2. **Las palabras perdidas**, 13: clasificar cada una, control roto o Luna, antes de creer el número. Varias son "los",
   "tres" o "una", que el control puede marcar de más.
3. **Las casillas de las 200**: emparejar los códigos sueltos y el teclado de K20 y K21, en su propio commit y con el ok
   de Martín, porque es cambiar la vara.
4. **Repetir el v14f1b una vez**, para ver la variación de Luna, antes de pasarlo a `app/`.
5. **El resto del camino con las filas del v14f1b:** lo entre corchetes va directo al rubro y al tema; lo entre llaves,
   a los embeddings y a Jev como en la FICHA 103. Medir con `jev_numero.py` contra 451 de 468.
6. **Pasar a `app/`** con el ok de Martín.

Más adelante, si la latencia pesa: un modelo grande en un proveedor rápido, con la misma vara y un piloto de 10. Los
modelos chicos ya erraron más en separar y elegir. Los precios de otros proveedores se confirman antes de decidir.

## 4. Cómo se trabaja

Igual que la FICHA 103: cada prueba con el ok de Martín, y las corridas largas con Sonnet, que se lanza con el modelo
explícito, tarea larga e informe de no más de 15 líneas. Un proceso de fondo corta a los 10 minutos: las corridas de 300
van con `--parte i/4`, que retoma lo grabado.

## 5. Cómo se corre

```bash
python3 banco_pruebas/flujo/llamada0_modelos.py --correr luna v14f1b --banco 200 [--parte 0/4]   # Luna, con gasto
python3 banco_pruebas/flujo/llamada0_modelos.py --correr luna v14f1b --banco neg100
python3 banco_pruebas/flujo/luna_ficha.py [--ver v14f1b]          # la vara, sin modelo; VER_N=40 muestra más casos
python3 banco_pruebas/flujo/embeddings_antes.py                    # los embeddings antes de Luna, caché fuera del repo
```

# FICHA 83 — Separar el mensaje: lo que movió la aguja

27-oct-2026, sesión con Martín. Sigue a la FICHA 82. **Es banco: nada de esto está en el bot.** Los instrumentos son
`banco_pruebas/momento0.py`, `razonar.py`, `sinteticas_separar.py` y `sinteticas_verifika.py`. Cada número tiene su
commit, que lo cuenta solo.

## La idea, de Martín

Primero separar bien, y solo separar. El modelo no tiene que inventar nada: tiene que leer lo que pidió el cliente y
dejar cada cosa en su lugar, con lo que mejor sabe hacer. Si esa base es firme, traducir y etiquetar vienen después.
Hasta que no llegue al 95%, no se pasa a lo siguiente.

## Lo que movió la aguja

**Cambiar lo que se le pide al modelo, para que haga algo que ya sabe hacer.** No le pedimos "partes con etiquetas",
que es un invento nuestro y necesita reglas. Le pedimos lo que pide el cliente, en primera persona y con sus palabras:

- una línea por cada producto y cada destino, con campos fijos: cosa, cantidad, destino y "si";
- la condición en su propia línea, y lo que depende de ella con su "si";
- lo que vale para todo el pedido, una vez, en "todo";
- dos ejemplos de la forma exacta: un reparto a destinos y una compra con condición.

Sobre los 91 primeros mensajes del banco, con la misma vara de una línea por cosa: **de 67 a 82**.

**Medir la información, no la forma.** La vara pedía una línea exacta por cosa. Revisadas a mano, las fallas tenían la
información completa en otra forma —"¿cuánto sale cada envío?" con los destinos en las otras líneas— que el código
puede llevar a su forma normal. Midiendo si falta algo del mensaje: **89 de 91**.

## Lo que no movió la aguja

| Lo probado | Resultado |
|---|---|
| Solo la consigna de separar, sin campos | 67 de 91: escribe preguntas al cliente, junta por destino, cruza todo con todo |
| Contar primero cuántas cosas pide | 79 contra 82: resta |
| Atar la salida al esquema, o pedirla libre, o en tabla | 89, 89 y 87: igual |
| Razonar, Gemini, sobre 30 difíciles | sin fijar 28, mínimo 28, bajo 27, medio 29; alto, dos minutos y 63.000 tokens por mensaje |
| DeepSeek sobre los mismos 30 | sin razonar 25; razonando 27, con 15 segundos de mediana |
| Mejoras de consigna sobre las de tiendas: la pregunta siempre en su línea, comprobación final, ejemplos abstractos | 47 contra 48: resta |
| Un filtro del código que elige qué bloques entran | detecta lugares 11 de 15 y "varias cosas" 52 de 86: lo que se escapa es lenguaje |
| Los ejemplos parecidos por embeddings | la acción correcta entre los 5 primeros en 76%: no alcanza |

Sin fijar, el modelo de producción no razona: igual que el nivel mínimo.

## Lo medido, con la consigna de las líneas

| Examen | Qué es | Bien |
|---|---|---|
| Primeros mensajes del banco | 91, de las 48, las 58 y las nuevas | 89 |
| El desmenuzado de la FICHA 67 | 138 primeros mensajes, escritos el 4-oct, nunca usados para la consigna | 125 |
| Muestra difícil | 30, los de más cosas y los más largos | 28 |
| Sintéticas de ocho tiendas | 48 complejas, con el rubro y los temas de cada tienda | 48 |
| Sintéticas de Verifika | 200 complejas, armadas por código con semilla | 190 |
| Con charla previa | 78 turnos, con la libreta | 68, contra 70 de la lectura de hoy |

Lo que falla en el primer mensaje casi no es de separar: es de traducir, el rubro que el cliente no nombra —"escribir
más cómodo", "algo para escuchar música en la casa" escrito como auricular—. Lo que falla con charla: cuando el cliente
pregunta por algo ya mostrado, el modelo pone un tema de la tienda en "cosa" en vez del número de la libreta.

Costo: la consigna pesa unos 700 tokens con la lista de temas, contra unos 3.700 de la lectura de hoy. Una llamada, unos
1,3 segundos de mediana.

## La consigna

Está en `banco_pruebas/momento0.py`, `LINEAS`, con sus dos ejemplos `EJ1` y `EJ2` y el esquema `_formato_lineas`. Para
otra tienda cambia solo el rubro de la primera línea y la lista de temas, que salen de sus datos.

## Lo que falta antes de confiar en el 95%

1. **Clientes reales.** Los exámenes los escribimos nosotros o el código. Falta pasar los primeros mensajes reales de
   producción, `produccion.py`, y los siete casos de producción.
2. **Lo que entra de más.** La vara mide que no falte nada, no que no sobre: en un caso inventó un pago, en otro repitió
   una compra. Falta contar las líneas de más.
3. **La misma pregunta dicha de otra forma.** Las 200 de Verifika salen de plantillas: comparten forma. Falta medir
   variantes de redacción de las mismas compras.
4. **Con la paga.** Las de tiendas, las 200 y la memoria corrieron con la clave gratis. Es el mismo modelo; conviene una
   corrida de control con la paga antes de llevarlo al bot.

## Lo que sigue

Dos caminos, por orden de Martín: que las líneas del primer mensaje lleguen al código en la forma que el código procesa,
y medirlo hasta la respuesta; después, la memoria, con "cosa" y "tema" en campos separados para que lo señalado se
escriba con su número.

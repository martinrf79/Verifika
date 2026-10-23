# FICHA 77 — Qué toca de la tienda y qué quiere hacer el cliente

23-oct-2026, sesión con Martín. **Es banco: nada de esto está en el bot.** Todo se midió con el modelo de producción y la
paga, con el ok de Martín en la sesión: unos 75 centavos en total. Cada número tiene su commit, que lo cuenta solo.

## El problema, dicho corto

El modelo **entiende** bien y **etiqueta** mal en los bordes. Sobre las 48 de razonamiento con memoria, de los 12 turnos
que la ficha nativa deja mal, 10 vienen de la ficha: mirar o comprar, "¿hay tres?" anotado como cantidad, "otro igual",
el condicional perdido. El código no puede ver una etiqueta mal puesta, porque no entiende razonamiento. Cada capa que se
sumó para corregirlo movió la falla de lugar.

La propuesta separa cada parte del mensaje en dos cosas:
- **qué toca de la tienda**: rubro, producto, campo o tema. Eso lo encuentra el código con una búsqueda;
- **qué quiere hacer el cliente con eso**: el acto. Eso lo pone el modelo, de una lista cerrada.

## Lo medido

| Prueba | Instrumento | Resultado |
| --- | --- | --- |
| Contar cuántas cosas pide, junto con separar | `banco_pruebas/cuenta_preguntas.py` | el número da igual a sus partes 34 de 34: no es un control. Pedir el número **primero** separa mejor: 13 de 17 contra 9 |
| Ida y vuelta: el código dice la ficha en castellano y el modelo la compara | `pedido_documento/ida_y_vuelta.py` | marca 10 de las 12 malas y 33 de las 36 buenas: **descartado** como control general |
| La búsqueda sobre las partes traducidas, rubros y temas, con las 16 de razonamiento | `banco_pruebas/buscador_partes.py` | rubro entre los seis 32 de 32, contra 29 sobre el mensaje crudo |
| Rubros y temas: 186 mensajes nuevos, los 22 rubros de tres formas y los 50 temas dos veces | `banco_pruebas/cobertura.py` | ver la tabla de abajo |
| Productos y campos: 88 productos y 101 condiciones, de Jev y nuevas | `banco_pruebas/cobertura_capas.py` | ver la tabla de abajo |
| El acto de cada parte, sobre las 48 | `banco_pruebas/actos.py` | de 26 a **34 de 48**: ver abajo |

**La búsqueda, con la consigna unida y por significado** (`gemini-embedding-001`, un vector por rubro, tema, campo y
modelo, armado una vez):

| Capa | Lo correcto entre los seis | Primero |
| --- | --- | --- |
| Rubro, 101 | 100 | 99 |
| Tema de la FAQ, 123 | 121 | 116 |
| Campo, 101 condiciones | 101 | 74 |
| Producto, 88 | 87 | 74 |

- Por palabras, como `agente.ubicar` hoy, con la consigna unida el tema primero cae a 87: **la búsqueda va por significado**.
- En productos, la búsqueda por significado acierta con tipeo 21 de 22 contra 5 del código de hoy; apodos 12 de 12;
  nombres de varios modelos 10 de 10.
- **Lo que se aprendió en el camino:** pedirle a la traducción que nombre con los nombres de la tienda borraba los modelos
  ("¿cuánto sale el G435?" quedaba "auriculares precio"). Se arregla con una línea: los modelos y marcas se copian tal cual.

**El acto**, sobre las 48, con la vara del oro de `pregunta_razonada/fichas.py` llevada a actos:

| Variante | Bien de 48 | Dependencias |
| --- | --- | --- |
| Sin ejemplos | 27 | 8 de 9 |
| Con 22 ejemplos en pares de borde | 29 | 9 de 9 |
| **Consigna unida**: actos, ejemplos, nombres de la tienda, modelos tal cual, destino como campo | 33 | 8 de 9 |
| La unida **más la regla del código**: comprar un rubro con un renglón sin producto elegido es elegir para ese renglón | **34** | 8 de 9 |

- **Regla de Martín para la vara**: lo que dice el modelo vale si se responde con la fuente, no alucina y no va contra
  vender. Con ella se aceptaron cuatro respuestas, en `actos.TAMBIEN`.
- **Regla probada y sacada**: una parte que solo nombra lugares es el destino de las otras. El padrón toma "Roberto
  Gómez" por la localidad de Gómez, y en un turno con memoria "mandá todo a Mendoza" es un cambio del pedido. Bajó a 32.

## Las 14 que quedan

1. **Detalles hechos parte**, unos 5: destinos y envío como partes sueltas. Va en el esquema y en ejemplos, no en el
   código: la regla del padrón no sirvió.
2. **"Nada" de más**, 2: "los auriculares están bien" junto a un cambio. Candidata a regla del código: con otras
   partes, la de "nada" no suma. Sin medir.
3. **Acto mal elegido**, unos 4, con pares nuevos: "¿qué me recomendás?" es mirar; "¿puedo pagar la mitad cuando llega?"
   es regla de la tienda; "para mi hija mejor uno más grande", con pedido, es cambiar; el pago dicho al pasar no se
   pierde.
4. **Para que decida Martín con su regla**, unos 4: "si no, decime cuál sí" como pregunta aparte que depende; "que sean
   tres" como cambio de cantidad; "¿el Deco sirve para dos pisos?" como compatibilidad; "sin el cable" como sacar.

## El flujo propuesto

1. **Primera llamada**: separar con el número primero, nombrar con la tienda copiando modelos y marcas, poner el acto,
   de qué parte depende, la cantidad en palabras y el destino como campo. Es la consigna unida de `actos.py`.
2. **El código busca** por significado los seis candidatos de cada parte, en las cuatro capas.
3. **Segunda llamada, solo si hace falta**: cuando el código no puede decidir entre los candidatos —un campo dudoso, un
   nombre de varios modelos—, el modelo elige entre ellos. **Sin armar ni medir.**
4. **El código hace las cuentas**: "otro igual", "para cada uno", "los otros". **Sin armar**; se prueba sin modelo.
5. **La respuesta** la sigue escribiendo el código, como hoy. Cambia lo que llega al ejecutor, no la redacción.

**Lo que no hay que olvidar:** la memoria entra por la libreta, y el flujo se mide con charlas de varios turnos, no solo
con mensajes sueltos; el índice de vectores se arma por tienda al subir catálogo y FAQ, como hoy los alias; son dos
llamadas y los vectores, menos de un centavo por mensaje y uno o dos segundos más; si una llamada cae, el cliente no
queda sin respuesta; antes del bot, las 48, los siete de producción y la charla de trece mensajes de Martín.

## El orden que sigue

1. Las cuatro decisiones de Martín de "Las 14 que quedan", punto 4.
2. Los pares nuevos del punto 3 y el esquema del punto 1 en la consigna unida; medir con `actos.py --unida --codigo`.
   Unos 3 centavos por corrida.
3. Medir con otras formas de decir lo mismo, `variantes.py`, para saber cuánto cae fuera de las 48; y la votación del
   acto si cae.
4. Las cuentas del código y la segunda llamada, cada una medida antes de seguir.
5. El turno armado, por el webhook, contra la vara entera. El arreglo del Cobra, commit 32424b6, sube en ese push.

# FICHA 78 — La primera traducción, la etiqueta y el motor de casos resueltos

23 y 24-oct-2026, sesión con Martín. **Es banco: nada de esto está en el bot.** Sigue a la FICHA 77. Todo se midió con
el modelo de producción y la paga, con el ok de Martín en la sesión; el día cerró en el tope de 1,60 dólares. Cada
número tiene su commit, que lo cuenta solo.

## El problema, dicho corto

El modelo **entiende** bien y **etiqueta** mal en los bordes: si es algo nuevo o algo que ya está en el pedido, y qué
respuesta de la tienda necesita. Esta ficha separó las dos cosas y midió cada una por su lado.

## Lo medido

### 1. La primera traducción está resuelta

Pasar lo que dice el cliente a los nombres de la tienda, sin etiquetar nada. `banco_pruebas/traduccion_sola.py`, una
llamada por frase.

| Prueba | Frases | Resultado |
| --- | --- | --- |
| Las 14 de la entrevista, rubros por razonamiento y temas de costado | 108 | 104 a 106 en todas las variantes |
| Las cien difíciles, sobre lo que falló, `traduccion_dificil.py` | 100 | ejemplos 88 · **calibrado 99** · libre 63 |
| El examen: cien escritas después de calibrar, `traduccion_tercera.py` | 100 | calibrado 81 · **duda 91** · por tipo 88 |

- **Contaminación encontrada:** `scripts/generar_alias.py` tiene en su prompt el ejemplo "el aparato con…", y
  `alias.json` trae "es el aparatito con teclas" para teclado. Las pruebas viejas con esa frase no prueban que el modelo
  razone. Todas las de esta ficha se escribieron sin mirar los alias y se controlaron contra ellos.
- **La atadura:** cuando la lista de la tienda va en el esquema que la API de Google hace cumplir, el modelo no puede
  contestar otra cosa y fuerza lo más parecido: "que no haga ruido" terminó en el tipo de switch, "el wifi no llega"
  en la característica wifi. **Libre** inventa nombres que la tienda no tiene: 2 de 15 en lo que no se vende.
- **Lo que gana: atado, con salida y con ejemplos calibrados.** La lista cerrada para lo que la tienda tiene; "otro"
  con la palabra del cliente para lo que no; "duda" para lo que no se entiende o puede ser dos cosas, que el código
  repregunta; una regla por clase de error y frases resueltas por clase, nunca de la prueba. Unos 1.000 tokens.
- **Las listas por tipo,** cada tipo con su lista cerrada por `anyOf`, que la puerta acepta, no suman: 88 contra 91.
- **Escribir el razonamiento primero** no sumó en la traducción.
- **Falla todavía:** los órdenes raros —"el más chiquito" salió el más barato, "qué tan fuerte suena" salió otro y no la
  potencia— y los requisitos sin característica bajan un poco con la duda.
- **Falta correr** el control de las 108 con duda y por tipo: lo cortó el tope del día.

### 2. Los candidatos que trae la búsqueda por significado

`banco_pruebas/candidatos.py`, sobre las 48 de razonamiento y las 58 con las K, contra lo escrito a mano.

| Capa | Entre los seis | Primero, con la pregunta completa pulida |
| --- | --- | --- |
| Rubro, 125 | 122 | 45 de 45 en las 48 · 69 de 80 en las 58 |
| Tema, 20 | 20 | 20 |
| Producto, 52 | 52 | 48 |
| Renglón del pedido, en las 48 | por parecido, 26 de 43 | por número con el pase de lo mostrado a su renglón, 28 |

- La tienda se encuentra bien. **Lo de la charla no va por parecido:** los renglones del mismo rubro se diferencian por
  destino, color o para quién, y el vector no los separa. Va por número, y **el pedido tiene que guardar para quién es
  cada cosa**: "el de mi hija" no tiene de dónde salir.
- **La pregunta completa**, cada parte entera y una cosa por parte, sube la búsqueda; pero al reescribir el modelo vuelve
  orden lo que era pregunta, o al revés, y la etiqueta se mueve.

### 3. La etiqueta, lo que sigue flojo

Sobre las 48, por la vara de `actos.py`, y las 58 con las K por su agenda. Desde el 23-oct vale la decisión de Martín:
**pedir algo que todavía no eligió —"necesito algo para…"— es opciones.**

| Forma | Llamadas | Las 48 | Las 58 |
| --- | --- | --- | --- |
| La consigna unida de hoy, con su acto | 1 | 34 | 66 de 105 |
| **La lista media de respuestas, con la tienda adentro**, `respuestas.py` | 1 | **35** | **74** |
| Guía mínima, la información A sola | 1 | 29 | 67 a 71 |
| Información A con pistas de la tienda por significado | 1 | 31 | 66 |
| Dos llamadas: separar y después elegir con pistas | 2 | 28 | 63 |
| El acto armado por el código desde modo, objeto y estado, `modos.py` | 1 | 30 | — |
| Segunda vuelta con candidatos de la tienda, `etiqueta.py` | 2 | 31 | — |

- **Una llamada le gana a dos:** la segunda lee lo que escribió la primera y no lo que dijo el cliente.
- **El código no puede poner el acto:** llevar o cambiar es lenguaje.
- **Cada palabra de la consigna mueve la etiqueta unos cuatro turnos** para un lado y otro: con 48 casos no se separa una
  mejora de la suerte.
- **La lista de respuestas**: trece, sacadas de lo que el ejecutor ya sabe contestar. Corta, unos 240 tokens; media, con
  lo que necesita cada respuesta y los rubros, temas y campos adentro, unos 930; larga, el índice, fuera del repo.
- **Un modelo más grande no es el camino**, lo dicen las fichas anteriores.

### 4. Las entrevistas

`banco_pruebas/entrevista_traduccion.py`, con la regla de la FICHA 67: se le habla con palabras del cliente.
- A ciegas tradujo las 14 frases nuevas; con la lista de la tienda, la lista lo forzó en dos.
- Dice que confunde un problema que cuenta el cliente con una característica del producto, que prefiere "otro" con la
  palabra del cliente antes que forzar, y que lo que más le sirve son frases resueltas. De ahí salió la calibración.
- Por la puerta compatible, el proveedor no informa si razona por dentro; no fijamos `reasoning_effort`.

## La recomendación para seguir

**Un segundo motor de casos resueltos, como plantilla que se llena una vez por tienda.** Es lo que más subió siempre:
los ejemplos resueltos, 88 a 99 en la traducción, y 12 de 12 por parecido en la FICHA 67.

- **La plantilla es igual para cualquier tienda:** clase de respuesta, formas de decirla y estado de la charla —sin
  pedido, con pedido, con una pregunta del bot abierta—, con huecos: "¿el {producto} viene en {color}?" es un dato del
  producto, campo color.
- **Se llena sola con la fuente de cada tienda**: catálogo, FAQ, políticas y compatibilidades. El código valida cada caso
  contra la fuente. Verifika es la primera.
- **Crece con el uso:** cada turno real queda guardado; lo que el cliente corrige con un "no, te dije…" es un error;
  lo que pasa el control del código y la muestra de Martín entra; cada tanda se mide contra un examen que nunca entra.
- **Firestore** sirve para guardarlo, con búsqueda de vectores filtrada por tienda y estado, hasta 2.048 números por
  vector: los embeddings se piden en 768.

**El flujo:**
1. Primera llamada: la traducción calibrada, atada con salida y duda.
2. El código busca por significado en la tienda —rubros, temas, campos, productos— y en el motor de casos, los cinco
   más parecidos.
3. La etiqueta con esos casos a la vista. **Se mide en una llamada y en dos**: las pruebas favorecieron una, pero lo que
   se traía eran pistas de la tienda, no casos resueltos.
4. El código controla después con la tienda: si el modelo dice saber general y hay un rubro muy cerca, repregunta.

## El orden que sigue

1. Correr el control de las 108 con duda y por tipo; dos o tres ejemplos de la clase de los órdenes raros.
2. El motor de casos, la primera tanda: la plantilla y Verifika llenada con 300 a 500 casos, sacados de las 58, las 48,
   cobertura y lo generado. El examen queda siempre afuera.
3. La prueba que decide: la etiqueta con los casos traídos por parecido contra la lista media, 35 de 48 y 74 de 105, en
   una llamada y en dos, con tres repeticiones.
4. El para quién en el borrador. Toca el bot.
5. Regenerar los alias sin el ejemplo del aparato: toca la fuente y necesita el permiso de Martín.
6. Recién con eso, el turno armado por el webhook contra la vara entera, antes de cualquier deploy.

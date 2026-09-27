# FICHA 45 — El loop. El criterio es el índice.

Las correcciones se hacen adentro del turno. No las opina una sesión.
Una pasada. Un actuador por punto. El texto del modelo no se reescribe.

## De dónde sale el criterio

De `indice_turno.cobertura`. Cada punto termina en un estado terminal:

| estado | qué significa | actuador |
|---|---|---|
| RESUELTO | llegó al cliente | nada |
| AMBIGUO | el turno ya preguntó | nada |
| NO_SE_SABE | no hay dato; no se dice "no" | nada |
| OFRECIDO / NO_CORRESPONDE | la oferta | nada |
| CONFLICTO | el pedido no cierra y no se preguntó | preguntar |
| casilla vacía con evidencia | omisión probada | reponer sellado |
| casilla vacía sin evidencia | no se buscó | anotar, mandar igual |

Eso es `actuar(puntos)`. Puro. No mira la prosa para decidir.

No es un juez. Un juez reescribe. Esto elige un actuador declarado y para.
La segunda redacción de `DECISIONES.md` #5 sigue sin pagarse.

## Qué se hace en esta ficha

Se enchufa el actuador que faltaba: CONFLICTO escribe UNA pregunta
sellada, con el hecho que el decisor ya declaró. No lo resuelve. No
explica un fallo. La higiene no la tira: el sello `Cómo lo querés:`
gana a las otras preguntas porque bloquea el cobro.

`reponer` ya existía. `anotar` ya existía. No se suma una pieza al
grafo: corre adentro de `punto_omitido`.

## Qué no se hace

No se deposita grasa. No se toca `certificar_temas`. No se elige un
extremo suelto. Si el piso baja, revert.

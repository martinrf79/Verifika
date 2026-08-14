# RESERVA — capacidades enteras que se guardan sin cablear

## Qué es esta carpeta y por qué existe

Acá vive código que **funciona, no está enchufado, y no se quiere borrar**.

Nació el 14-ago-2026 con una decisión de Martín. `posventa.py` era una capacidad
completa —plazo de devolución, garantía vigente, validación de CUIT— que nadie
importaba. Estando en `app/`, todos los instrumentos la contaban como código
muerto: el mapa la marcaba SIN ALCANCE, `test_nada_suelto` pedía que se declare
con motivo, y cada sesión nueva volvía a preguntar si se borraba. Estorbaba sin
hacer nada. Borrarla y rehacerla después era perder un trabajo que ya estaba
hecho y probado.

Entonces se mueve. Acá no molesta a ningún instrumento y sigue en el repo.

## Las tres reglas de esta carpeta

**1. `app/` NUNCA importa desde `reserva/`.** Es lo único que la vuelve
inofensiva: la reserva no puede afectar una respuesta al cliente porque el
camino vivo no la puede alcanzar. Lo defiende `tests/test_reserva.py`, que se
pone rojo si aparece un import.

**2. Lo de acá NO importa `app/`.** Al revés tampoco: un módulo guardado que
depende de `app/` se pudre solo el día que `app/` se mueve, y nos enteramos
recién al querer enchufarlo. Lo de la reserva es código puro. Mismo test.

**3. Esto no es un depósito, es una lista corta.** Cada archivo entra con su
motivo escrito en la tabla de abajo, y `tests/test_reserva.py` falla si un
archivo no está en la tabla o si la tabla nombra un archivo que ya no existe.
Si la lista empieza a crecer, algo se está barriendo abajo de la alfombra: la
reserva es para una capacidad terminada que espera su turno, no para dudas.

**Lo que la reserva NO es.** No es un flag apagado. Un flag en `false` es un
camino que corre al lado del vivo esperando que alguien lo prenda, y es la
regla 2-bis de `CLAUDE.md`, la que costó los 70 flags. Esto es lo contrario:
código FUERA del camino, que el sistema no puede ejecutar ni por accidente.

## Qué hay guardado

| archivo | qué hace | qué falta para enchufarlo |
|---|---|---|
| `posventa.py` | Plazo de devolución, garantía vigente y validación de CUIT, todo determinista: el bot no improvisa una fecha ni dice "sí, tiene garantía" sin base. | Falta el dato de tienda —días de devolución y meses de garantía por producto— y una herramienta que lo exponga al modelo. Ver abajo. |

## Cómo se vuelve a enchufar (posventa, paso a paso)

No hace falta reconstruir nada: el motor está entero y su matemática no depende
de nadie. Lo que falta es el cableado, y son cuatro pasos.

1. **El dato de tienda.** Hoy `plazo_devolucion` usa el default de plataforma,
   10 días corridos de la Ley de Defensa del Consumidor, y `garantia_vigente`
   recibe los meses por argumento. Para que sea real, esos dos números tienen
   que salir de la fuente, no del código: los días de devolución van a
   `base_conocimiento.json` y los meses de garantía a la columna que ya existe
   en el catálogo. Sin esto, el bot contesta la política genérica.
2. **La fecha de compra.** Es el dato que el sistema no tiene. Hoy no hay
   herramienta de pedidos, y eso es a propósito: `las_40` tiene un caso —el
   pedido #4589— que verifica justamente que el bot NO confirme un número de
   pedido inventado. Enchufar posventa sin resolver de dónde sale la fecha
   invita exactamente a esa alucinación. O la pregunta al cliente y la trata
   como dicha por él, o hay una fuente real de pedidos.
3. **Mover el archivo y exponerlo.** `git mv reserva/posventa.py
   app/core/posventa.py`, sacarlo de la tabla de arriba, y agregar la
   herramienta en `app/core/herramientas.py` con su molde Pydantic, igual que
   las otras. Recién ahí el modelo puede llamarla.
4. **Las pruebas.** El motor es código puro y determinista, así que se prueba
   entero offline y gratis: fechas de borde —el 31 de enero más un mes, el año
   bisiesto—, el CUIT con dígito verificador 10 y con 11, y el límite justo en
   el día que vence. Y un caso en las charlas grabadas, que es lo único que
   mide el turno completo.

## Cómo se saca algo de la reserva sin dejar restos

Se borra el archivo, se borra su fila de la tabla de arriba, y listo:
`tests/test_reserva.py` avisa si quedó una de las dos mitades. Si la carpeta
queda vacía, se borra la carpeta y su test.

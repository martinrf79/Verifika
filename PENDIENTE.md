# PENDIENTE — lo que quedó abierto

Este archivo es **CORTO a propósito** y el hook de arranque lo imprime entero, así
que toda sesión nueva lo lee sin buscarlo. **Máximo veinte líneas de contenido, un
ítem por línea.** El 21-ago tenía veinte PÁRRAFOS, uno de mil novecientos
caracteres: un archivo que se imprime en cada arranque no puede ser un diario.

**Lo que se HIZO no va acá:** lo cuenta `git log`, que el hook también imprime y
que nadie puede desactualizar.

**El PLAN tampoco va acá**, y ese es el cambio del 21-ago. El recorte vive como
tests que se cuentan solos; escribirlo además en prosa eran dos fuentes sobre lo
mismo, que es exactamente lo que venimos sacando de todos lados.

Estados: **ABIERTO** · **ESPERA A MARTIN** (falta una decisión o un dato suyo).

Candado: `tests/test_pendiente_al_dia.py` falla si hay commits que tocan `app/`
más nuevos que este archivo.

---

## Dónde está el proyecto — dos números, y salen de correr `pytest`

```
A MEDIAS   algo que se EMPEZÓ y no se terminó.  Tiene que llegar a CERO.
PLAN       el recorte. Baja a medida que se hace.
```

El detalle de cada paso, con su número de hoy y su objetivo, está en
`tests/test_plan_del_recorte.py`. La unidad de trabajo abierta, en `arquitectura/`.

---

## Abierto

- **ABIERTO** · **VEINTICUATRO ENGRANAJES CORREN SIN NODO DECLARADO, y el censo del grafo recien ahora los cuenta.** El grafo declara 15 nodos y en los 54 turnos dejan marca 39: los otros 24 son las piezas de adentro de las puertas de `salida` y `reposicion` —`atadura` interviene en 46 de 54 turnos, `saludo` en 24, `cuenta_repuesta` en 19— que despues de las FICHAS 10 y 11 siguen registrando con su id propio y NO tienen nodo en `NODOS`. Corren SIN CONTRATO declarado, y el barrido de `test_grafo_cableado.py` saca su lista de `NODOS`, asi que **no las barre ninguna**. Hay que decidir de a una si se declaran con su contrato o si se aceptan como internas de su puerta; el numero esta clavado en `tests/test_censo_del_grafo.py` para que no crezca solo.
- **ABIERTO** · **NUEVE ENGRANAJES CORREN EN LOS 54 TURNOS Y NO INTERVIENEN EN NINGUNO:** `aduana`, `honestidad_bot`, `sin_cobro_inventado`, `sin_json`, `sin_negar_lo_traido`, `hallazgo_repuesto`, `busqueda_repuesta`, `condicion_repuesta` y `cierre`. No prueba que sobren: prueba que el corpus no los ejercita. El paso esta contado como `PLAN:` y lo bloquea grabar los guiones 26 a 38, que necesita la clave paga.
- **ABIERTO** · El rubro que cambia de producto quedó cerrado en sus dos mitades; falta mirar si el mismo defecto entra por otra puerta que no sea la reposición.
- **ABIERTO** · Veintiocho funciones se alcanzan pero no las llama nadie: están DECLARADAS con su motivo en `tests/test_nada_suelto.py`, que se pone rojo si aparece una nueva. Hay que decidir de a una si se enchufan o se borran.
- **ABIERTO** · **EL TOPE DE LARGO BAJÓ DOS ESCALONES: 1.882 → 1.872 → 1.614, y el segundo no lo cortó nadie a mano.** El mecanismo del `_doc` del piso —después de cada corte el tope se fija en el máximo REAL que quedó, sin aire, y no vuelve a subir— hizo su trabajo: la puerta única bajó 258 caracteres del turno más pesado sin que la concisión fuera la tarea. Queda abierto seguir bajándolo, y sigue valiendo el aviso: la grasa que queda es prosa del modelo, no del código, y este módulo ya revirtió dos veces un corte por largo. **Y la regrabacion de la FICHA 17 lo paso: hoy hay un turno de 1.652 y otro de 1.639.** El tope NO se subio; el exceso quedo como `A MEDIAS:` en `test_el_mensaje_no_se_alarga`. Los dos son el mismo caso -pedido de varios rubros con reparto y pago dividido- donde el bot explica en prosa y despues repite el presupuesto entero.
- **ABIERTO** · `garantia_detalle` factorizado sale sin la marca: si un día dos productos de la misma categoría tienen plazos distintos, el campo no se factoriza y la repetición vuelve. No hay ningún caso así en el catálogo hoy.
- **ABIERTO** · Los dos `G Pro X` de Logitech no resuelven por modelo pelado: sus tres palabras son una letra, `pro` —que está en las genéricas— y otra letra. Sacar `pro` de las genéricas toca el match de los 880 y hay que medirlo con el barrido antes. El guion 30 lo ejercita.
- **ABIERTO** · La vara de CONTENIDO dio entiende 94 / contesta 94 con UNA repetición. Falta medirla con más repeticiones y sumar casos de turno largo; la única falla que se repite es `criterio_de_origen`.
- **ABIERTO** · El banco de turno largo corre offline sobre el estado, que es determinista. Lo que NO cubre es la redacción del modelo en un turno 10: eso sigue siendo prueba en real o casete grabado.
- **ABIERTO** · **EL TOTAL PERDIDO ESTÁ CERRADO y el piso ya se refijó: 495 puntos, largo 1.872, 2 llamadas.** El defecto era doble y los dos estaban tapados por el corpus viejo. **(1)** `_certifico_algo` apagaba la memoria ENTERA cuando el turno certificaba cualquier cosa: el cliente decía "agregá un teclado" y, por certificar teclados, se le negaba el carrito donde vivían los otros seis artículos. Ahora la gobierna el reclamo TIPADO del reconciliador, `falta_la_cuenta`. **(2)** Las búsquedas que hace EL CÓDIGO en las reposiciones no pasaban por `certificar_ids_de_resultado`, así que la calculadora rechazaba sus propios ids —`id_no_certificado sueltos=['AUR0019','MOU0023','RAM0001']`— y el turno cerraba sin un peso. Lo que queda ABIERTO es de otro orden y sale del mismo hallazgo: **cuántas piezas más del código buscan o calculan por su cuenta sin pasar por el registro de certificados**. Se arreglaron las dos búsquedas; las tres llamadas a `armar_presupuesto` que hace el código quedaron sin tocar a propósito, para no ampliar lo que la regla cero acepta en el mismo movimiento. **Y la FICHA 11 dejo la cuenta adentro de la puerta de reposicion, sin subirla a la etapa de resolucion como pide `DECISIONES.md` #8:** la condicion que la gobierna la emite el reconciliador, asi que subirla la pondria antes de saber si el cliente pidio precio, que es justo lo que este arreglo curo.
- **ABIERTO** · **La segunda redaccion que pide `DECISIONES.md` #5 —rechazar el texto y volver a redactar UNA vez con la violacion como aviso— no se puede pagar hoy**: son dos llamadas al modelo por turno y el piso las tiene clavadas en 2, y los casetes no tienen grabada esa vuelta, asi que el turno saldria con el enlatado de sobrecarga. Regrabar necesita la clave paga. Mientras tanto la puerta repone con material sellado y marca lo que no puede reponer.
- **ABIERTO** · La gemela PROCEDENCIA de la cobertura vive hoy con otro nombre y en otro modulo, `atadura_prosa`: ata cada afirmacion a su producto. Falta que la fuente sea el PUNTO resuelto y no el producto, que es lo que las volveria una sola vara en vez de dos.
- **ABIERTO** · **EL CORPUS SE REGRABO (FICHA 17) Y EL AVANCE SE MOVIO: 29/55 -> 33/55, `no_se_frena` 28/29 -> 33/33, `OFRECIDO` 14 -> 23 y `SIN_ESTADO` 13 -> 4.** De los 13 turnos que no ofrecian, **10 ahora ofrecen**. Los apuntes de ANTES y DESPUES estan en `APUNTE_ANTES_FICHA17.md` y `APUNTE_DESPUES_FICHA17.md`, con el cruce turno por turno que separa lo que movio el BOT de lo que movio el CORPUS. **Lo que quedo abierto es de tres clases.** (1) **CINCO VARAS ROJAS, contadas y no escondidas**, con el techo de A MEDIAS subido de 0 a 5 en su propio commit y ningun piso bajado: el largo maximo subio a 1.652 -76 t2- contra un tope de 1.614; los puntos de casetes bajaron de 496 a 495 por `62` T2, que afirma un universal sobre el catalogo sin herramienta, y `71` T4; `una_sola_repregunta` bajo a 53/55 por `46` t4 y `76` t2, que hacen dos preguntas en el mismo mensaje; y la puerta sin modelo bajo sola, porque su VERDAD DE REFERENCIA es el `registrar_pedido` que declaro el modelo y al regrabar declaro otros -un piso medido contra un blanco que se mueve con cada regrabacion no se puede leer, y esa es la parte que falta-. (2) **EL DETECTOR NO CUENTA LA OFERTA CUANDO EL PRONOMBRE VA PEGADO AL INFINITIVO** —`cotizarte`, `cargarlos`—: rompe el VERBO antes de llegar al producto, y las mismas frases con el pronombre suelto ya cuentan. Son tres turnos textuales -70 t2, 70 t3, 81 t3-, asi que el numero real es **OFRECIDO 26 y SIN_ESTADO 1**. No se arreglo en la sesion que lo encontro para que el numero se pueda leer. (3) **El unico turno que empeoro de verdad es `71` t3**: tenia el Teclado Logitech K120 para proponer y cerro sin nombrarlo. `camino_al_cobro` sigue clavado en 9/15, que es la FICHA 19.

## Espera a Martín

- **ABIERTO** · **LA PUERTA YA FRENA, Y EL NUMERO REAL DE OMISION ES 28 DE 238 PUNTOS EN LAS 15 CHARLAS GRABADAS, contra 38 antes de la FICHA 09.** De esas 28, **20 son de politica y son FALSAS**: el nombre del tema es vocabulario de nuestro archivero —`desconfianza_online`— y no aparece en un mensaje escrito para un cliente, y cuando el tema tiene numeros el turno contesta con el REAL de la cotizacion en vez del generico de la FAQ. Medir de verdad la omision de politica necesita otra vara —una que mire el CONTENIDO y no el nombre—, y hasta que exista el 12% es un techo con ruido adentro. Las de destino, que eran la masa real, bajaron de 10 a 2.
- **ABIERTO** · **Ante un tema `ambiguous` el codigo SIRVE TODOS LOS CANDIDATOS en vez de repreguntar, y eso se aparta de lo que pedia la FICHA 06.** Repreguntar ahi seria pedirle al cliente que elija entre dos nombres de nuestro archivero —"¿garantia o garantia_como_usar?"—, que es la falla que el repo ya diagnostico el 4-ago al unir los dos enums. No se elige, que es la parte que importa de la regla cero: se sirven las dos politicas enteras y el modelo contesta la que preguntaron. Medido sobre las 785 señas: 1,37 temas servidos por seña, cero choques ciegos. **Si Martin quiere la repregunta, es una linea en `certificar_temas`.**
- **ABIERTO** · `banco_pruebas/banco_llamada_uno.py` mide que herramienta ELIGE el modelo, y desde la puerta unica el modelo no elige ninguna. Sus 14 casos siguen siendo buenas preguntas —"¿entendio que era una condicion de origen?"— pero hay que reapuntarlos a lo DECLARADO. Hasta que eso pase, sus numeros no quieren decir nada.
- **ESPERA A MARTIN** · Los pares de temas que comparten una palabra —`factura`/`precios_iva` con "iva", `cuotas`/`cuotas_financiacion`, `regalo`/`envoltorio_regalo`— **dejaron de hacer daño: la certificacion los sirve a los DOS y el modelo contesta con las dos politicas delante.** Cero choques ciegos sobre las 785 señas, medido en `tests/test_barrido_faq.py`. Darle a cada uno su seña propia sigue siendo una mejora de la FUENTE, pero ya no es un agujero.
- **ESPERA A MARTIN** · El sistema SIN LLM está medido en `banco_pruebas/puerta_determinista.py` y el número es alto. Lo que ninguna pieza ve es la NEGACIÓN —"el teclado sacalo"— y lo que no tiene pieza es `pide_precio` y `contradicciones`. Sirve como modo degradado para cuando el modelo se cae; NO se deploya en paralelo al vivo.
- **ESPERA A MARTIN** · `villa, Buenos Aires` resuelve a un CP que el cliente no nombró. Daño chico —misma tarifa de interior— pero es el sistema eligiendo por el cliente. Se arregla en `geo_cp.resolver`.
- **ESPERA A MARTIN** · Cuánto tiempo se guardan las conversaciones y con qué criterio se borran. Desde el 19-ago el bot pide solo el nombre, así que la superficie es chica, pero la decisión de retención es suya y conviene tomarla antes de vender a una empresa.

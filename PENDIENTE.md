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

- **ABIERTO** · El rubro que cambia de producto quedó cerrado en sus dos mitades; falta mirar si el mismo defecto entra por otra puerta que no sea la reposición.
- **ABIERTO** · Veintiocho funciones se alcanzan pero no las llama nadie: están DECLARADAS con su motivo en `tests/test_nada_suelto.py`, que se pone rojo si aparece una nueva. Hay que decidir de a una si se enchufan o se borran.
- **ABIERTO** · `cierre` sale MUERTO en el censo: corre en los 54 turnos y no mueve el texto en ninguno. Antes de borrarlo hay que escribir el caso que lo despierta —vale para los nueve muertos, y los guiones 26 a 38 se escribieron para eso.
- **ABIERTO** · **EL TOPE DE LARGO BAJÓ POR PRIMERA VEZ: de 1.882 a 1.872, y ahora hay un mecanismo que lo obliga a bajar en vez de una intención.** Hasta el 22-ago el piso solo impedía que el largo CRECIERA, y un tope que solo prohíbe empeorar deja el número donde está para siempre: 1.882 había subido dos veces y no había bajado nunca. La regla nueva vive en el `_doc` del propio piso, que es donde vive el número: **después de cada corte el tope se fija en el máximo REAL que quedó, sin aire, y no vuelve a subir**. Así la concisión pasa a ser un efecto medido del recorte y no una tarea aparte que nunca llega. Lo que queda abierto es que 1.872 sigue siendo mucho: el turno 2 de `76` es el que lo marca y su grasa restante es prosa del modelo, no del código, así que no se puede cortar sin respaldo —los invariantes no la marcan como repetida y este módulo ya revirtió dos veces un corte por largo—.
- **ABIERTO** · `garantia_detalle` factorizado sale sin la marca: si un día dos productos de la misma categoría tienen plazos distintos, el campo no se factoriza y la repetición vuelve. No hay ningún caso así en el catálogo hoy.
- **ABIERTO** · Los dos `G Pro X` de Logitech no resuelven por modelo pelado: sus tres palabras son una letra, `pro` —que está en las genéricas— y otra letra. Sacar `pro` de las genéricas toca el match de los 880 y hay que medirlo con el barrido antes. El guion 30 lo ejercita.
- **ABIERTO** · La vara de CONTENIDO dio entiende 94 / contesta 94 con UNA repetición. Falta medirla con más repeticiones y sumar casos de turno largo; la única falla que se repite es `criterio_de_origen`.
- **ABIERTO** · El banco de turno largo corre offline sobre el estado, que es determinista. Lo que NO cubre es la redacción del modelo en un turno 10: eso sigue siendo prueba en real o casete grabado.
- **ABIERTO** · **EL TOTAL PERDIDO ESTÁ CERRADO y el piso ya se refijó: 495 puntos, largo 1.872, 2 llamadas.** El defecto era doble y los dos estaban tapados por el corpus viejo. **(1)** `_certifico_algo` apagaba la memoria ENTERA cuando el turno certificaba cualquier cosa: el cliente decía "agregá un teclado" y, por certificar teclados, se le negaba el carrito donde vivían los otros seis artículos. Ahora la gobierna el reclamo TIPADO del reconciliador, `falta_la_cuenta`. **(2)** Las búsquedas que hace EL CÓDIGO en las reposiciones no pasaban por `certificar_ids_de_resultado`, así que la calculadora rechazaba sus propios ids —`id_no_certificado sueltos=['AUR0019','MOU0023','RAM0001']`— y el turno cerraba sin un peso. Lo que queda ABIERTO es de otro orden y sale del mismo hallazgo: **cuántas piezas más del código buscan o calculan por su cuenta sin pasar por el registro de certificados**. Se arreglaron las dos búsquedas; las tres llamadas a `armar_presupuesto` que hace el código quedaron sin tocar a propósito, para no ampliar lo que la regla cero acepta en el mismo movimiento.
- **ABIERTO** · **No hay ningún número de VENTA.** Todo lo que se mide es defensivo —no cae, no inventa, no omite—. No hay tasa de cierre ni dónde se cae el cliente. Un sistema que solo mide lo que no debe hacer termina siendo un bot que no hace nada mal y no vende.

## Espera a Martín

- **ABIERTO** · **`indice_turno.puntos` ya abre las DIEZ familias, pero cuatro no se pueden abrir todavia en una charla real, y el numero engaña.** Se sumaron `atributo`, `stock`, `compatibilidad` y `politica`, cada una con su criterio de cobertura y con anclaje donde el codigo tiene el dato. **El problema es el MOLDE: `registrar_pedido` no tiene esos cuatro campos**, asi que el modelo no puede declararlos y en el corpus grabado no se abre ni uno. Medido despues del cambio: 190 puntos, 24 sin contestar, 13% — EXACTAMENTE los mismos de antes. **Ojo con leer ese 13% como una buena noticia: sigue siendo un PISO, no el numero real.** Lo que falta es agregarle los cuatro campos a `registrar_pedido`, y eso cambia el esquema que ve el modelo, o sea que es otra unidad con otro riesgo y hay que medir el peso del esquema al hacerlo.
- **ABIERTO** · **`puerta_piso.json` guarda PORCENTAJES atados a un corpus que cambia, y eso da falsos rojos. Se refijó el 22-ago, pero el defecto de diseño sigue.** Al regrabar los casetes se puso rojo diciendo `reparto_pago: 11.1% -> 9.1%`, como si el código entendiera menos. **No entendía menos: sacaba el mismo 1 turno.** Cambió el denominador, porque el modelo declaró reparto de pago en 11 turnos en vez de 9. Los otros cinco números subieron o quedaron igual —items 78,4→83,3, destinos 41,2→47,1, restricciones 60,0→66,7, turnos medidos 51→53— así que el refijado no baja ninguna vara. **Un piso que guarda una RAZÓN contra un corpus mutable mide dos cosas a la vez y no puede decir cuál se movió**, que es la misma enfermedad que la FICHA 03 curó en el otro piso. Guardar el numerador y el denominador por separado lo arregla, y hasta que eso pase sus rojos hay que leerlos con pinzas.
- **ESPERA A MARTIN** · Tres pares de temas comparten una palabra y ninguno tiene una seña propia: `factura`/`precios_iva` con "iva", `pedido_de_fotos`/`placa_video` con "video", `cambio_direccion`/`ubicacion` con "direccion". Es una edición de la FUENTE, no de código.
- **ESPERA A MARTIN** · El sistema SIN LLM está medido en `banco_pruebas/puerta_determinista.py` y el número es alto. Lo que ninguna pieza ve es la NEGACIÓN —"el teclado sacalo"— y lo que no tiene pieza es `pide_precio` y `contradicciones`. Sirve como modo degradado para cuando el modelo se cae; NO se deploya en paralelo al vivo.
- **ESPERA A MARTIN** · `villa, Buenos Aires` resuelve a un CP que el cliente no nombró. Daño chico —misma tarifa de interior— pero es el sistema eligiendo por el cliente. Se arregla en `geo_cp.resolver`.
- **ESPERA A MARTIN** · Cuánto tiempo se guardan las conversaciones y con qué criterio se borran. Desde el 19-ago el bot pide solo el nombre, así que la superficie es chica, pero la decisión de retención es suya y conviene tomarla antes de vender a una empresa.

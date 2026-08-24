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
- **ABIERTO** · **EL TOPE DE LARGO BAJÓ DOS ESCALONES: 1.882 → 1.872 → 1.614, y el segundo no lo cortó nadie a mano.** El mecanismo del `_doc` del piso —después de cada corte el tope se fija en el máximo REAL que quedó, sin aire, y no vuelve a subir— hizo su trabajo: la puerta única bajó 258 caracteres del turno más pesado sin que la concisión fuera la tarea. Queda abierto seguir bajándolo, y sigue valiendo el aviso: la grasa que queda es prosa del modelo, no del código, y este módulo ya revirtió dos veces un corte por largo.
- **ABIERTO** · `garantia_detalle` factorizado sale sin la marca: si un día dos productos de la misma categoría tienen plazos distintos, el campo no se factoriza y la repetición vuelve. No hay ningún caso así en el catálogo hoy.
- **ABIERTO** · Los dos `G Pro X` de Logitech no resuelven por modelo pelado: sus tres palabras son una letra, `pro` —que está en las genéricas— y otra letra. Sacar `pro` de las genéricas toca el match de los 880 y hay que medirlo con el barrido antes. El guion 30 lo ejercita.
- **ABIERTO** · La vara de CONTENIDO dio entiende 94 / contesta 94 con UNA repetición. Falta medirla con más repeticiones y sumar casos de turno largo; la única falla que se repite es `criterio_de_origen`.
- **ABIERTO** · El banco de turno largo corre offline sobre el estado, que es determinista. Lo que NO cubre es la redacción del modelo en un turno 10: eso sigue siendo prueba en real o casete grabado.
- **ABIERTO** · **EL TOTAL PERDIDO ESTÁ CERRADO y el piso ya se refijó: 495 puntos, largo 1.872, 2 llamadas.** El defecto era doble y los dos estaban tapados por el corpus viejo. **(1)** `_certifico_algo` apagaba la memoria ENTERA cuando el turno certificaba cualquier cosa: el cliente decía "agregá un teclado" y, por certificar teclados, se le negaba el carrito donde vivían los otros seis artículos. Ahora la gobierna el reclamo TIPADO del reconciliador, `falta_la_cuenta`. **(2)** Las búsquedas que hace EL CÓDIGO en las reposiciones no pasaban por `certificar_ids_de_resultado`, así que la calculadora rechazaba sus propios ids —`id_no_certificado sueltos=['AUR0019','MOU0023','RAM0001']`— y el turno cerraba sin un peso. Lo que queda ABIERTO es de otro orden y sale del mismo hallazgo: **cuántas piezas más del código buscan o calculan por su cuenta sin pasar por el registro de certificados**. Se arreglaron las dos búsquedas; las tres llamadas a `armar_presupuesto` que hace el código quedaron sin tocar a propósito, para no ampliar lo que la regla cero acepta en el mismo movimiento.
- **ABIERTO** · **No hay ningún número de VENTA.** Todo lo que se mide es defensivo —no cae, no inventa, no omite—. No hay tasa de cierre ni dónde se cae el cliente. Un sistema que solo mide lo que no debe hacer termina siendo un bot que no hace nada mal y no vende.

## Espera a Martín

- **ABIERTO** · **YA HAY NUMERO REAL DE OMISION Y ES PEOR, COMO SE ANUNCIO: 43 de 243 puntos sin contestar, 18%, contra 22 de 206 (11%) de ayer. NO es una regresion, es la verdad apareciendo** — las preguntas informativas ahora abren punto, asi que aparecen los que siempre estuvieron sin contestar. Lo que queda abierto es bajarlo: hoy la cobertura se escribe en el log y no frena nada, y eso es la FICHA 08.
- **ABIERTO** · **Ante un tema `ambiguous` el codigo SIRVE TODOS LOS CANDIDATOS en vez de repreguntar, y eso se aparta de lo que pedia la FICHA 06.** Repreguntar ahi seria pedirle al cliente que elija entre dos nombres de nuestro archivero —"¿garantia o garantia_como_usar?"—, que es la falla que el repo ya diagnostico el 4-ago al unir los dos enums. No se elige, que es la parte que importa de la regla cero: se sirven las dos politicas enteras y el modelo contesta la que preguntaron. Medido sobre las 785 señas: 1,37 temas servidos por seña, cero choques ciegos. **Si Martin quiere la repregunta, es una linea en `certificar_temas`.**
- **ABIERTO** · `banco_pruebas/banco_llamada_uno.py` mide que herramienta ELIGE el modelo, y desde la puerta unica el modelo no elige ninguna. Sus 14 casos siguen siendo buenas preguntas —"¿entendio que era una condicion de origen?"— pero hay que reapuntarlos a lo DECLARADO. Hasta que eso pase, sus numeros no quieren decir nada.
- **ABIERTO** · **`puerta_piso.json` guarda PORCENTAJES atados a un corpus que cambia, y eso da falsos rojos. Se refijó el 22-ago, pero el defecto de diseño sigue.** Al regrabar los casetes se puso rojo diciendo `reparto_pago: 11.1% -> 9.1%`, como si el código entendiera menos. **No entendía menos: sacaba el mismo 1 turno.** Cambió el denominador, porque el modelo declaró reparto de pago en 11 turnos en vez de 9. Los otros cinco números subieron o quedaron igual —items 78,4→83,3, destinos 41,2→47,1, restricciones 60,0→66,7, turnos medidos 51→53— así que el refijado no baja ninguna vara. **Un piso que guarda una RAZÓN contra un corpus mutable mide dos cosas a la vez y no puede decir cuál se movió**, que es la misma enfermedad que la FICHA 03 curó en el otro piso. Guardar el numerador y el denominador por separado lo arregla, y hasta que eso pase sus rojos hay que leerlos con pinzas.
- **ESPERA A MARTIN** · Los pares de temas que comparten una palabra —`factura`/`precios_iva` con "iva", `cuotas`/`cuotas_financiacion`, `regalo`/`envoltorio_regalo`— **dejaron de hacer daño: la certificacion los sirve a los DOS y el modelo contesta con las dos politicas delante.** Cero choques ciegos sobre las 785 señas, medido en `tests/test_barrido_faq.py`. Darle a cada uno su seña propia sigue siendo una mejora de la FUENTE, pero ya no es un agujero.
- **ESPERA A MARTIN** · El sistema SIN LLM está medido en `banco_pruebas/puerta_determinista.py` y el número es alto. Lo que ninguna pieza ve es la NEGACIÓN —"el teclado sacalo"— y lo que no tiene pieza es `pide_precio` y `contradicciones`. Sirve como modo degradado para cuando el modelo se cae; NO se deploya en paralelo al vivo.
- **ESPERA A MARTIN** · `villa, Buenos Aires` resuelve a un CP que el cliente no nombró. Daño chico —misma tarifa de interior— pero es el sistema eligiendo por el cliente. Se arregla en `geo_cp.resolver`.
- **ESPERA A MARTIN** · Cuánto tiempo se guardan las conversaciones y con qué criterio se borran. Desde el 19-ago el bot pide solo el nombre, así que la superficie es chica, pero la decisión de retención es suya y conviene tomarla antes de vender a una empresa.

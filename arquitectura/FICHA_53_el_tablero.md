# FICHA 53 — EL TABLERO

**Es el componente 7 de la FICHA 52 y nada mas.** El tablero es el indice de lo
que se puede preguntar: viaja antes del motor y su unico trabajo es que el
modelo escriba UNA consulta que pegue a la primera. Las bocas, los ramales y el
retorno se nombran por su numero de la 52 y no se vuelven a describir.

Escrita el 13-sep-2026 y **reescrita el mismo dia con el codigo ya hecho**, que
es la unica forma de que una ficha no mienta. Lo que corre lo dice el codigo;
si esto lo contradice, gana el codigo.

**NO ES UNA CAJA NUEVA DEL CROQUIS.** El croquis de la 52 no cambia: TABLERO →
MODELO → MOTOR → BOCAS → RETORNO. Lo que esta ficha agrega vive ADENTRO del
tablero, que ya estaba dibujado. Mas efectividad, cero cajas.

---

## 1. QUE ES

**El tablero NO TIENE UN SOLO DATO.** No dice que producto hay ni a que precio.
Dice **con que palabras se pregunta**.

**Un valor enumerado no es un dato, es vocabulario.** Que la fuente escriba
`china` no dice que producto es chino: dice que esa es la palabra. Por eso el
tablero no crece con el catalogo: crece con la VARIEDAD. Vara en
`tests/test_tablero.py`, que verifica que no se cuele un id ni un precio.

**Viaja como esquema de la herramienta, no como texto.** Es el parametro
`tools` de la llamada. El enum cierra los NOMBRES de campo: uno que no existe
no se puede ni nombrar.

---

## 2. EL DEFECTO QUE ARREGLA, MEDIDO

El tablero de ayer daba los 41 nombres de campo y las 22 categorias, y nada
mas. Le faltaban cuatro cosas y cada una tenia su costo.

**1. No decia que VALORES usa la fuente.** `pais_fabricacion` tiene cinco:

    633  china
     96  taiwan o china segun linea
     72  tailandia o malasia segun linea
     60  china, taiwan o corea segun linea
     19  malasia o vietnam segun linea

`igual china` trae 633. `contiene china` trae 789. **156 productos de
diferencia, el 18% del catalogo**, decididos por un operador que el modelo
elegia a ciegas. Los NO chinos de verdad son 91.

**2. No decia en cuantos productos esta cargado el campo.** `memoria_video`
esta en 18 de 880. Filtrar por ahi devuelve casi nada, y ese casi nada se lee
como "no lo tenemos" en vez de "no esta cargado": la respuesta 2 dicha como la
3, que la FICHA 52 llama el defecto mas caro del nicho.

**3. Ofrecia ordenar por los 41 campos.** Sobre una etiqueta el orden es
alfabetico y no contesta ninguna pregunta que un cliente pueda hacer.
`orden_tiene_sentido` ya lo rechazaba DESPUES: el modelo gastaba una consulta
para que el motor le dijera que no.

**4. Nombraba dos bocas de cinco.** Una boca que el tablero no nombra no existe
para el modelo, aunque tenga cable.

---

## 3. COMO QUEDO — tres partes

**PARTE A · LAS CINCO BOCAS.** En la descripcion de la herramienta. Que se pide
por aca —catalogo y politicas— y que todavia NO tiene cable —compatibilidad,
criterio y envio—. Lo que falta se dice; no se finge.

**PARTE B · EL VOCABULARIO**, en `filtros_catalogo.leyenda`. Tres formas de
renglon, y ninguna mas:

    NUMEROS      el rango, no la lista: precio_ars de 8.500 a 3.100.500
    ETIQUETAS    los valores, con su carga: color (861/880): negro | blanco | ...
    FLACOS       los cargados en menos del 30%, nombrados juntos

**PARTE C · LO QUE LA FUENTE NO TIENE.** `sin_campo_en_la_fuente` para el
pedido que ningun campo expresa, `no_vendidas` para el rubro que la tienda no
vende, y el hueco de valor de la seccion 5. **Las tres son respuestas, no
errores.**

---

## 4. QUIEN ENTRA EN LA LEYENDA, Y POR QUE ASI

**No se cuenta valores: se mide el renglon.** Contar dejaba afuera al barato y
adentro al caro. `marca` tiene 75 valores y pesa 825 caracteres, y es de los
campos que mas nombra un cliente; `puertos` tiene 43 y pesa 1.700, porque cada
valor es una lista.

**El orden lo decide el RENDIMIENTO:** en cuantos productos esta cargado el
campo, dividido lo que cuesta su renglon. Se llena el presupuesto con lo que
mas contesta por caracter y se corta. **Ninguna lista escrita a mano:** una
tienda nueva con otra fuente se ordena sola.

**Un valor que no entra en un renglon no se enumera nunca.**
`contenido_caja` tiene 22 valores —poca variedad— y cada uno es un parrafo:
enumerarlo pesaba 675 tokens de prosa. Los dos topes viven en
`filtros_catalogo`: `LARGO_ETIQUETA` y `TECHO_LEYENDA`.

---

## 5. EL HUECO DE VALOR — la decision que mas cambia el turno

**Un valor que la fuente no usa NO PUEDE DEVOLVER CERO.** Cero se lee como "no
lo tenemos". El hueco se lee como "esa palabra no es la nuestra, estas si".

El motor no filtra por esa condicion, lo dice, y devuelve los valores reales:

    la fuente no escribe 'japon' en pais_fabricacion; lo que dice es:
    china | taiwan o china segun linea | ... No se filtro por eso: volve a
    pedir con una de esas

Es la misma escuela que `SIN_CAMPO`, que ya vivia en `filtros_catalogo`.

**Solo sobre campos cuyo vocabulario se conoce entero.** Sobre `modelo`, con
482 valores, el que contesta es el rescate por cercania, que ya existe y ya
devuelve lo mas parecido con el motivo al lado.

---

## 6. EL CASO G15

    modelo contiene g15  →  9 filas, 3 modelos, marca Dell
    modelo contiene g16  →  9 filas, 3 modelos, marca Asus

El borde de un numero son otros digitos —la regla que ya vive en `_raices`—,
asi que `g15` no puede traer una G16 ni una G150. Vara en
`tests/test_tablero.py`, los dos codigos.

**Y por eso los 482 modelos no entran al tablero.** Los valores de alta
variedad no se enumeran nunca: los ata el motor, no el indice.

---

## 7. LOS NUMEROS, MEDIDOS EL 13-sep

El metodo: se serializa como viaja, se cuentan los bytes, se divide por cuatro.
No hay tokenizador en el repo; lo que importa es medir siempre igual.

    LA LEYENDA                              920 tokens
    EL TABLERO entero, con la leyenda     2.001    (antes 1.047)
    EL PROMPT, reglas mas 20 tipos        1.488    (antes 1.828)

**El tablero viaja DOS veces por turno y el prompt TRES.** En la ultima vuelta
la herramienta ya no viaja: es la vuelta de contestar. Un turno de tres vueltas
paga:

    antes  844×3 + 1.047×2 = 4.626
    ahora  580×3 + 2.001×2 + 211×2 = 6.164

**+1.538 por turno, y el negocio esta en otro lado:** una vuelta de mas cuesta
del orden de 7.700 tokens y entre uno y dos segundos. El tablero se paga solo
si ahorra UNA vuelta cada cinco turnos.

**Por eso el techo que manda no es el del bloque, es el del TURNO.** El techo
de bloque —`TECHO_TABLERO`, 2.100— existe para que nadie engorde el indice sin
darse cuenta, y solo baja. El que dice si esto sirvio es la media de vueltas
por turno, en `motor_turno`.

---

## 8. LA MUDANZA, Y EL PARRAFO QUE NO SE MUDO

Cada cosa viaja cuando sirve, y nada se borro:

    ensena a BUSCAR              → al esquema. Muere en la vuelta de contestar.
    ensena a LEER LO QUE VOLVIO  → al encabezado del retorno. Nace con el retorno.
    ensena a CONTESTAR y VENDER  → al prompt. Siempre.

**`busco` NO se mudo, y la vara lo freno a tiempo.** Medido el 12-sep: con
`busco` viviendo solo en la descripcion de la herramienta, **0 de 9 consultas
lo declararon** y la ambiguedad no se podia disparar nunca. Vara en
`tests/test_turno_nuevo.py`. Es la unica excepcion y tiene medicion.

**LOS CINCO ATRIBUTOS DE VENTA ENTRARON AL PROMPT, y no estaban en ningun
lado.** Tres de los cinco de la FICHA 52 §5 no aparecian: no repetir, no
reofrecer lo rechazado, una sola pregunta. El bot estaba atado para no mentir y
no estaba instruido para vender.

---

## 9. LO QUE NO SE HACE

- **Embeddings.** Regla 10.4: un vecino cercano no se mapea a un id.
- **Mandar fichas o un resumen del catalogo.** Crece con la cantidad.
- **Una herramienta nueva al lado de `buscar`.** Serian dos puertas.
- **Una flag apagada para medir.** Regla 2-bis.
- **Listas de campos escritas a mano.** Todo sale de la fuente viva.

---

## 10. LO QUE SE MIDIO VIVO, EL 13-sep

**Con la clave GRATIS**, dos tandas de catorce mensajes que cubren los catorce
pedidos de la FICHA 52. El banco es `banco_pruebas/tanda_tablero.py` y el piso
queda en `banco_pruebas/tablero_piso.json`. **28 turnos corridos, 22 sanos:**
los seis que faltan murieron con `RateLimitError` de la cuota gratis, que es lo
que la regla 4 dice que pasa y por eso se cuentan aparte en vez de ensuciar el
promedio.

    VUELTAS POR TURNO       2,23   contra 3,00 del 12-sep
    BUSCARON                22 de 22   contra 15 de 19
    BUSQUEDAS VACIAS        0
    HUECOS DE VALOR         4, y los cuatro correctos
    `busco: uno`            4 de 4 oportunidades
    CONSULTAS REPETIDAS     6 de 31

**EL TABLERO SE PAGA.** Cuesta 1.538 tokens por turno y ahorra 0,77 vueltas;
una vuelta vale del orden de 7.700, o sea unos 5.900 ahorrados. **Queda a favor
por cuatro a uno**, y eso sin contar el segundo y medio de latencia que cada
vuelta se lleva.

**EL HUECO DE VALOR FUNCIONA Y APARECIO SOLO.** Los dos de cada tanda:
`pais_fabricacion japon`, que es el caso buscado, y `caracteristicas_extra
mecanico`, que no lo era —el modelo fue a buscar "teclado mecanico" a un campo
donde la fuente escribe otra cosa—. Los dos volvieron con los valores reales en
vez de con un cero.

**`busco` SE DECLARA CUANDO CORRESPONDE, y el primer numero enganaba.** "2 de
18 consultas" parecia un fracaso: `uno` solo corresponde si el cliente nombro
un producto puntual, y de los catorce mensajes hay dos asi. Los dos lo
declararon, las dos tandas. El banco ahora cuenta sobre el denominador que
corresponde.

**LA CONSULTA REPETIDA SE CERRO EL MISMO DIA, Y LA CAUSA NO ERA LA ESCRITA.**
El comentario de `_anotar` decia que el modelo repite porque entre vuelta y
vuelta no ve lo que ya pidio. Ese texto quedo viejo: `hallazgos` hoy le manda
"Buscaste: ..." de vuelta, asi que si lo ve. El crudo de la tanda muestra otra
cosa: **manda dos consultas IDENTICAS en la MISMA llamada**, donde no hay
vuelta de por medio.

Por eso el arreglo es determinista y vive en el motor, no en el prompt: pedirle
al modelo que se acuerde cuesta tokens en cada turno para garantizar algo que
el codigo garantiza gratis. La repetida vuelve **en su lugar y sin filas** —en
su lugar porque el modelo mando N consultas y tiene que recibir N resultados;
sin filas porque copiarlas seria mandarle las mismas fichas dos veces adentro
del mismo retorno, que es el gasto que esto saca—.

Y el recorte de `hallazgos` paso de 900 a 1.400 caracteres: un pedido abierto
manda cinco consultas que dan 959, asi que la quinta llegaba partida.

**Tercera tanda, ya con esto adentro: 14 de 14 turnos sanos, 2,21 vueltas, cero
sin respuesta.**

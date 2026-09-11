# PLAN DE LA INTERPRETACION — la unidad de trabajo abierta

Escrito el 10 y 11 de septiembre de 2026. Reemplaza a nada: es lo que sigue.
Si una sesion nueva lee el bloque 0 de `CLAUDE.md` y `MAPA.md`, este es el
tercer archivo que tiene que leer, y con esos tres arranca sabiendo donde
estamos. No hay que leer nada mas para empezar.

## EL NUMERO, Y COMO SE SACA

    Interpretacion: 30 turnos exactos de 36. 83 por ciento. 10-sep-2026.

Se saca comentando `/vara` en el issue 31. El workflow corre
`banco_pruebas/banco_llamada_uno.py` contra el modelo real, deja la salida
entera en `banco_pruebas/salidas/vara_<corrida>.txt` y contesta en el issue.
Nadie pega una clave en un chat y nadie copia resultados a mano.

QUE MIDE. Si el modelo declara en la CASILLA que corresponde, y nada mas. No
llega a la respuesta. Mide en las dos direcciones: las casillas que tienen que
venir llenas y las que tienen que quedar vacias. La segunda mitad es la que
importa, porque el fallo tipico es llenar de mas.

La corrida anterior dio 28 de 36, y la diferencia NO fue el modelo: dos casos
de la vara estaban mal escritos y se aflojaron. Queda anotado porque es la
trampa de siempre: antes de culpar al sistema hay que mirar si la vara mide lo
que dice medir.

## LOS SEIS FALLOS QUE QUEDAN, EN DOS FAMILIAS

FAMILIA 1, EL SUPERLATIVO SIN RUBRO. Tres casos. Cuando el cliente no nombra un
rubro, el modelo se queda sin que poner en `items` y empuja la pregunta a la
casilla equivocada.

    "Dime cual es el producto mas caro que tienen"    se fue a `temas`
    "Cual es el producto mas caro de toda la tienda"  se fue a `temas`
    "Tienes algun producto con origen estados unidos" se fue a `atributos`

Con rubro nombrado -"el mouse mas barato", "microfonos marcas estados unidos"-
el mismo modelo lo declara bien en `restricciones`. O sea que entiende: lo que
falta es una casilla donde poner una pregunta que es sobre el catalogo entero y
no sobre un producto.

FAMILIA 2, LA CASILLA QUE NO SE LLENA. Dos casos: "que teclado tiene la garantia
mas larga" y "cual es el mouse mas liviano", donde declara la condicion pero no
el rubro en `items`.

Y uno suelto: "de donde viene, es chino", que declara bien el atributo y ademas
abre `temas` de mas.

## LOS DOS HALLAZGOS QUE CAMBIAN EL PLAN

PRIMERO, Y CORRIGE LO QUE SE CREIA: el vocabulario de `campo` YA esta cerrado y
se respeta al cien por ciento. `herramientas.esquemas()` inyecta el enum desde
el catalogo vivo -41 campos- con `sin_campo_en_la_fuente` como escapatoria, y en
36 casos el modelo no se salio ni una vez. `pais_fabricacion`, que se habia dado
por inventado, existe de verdad en la fuente. NO HAY NADA QUE CERRAR AHI, y ese
trabajo se cae de la lista.

SEGUNDO, Y ES EL QUE MANDA: de 14 temas declarados, 6 existen, 7 vuelven
AMBIGUOS y 1 no existe. La mitad son ambiguos. Ambiguo no significa que falle:
significa que el nombre libre que puso el modelo coincide con varias claves de
la casa a la vez, y el sistema se queda con TODAS y las redacta.

De ahi salio, medido el 9-sep con la sonda, el peor mensaje del dia: "tienes
algun producto con origen estados unidos" volvio con seis parrafos, uno
hablandole de compatibilidad con consolas.

## EL PATRON QUE FUNCIONA, Y DONDE FALTA APLICARLO

La casilla `atributos` tiene DOS campos: `de`, que es el texto crudo del
cliente, y `campo`, que es cerrado y sale de la fuente. Esa casilla acierta 26
de 27 y no se sale del enum ni una vez. Es la unica casilla con esa forma y es
la que mejor mide.

`temas` tiene UN campo y es libre. Ahi esta el 50 por ciento de ambiguos.

ENTONCES EL TRABAJO ES REPLICAR LA FORMA, no inventar una nueva: cada casilla
que hoy pide una clasificacion deberia tener un campo CRUDO con las palabras del
cliente y un campo CERRADO elegido de una lista de la fuente. Empezando por
`temas`.

Y hay una regla que el repo YA TIENE ESCRITA y aplica en un solo lado. En
`tabla._candidatos_ambiguos` dice, textual, que ambiguo no es un error ni una
falta de material: es el unico veredicto ante el cual el codigo tiene PROHIBIDO
elegir. Para un producto ambiguo el sistema pregunta cual de estos. Para un tema
ambiguo se queda con todos. La regla existe; falta aplicarla donde mas duele.

## EL ORDEN DEL TRABAJO, Y NO SE HACEN DOS COSAS A LA VEZ

Cada paso se mide con `/vara` ANTES y DESPUES. Si el numero no se mueve, el paso
no sirvio y se revisa antes de seguir.

1. UN TEMA AMBIGUO NO SE EXPANDE. Aplicar a los temas la regla que ya existe
   para los productos: o se descarta, o se pregunta, pero no se redactan los
   tres candidatos. Es el cambio que corta los parrafos de mas y no toca la
   interpretacion.

2. `temas` PASA A DOS CAMPOS: uno crudo con las palabras del cliente y uno
   cerrado con las claves de la casa, igual que `atributos`. Con la escapatoria
   correspondiente para cuando ninguna clave sirve.

3. LA CASILLA QUE FALTA, para una pregunta sobre el catalogo entero: el mas
   caro, el mas barato, cuantos hay de tal cosa, de que origen. Hoy no existe y
   por eso esas preguntas caen en `atributos` o en `temas`.

4. RECIEN DESPUES, la señal de confianza: correr la declaracion dos veces y
   comparar; donde las dos corridas difieren hay ambigüedad real y ahi se
   pregunta en vez de actuar. Es lo que convierte el resto de errores, que
   ninguna tecnica elimina, en una pregunta honesta.

## LO QUE YA QUEDO HECHO Y NO SE REPITE

- 9-sep: la sonda de turno, `banco_pruebas/sonda_turno.py`, muestra las ocho
  etapas por dentro sin tocar el codigo. Se pide con `/sonda`.
- 9-sep: D14 cerrada. Una fila sin material ya no aporta prosa del modelo, y la
  apertura pasa por la poda. Ahi se cortaba la alucinacion sin cifras.
- 10-sep: la vara de la llamada uno, que estaba MUERTA desde el 3-sep porque
  importaba el hub borrado, y ademas medía un blob de todas las casillas juntas
  y daba verde con la casilla equivocada.
- 10-sep: el orden del repo, etapa 1. La raiz bajo de 31 entradas a 23 y de 14
  documentos a 4, y aparecio `MAPA.md`.
- 11-sep: el primer corte de la etapa 2. El molde salio a `app/core/molde.py`:
  los moldes de Pydantic, `_MOLDES`, `esquemas()` y el saneo de nulos. No cambio
  comportamiento, `herramientas.py` los sigue exportando con los mismos nombres,
  y bajo de 2.612 lineas a unas 2.040. Los pasos 2 y 3 se editan en el molde.

## EL CORTE DE LOS ARCHIVOS GRANDES — etapa 2 del orden

MEDIDO, no estimado. `herramientas.py` tiene 2.612 lineas y 61 definiciones;
`resolver.py` 1.505 y 20; `turno.py` 1.241 y 23.

EL PRIMER CORTE, HECHO EL 11-SEP: el MOLDE salio de `herramientas.py` a
`app/core/molde.py`. Son los modelos de Pydantic
-`RegistrarPedido` y sus hermanos, 139 lineas solo la clase principal- mas
`esquemas()`, que es donde se inyectan los enums. Es exactamente lo que hay que
editar para los pasos 2 y 3 de arriba, y hoy vive mezclado con las herramientas
de consulta.

Los cortes que siguen, cuando haga falta y no antes:

    herramientas.py   `_lista` 337 lineas, `_presupuesto` 239, `_catalogo` 120,
                      `_compatibilidad` 101, y los temas -`certificar_tema`,
                      `temas_consultables`- que son 130 juntos.
    resolver.py       `_derivar_las_busquedas` 325 y la cuenta
                      -`_cuenta_con_lo_declarado` 273 mas `_bloques_a_uno` 160-.
    turno.py          es el mas legible de los tres y el que mas se lee entero.
                      No se corta salvo que estorbe.

REGLA DEL CORTE: se mueven funciones, no se cambia comportamiento, el nombre
viejo sigue importando del nuevo, y la bateria corre antes y despues. Un corte
por vez.

## COMO ARRANCA UNA SESION NUEVA SIN GASTAR DE MAS

Tres archivos y nada mas: el bloque 0 de `CLAUDE.md`, `MAPA.md`, y este.

Despues, para cualquier cosa, se va al archivo que dice el mapa. NO se lee el
repo entero ni se exploran carpetas: eso es lo que gasta.

Para ver el sistema por dentro no se pide que Martin corra nada ni que pegue
resultados: se comenta en el issue 31.

    /logs sev=INFO fresh=6h limit=300     produccion: logs e invariantes
    /sonda <pregunta>                     un turno completo por dentro
    /vara                                 los 36 casos de interpretacion

Y para leer esas salidas conviene mirar la COLA del archivo, que es donde estan
los numeros, y no el archivo entero.

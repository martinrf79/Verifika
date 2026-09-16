# FICHA 55 — EL RUTEO ES DEL MOTOR, NO DEL MODELO

**Decision de Martin, 16-sep-2026.** Unidad de trabajo abierta. La FICHA 54
queda cerrada: sus seis pasos estan hechos y el ultimo se midio en vivo.

Los nombres —bocas, ramales, retorno, tablero— se definen en la FICHA 52 y en
`MAPA_CABLEADO.md`. Aca no se vuelven a describir.

---

## 1. LA CONSIGNA, EN UNA LINEA

**A que boca va cada parte del mensaje lo decide el CODIGO, no el modelo.**

El modelo traduce, elige entre lo que volvio y redacta. Eso es lo que sabe
hacer. Elegir la boca es ruteo, es la decision mas variable del turno, y hoy
esta del lado que menos garantias da.

**NO ES UNA IDEA NUEVA: ES LA DECISION 1 DEL 19-AGO**, en `papeles/
DECISIONES.md` —"la llamada UNO solo DECLARA; el codigo deriva las
busquedas"—, con su motivo medido: en el 57% de los turnos lo declarado y lo
buscado no coincidian. Se construyo —`indice_turno`, 1.738 lineas— y se apago
el 11-sep con el hub. **El apagon estuvo bien y no se revierte.** Lo que se
fue con el agua fue el contrato del turno, y eso es lo que vuelve, chico.

---

## 1-bis. LAS DOS ACTIVIDADES DEL MODELO, Y NINGUNA MAS

**Decision de Martin, 16-sep-2026.** El modelo hace dos cosas:

1. **TRADUCE.** Lee el mensaje del cliente y llena la planilla con SUS
   palabras: que pide, que intencion trae. Es lo unico que el codigo no puede
   hacer -"un rectangulo con teclas" es `teclado`- y es la mitad del punto 1.
2. **REDACTA Y VENDE.** Escribe la respuesta con los cinco atributos de venta
   de la FICHA 52 §5, **y TODOS los datos que escribe salen del codigo.**

**TODOS QUIERE DECIR TODOS**, y la lista no es una enumeracion de casos —que
es lo que se desincroniza— sino una sola regla: **si el cliente lo puede
verificar contra la tienda, salio del codigo.** Producto, precio, stock,
plazo, tarifa, total, politica, veredicto de compatibilidad **y tambien las
NEGACIONES**: "eso no lo tenemos", "no puedo filtrar por ahi", "no lo
vendemos".

**DONDE ESTA EL LIMITE, y escribirlo es lo que evita que esto se lea como una
promesa imposible.** El dato es del codigo; **la PROSA es del modelo**: el
orden de las frases, los conectores, el tono y la pregunta final. Si la prosa
tambien saliera del codigo volvemos al solver de fragmentos que se borro el
2-ago —`DECISIONES.md` #10— y el bot deja de vender.

**COMO SE LOGRA, y no es un mecanismo nuevo: es `DECISIONES.md` #11**, los
cuatro niveles de atadura, escrito el 19-ago y construido a medias.

    enum                 el modelo solo puede NOMBRAR lo que existe   · vivo
    bloque sellado       lo que afirma plata o politica vuelve YA
                         ESCRITO del codigo y se pega                 · a medias
    ancla por afirmacion toda oracion que afirma apunta a un dato
                         que volvio; los conectores son libres        · NO existe
    lo prohibido         la lista corta de lo que no se dice nunca    · vivo

**LA PIEZA QUE FALTA ES LA TERCERA, y la FICHA 52 §18 ya la tiene escrita como
la segunda regla de la guarda:** si el texto nombra un producto, un precio, un
plazo, una politica o una cuenta y NO hubo retorno, no sale. Hoy la guarda
mira cifras —`numeros.py`— y nada mas.

**Y LA NEGACION SE RESUELVE DANDOLA VUELTA, que es lo barato:** el motivo de
por que algo no se pudo cumplir YA vuelve escrito del motor —el hueco de
valor, `sin_campo`, `no_cumple`, `sin_dato`—. El modelo lo COPIA, no lo
redacta. Asi la negacion deja de ser prosa y pasa a ser un dato, que es como
se puede verificar. **Perseguir la frase con una lista de palabras no se hace:
ya fracaso tres veces.**

---

## 2. LO QUE SE MIDIO EN VIVO, 15 y 16-sep

Cuatro turnos por WhatsApp sobre UN pedido de dos auriculares, dos mouse y dos
memorias, con tres destinos y el pago repartido setenta treinta. Se leen con
la pelicula: `python3 banco_pruebas/produccion.py --desde 8h`.

**LO QUE ANDUVO.** El modelo llamo al motor en los cuatro turnos. Escribio la
consulta igual las cuatro veces —categoria, `busco`, cantidad—. Pidio el
teclado que el cliente nombro solo en el reparto de envios. Y el filtro de
origen funciono: `pais_fabricacion no_contiene china` volvio `no_existe` en
las cuatro categorias, y es correcto, porque los 46 auriculares, los 52 mouse
y los 48 teclados dicen `china` y las 96 memorias dicen `taiwan o china segun
linea`. Cero cumplen. **Eso no es un defecto del motor: es el D8, y es de
FUENTE.**

**LO QUE FALLO, y los dos primeros ya estan arreglados —lo cuenta `git log`—:**

    el carrito se rearmaba cada turno      207.500 · 284.000 · 395.000
    el envio cotizado no salia             3 destinos, 0 montos en el texto
    afirmo sobre un campo sin consultarlo  "no tenemos el pais de fabricacion"
    la cuenta no se pidio en el complejo   las dos vueltas se fueron buscando

---

## 3. LOS SIETE CONFLICTOS, y por que parchar de a uno no cierra

No son siete errores: son siete sintomas de que **el PEDIDO no existe como
estado**. Cada arreglo que se hace sin esa pieza se fabrica su propia memoria
local, y esa memoria choca con la del arreglo de al lado. Es la forma exacta
de las tres cascadas que este repo ya pago: los 116 regex, las 70 flags y los
13 mutadores encadenados.

| # | el conflicto | el arreglo |
|---|---|---|
| 1 | catalogo da cinco opciones, la cuenta exige uno | la cuenta acepta una LINEA por rubro con regla escrita |
| 2 | la memoria guarda 20 vistos y muestra 8, en silencio | el corte se dice o no existe |
| 3 | el retorno muere al terminar el turno | lo que volvio sobrevive **· hecho para la cuenta, 15-sep** |
| 4 | nadie controla lo que el modelo AFIRMA de la fuente | el ancla por afirmacion del §1-bis; la negacion la escribe el codigo y el modelo la copia |
| 5 | una condicion filtra o no filtra, no hay grado | la condicion se puede pedir como PREFERENCIA: ordena, no descarta |
| 6 | `contradicciones` lo declara el modelo y no lo lee nadie | el codigo cruza lo pedido contra lo repartido |
| 7 | dos vueltas no alcanzan cuando hay cuenta | con el 1 resuelto, la cuenta entra en la misma llamada |

---

## 4. LAS TRES COSAS QUE HAY QUE HACER, en orden

### 4.1 EL RUTEO PASA AL MOTOR · **PRIMER PASO HECHO, 16-sep**

El modelo llena una PLANILLA PLANA: que pide el cliente, renglon por renglon,
con SUS palabras. No elige boca.

**LO QUE YA CORRE.** La planilla existe y es OBLIGATORIA en el tablero
—`pedido`, con `id` y `dice`—, el modelo declara en `atiende` que renglones
cubre cada llamada, y el motor resta por ID y devuelve `sin_atender` con las
palabras del cliente. El cruce es por identificador y no por palabras
compartidas, que es lo que lo separa de D3, D4, D6 y D16. Costo medido: +24
tokens en el tablero, porque lo que pesa la planilla se pago consolidando las
descripciones que repetian el indice y el encabezado del retorno.

**LO QUE FALTA, y es la otra mitad.** El codigo todavia no RUTEA: sigue siendo
el modelo el que decide a que boca va cada renglon. Lo que se gano es que un
renglon no pueda desaparecer en silencio. Correr `certificar_temas`,
`criterio_de`, `geo_cp` y el certificador de identidad ANTES, para que ellas
elijan la boca, es el paso que queda.

El motor rutea cada renglon con las certificaciones que **ya existen y hoy
corren tarde**: `certificar_temas`, `criterio_de`, `geo_cp`, el vocabulario de
compatibilidad y el certificador de identidad. Hoy todas corren DESPUES de que
el modelo eligio la boca. Se trata de correrlas ANTES y que ellas elijan.

**Chico a proposito.** Una planilla, no un grafo de puntos con actuadores. Lo
que se apago pesaba mil setecientas lineas; esto es una lista.

### 4.2 UNA SOLA DEFINICION DE LAS BOCAS

El tablero, el encabezado del retorno y lo que el prompt promete se escriben
HOY a mano en tres lugares. Por eso el encabezado tardo tres dias en enterarse
de que habia cinco bocas, y por eso el envio cotizado no salia.

**Una definicion, tres vistas derivadas.** Es la regla del `MAPA_CABLEADO`
aplicada al codigo: la segunda descripcion de lo mismo es el telefono
descompuesto. Vara puesta el 16-sep en `tests/test_retorno_se_explica.py`,
que ya impide que una boca vuelva muda.

### 4.3 EL PEDIDO COMO ESTADO, Y NACE MUDO

Que se pidio, que se resolvio, que falta. **Primero solo se escribe y se
loguea**, sin cambiar una respuesta. Cuando el renglon coincida con lo que se
lee en la charla real, recien ahi se le da poder de frenar. Asi nacio el
indice viejo y asi se revierte gratis.

---

## 5. LAS SEIS REGLAS CONTRA LA CASCADA

Martin, 15-sep. Valen para esta unidad entera.

1. **Una sola pieza nueva por vez, y que sea la que falta.** Si un arreglo
   necesita memoria propia, esta mal planteado.
2. **La pieza nace muda.**
3. **Un arreglo, un deploy, un numero.** Y el numero no es que la bateria
   pase: es el renglon sobre turnos REALES.
4. **Ninguna guarda que persiga palabras.** Perseguir prosa ya fracaso tres
   veces: 4 nodos, despues 18, despues 46. Las condiciones son de ESTADO.
5. **Por cada pieza que se prende, una que se apaga.**
6. **El error nuevo que asoma al editar se ANOTA, no se arregla en el
   momento.** Salvo que rompa lo que esa misma pieza prometia. Perseguir el
   error que asoma es lo que convierte tres horas en tres dias.

---

## 6. LO QUE NO SE HACE

- **Cambiar la arquitectura.** Ya se cambio tres veces y el defecto sobrevivio
  a las tres, porque no era de arquitectura. La puerta unica, la certificacion
  y las cinco bocas se quedan.
- **Partir el turno en varias llamadas.** Medido: seis segundos y la cuota
  diaria de a tres.
- **Obligar la busqueda en la primera vuelta.** Hoy es `tool_choice: auto` y
  no hace falta: en los cuatro turnos medidos el modelo busco siempre, y
  `turno_sin_buscar` no aparecio. Forzarlo haria que un saludo gaste una
  consulta. **Si la pelicula muestra un turno que debia buscar y no busco, es
  una linea y se hace ahi.**
- **Un banco de prueba nuevo.** Se mide con la pelicula, sobre charlas reales.

---

## 7. COMO SE MIRA, Y ES LO QUE CAMBIO EL 15-sep

`banco_pruebas/produccion.py` arma **la pelicula del turno**: con que palabras
pidio el modelo, que tenia delante cuando las escribio, que volvio y que
contesto. Sale por el issue 31 y desde cualquier sesion con la clave de
lectura. Los dos renglones que la hacen posible —`motor_pedido` y
`prompt_armado`— los escribe el turno vivo.

**EL NUMERO DE ESTA UNIDAD: la consistencia entre turnos.** Mismo pedido,
turnos sucesivos, ¿vuelven los mismos ids y el mismo total? El 15-sep fue
**cero de tres**. Si con el pedido guardado ese numero no sube, la discusion
es otra y se tiene con el dato en la mano.

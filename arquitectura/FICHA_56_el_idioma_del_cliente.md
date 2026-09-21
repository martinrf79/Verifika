# FICHA 56 — EL IDIOMA DEL CLIENTE

**Abierta el 21-sep-2026. Es un ESTUDIO, no una implementacion.** No toca una
linea de codigo. Su producto es una lista, y esa lista es la que despues
decide que forma tiene el indice.

**LA CONSIGNA DE MARTIN, textual:** abarcar casi todas las preguntas posibles
de e-commerce de complejidad similar a "un aparato rectangular con varias
teclas". Ser lo mas abarcativo posible ANTES de decidir nada. Lo que queda
afuera se cubre despues con repregunta.

---

## 0. QUE ENTRA Y QUE NO — el test, en una linea

> **Una frase es CRITERIO si NINGUNA busqueda contra la fuente la resuelve.**

    "tenes el K120?"                    lo resuelve una busqueda   → FUENTE, otro estudio
    "aparato rectangular con teclas"    no lo resuelve nada        → CRITERIO
    "dada la crisis"                    no lo resuelve nada        → CRITERIO
    "que no sea chino"                  MITAD Y MITAD (ver eje C)

El eje C es el borde: el VALOR `china` sale de la fuente, pero decidir si eso
filtra, ordena o excluye es criterio. Por eso esta aca y no en el otro estudio.

**ESTE ESTUDIO NO ES GRAMATICAL.** Es semantico, y son dos cosas: **como se
REFIERE** el cliente a algo sin nombrarlo, y **como se UBICA** en una escala.
Las dos son inventarios chicos y cerrados, y por eso esta lista puede aspirar
a ser casi completa en vez de una coleccion de ocurrencias. Perseguir frases
con una lista de frases ya fracaso tres veces en este repo —4 nodos, 18, 46—;
lo que no fracasa es tener los EJES.

**DE DONDE SALE.** Tres fuentes, y se dice cual es cual:
- lo que el repo ya sufrio: los 94 guiones, `barrido_orden`, `preguntas.py`,
  los mensajes reales de WhatsApp de la vara;
- la literatura de *tip-of-the-tongue known-item retrieval*, que estudia
  justo como alguien describe lo que no sabe nombrar, y de donde salen cuatro
  fenomenos que no teniamos: la duda declarada, la exclusion, la comparacion
  relativa y **la premisa falsa**;
- y simulacion deliberada de un comprador argentino por WhatsApp, que es lo
  que Martin pidio expresamente y es lo que hace que esto no sea un censo de
  lo ya visto.

---

## EJE A · NOMBRAR LA COSA SIN SU NOMBRE

El cliente no usa la palabra del catalogo. Es el caso del aparato con teclas.

**A1 · Por la FORMA.**
"un aparato rectangular con varias teclas" · "una cajita con luces" ·
"eso chato que va abajo del monitor" · "un cuadrado con un ventilador adentro"

**A2 · Por la FUNCION.**
"algo para escribir" · "con que escucho musica" · "algo para que se vea la
pantalla mas grande" · "lo que hace que ande el wifi" · "algo para guardar
archivos"

**A3 · Por la PARTE o el lugar del cuerpo.**
"eso que se pone en la oreja" · "lo que se agarra con la mano y mueve la
flechita" · "el cable ese que va a la tele" · "lo que se enchufa en el USB"

**A4 · Por el EFECTO que busca.**
"algo para que no se me cansen las manos" · "algo para que no se escuche el
ruido de afuera" · "algo para que la compu no se ponga lenta" · "algo para
que no se me caiga la senal"

**A5 · HIPERONIMO vago.**
"un aparato" · "una cosa" · "un dispositivo" · "un chirimbolo" · "un
adminiculo"

**A6 · METONIMIA de marca.**
"un logitech" · "unos redragon" · "quiero un JBL" — la marca usada como si
fuera la categoria.

**A7 · EXTRANJERISMO o calco.**
"un keyboard" · "un headset" · "unos earbuds" · "un mouse pad" · "una
webcam" · "un pendrive"

**A8 · REGIONALISMO y sinonimo rioplatense.**
"computadora" vs "ordenador" · "celular" vs "movil" · "notebook" vs "laptop"
vs "portatil" · "memoria" vs "pendrive" vs "USB" · "parlantes" vs "bafles"
vs "altavoces" · "auriculares" vs "audifonos" vs "cascos"

**A9 · Por QUIEN lo usa.**
"lo que usan los gamers" · "lo que se usa en oficina" · "algo de streamer" ·
"lo que usan para editar video"

**A10 · Por COMPARACION con algo que tiene.**
"algo como el que tenia" · "parecido a este pero mas nuevo" · "lo mismo que
compre la vez pasada" · "igual al de mi hermano"

**A11 · ANAFORA — el referente esta en la charla.**
"ese" · "el anterior" · "el que me mostraste" · "el segundo de la lista" ·
"el de 50 mil" · "los dos primeros"

**A12 · NOMBRE PARCIAL o mal escrito.**
"k 120" · "la g15" · "el dx110" · "logitec" · "redagron" — borde con FUENTE:
lo resuelve el rescate por cercania, pero el modelo tiene que DECIDIR que es
un intento de nombre y no una categoria.

---

## EJE B · UBICARSE EN UNA ESCALA

El cliente no dice "ordename por precio". Dice donde quiere estar parado.
**Este eje es el mas grande y el mejor medido: `barrido_orden` ya tiene el
bloque duro en 59 de 59.**

**B1 · SUPERLATIVO directo.**
"el mas barato" · "el mas caro" · "el mas liviano" · "el que mas dura"

**B2 · SUPERLATIVO con rodeo.**
"el de menor precio" · "el de precio mas accesible" · "el que mejor precio
tenga" · "el de mas bajo precio" · "la mas economica"

**B3 · NEGACION DEL EXTREMO OPUESTO.**
"que no sea caro" · "nada caro" · "que no salga tanto" · "sin que sea caro" ·
"que no sea una locura"

**B4 · ATENUADO.**
"no muy caro" · "que no sea tan caro" · "algo moderado" · "nada del otro
mundo"

**B5 · CIRCUNSTANCIA como grado — el caso "crisis".**
"dada la crisis" · "ando corto" · "estoy justo de plata" · "sin gastar una
fortuna" · "algo acorde a los tiempos" · "para el bolsillo de hoy" ·
"estamos complicados"

**B6 · RANGO VAGO / gama.**
"gama media" · "ni lo mas barato ni lo mas caro" · "algo del medio" · "gama
baja" · "algo de entrada" · "lo mas top"

**B7 · UMBRAL numerico.**
"hasta 50 mil" · "menos de 100 lucas" · "de 50 a 80" · "que no pase de 200"

**B8 · RELATIVO a un referente.**
"mas barato que ese" · "el doble de memoria que este" · "algo un poco mejor
que el que vi" · "la mitad de lo que sale ese"

**B9 · RELACION calidad-precio.**
"el que mas conviene" · "buena relacion precio calidad" · "el que mejor
rinde por lo que sale" · "lo que mas me rinda"

**B10 · ESCALA NO MONETARIA.**
"el mas liviano" · "el mas silencioso" · "el mas resistente" · "el mas
comodo" · "el que menos consume" · "el que mas dura la bateria"

**B11 · ESCALA SOCIAL.**
"el mas vendido" · "el que mas se lleva" · "el que recomiendan" · "el que
mejor lo califican" · "el que usa todo el mundo"

**B12 · ESCALA TEMPORAL.**
"el mas nuevo" · "el ultimo modelo" · "lo que acaba de salir" · "nada viejo"

**B13 · CALIDAD sin eje.**
"que sea bueno" · "de calidad" · "que no sea berreta" · "que sea decente" ·
"nada trucho"

**OJO CON B9, B11, B13, y parte de B6 y B10.** La fuente de hoy tiene TRES
campos ordenables —`precio_ars`, `peso_gramos`, `garantia_meses`— y sobre lo
demas ordenar no significa nada. **Esas frases no se pueden cumplir y la
respuesta correcta es decirlo.** Es el bloque blando del D16, 28 frases, que
PENDIENTE tiene en ESPERA A MARTIN: no es codigo, es decidir que campo
normalizado se agrega a la fuente.

---

## EJE C · PONER UNA CONDICION QUE NO ES UN VALOR

Es el borde con FUENTE. El valor puede salir del catalogo; lo que es criterio
es **que clase de condicion** es.

**C1 · DURA afirmativa.** "tiene que ser inalambrico" · "si o si negro"
**C2 · DURA negativa.** "que no sea chino" · "nada de plastico"
**C3 · BLANDA, preferencia.** "preferentemente Logitech" · "ojala negro" ·
"si se puede, con cable"
**C4 · GRADO sobre una condicion.** "las menos partes chinas posibles" ·
"lo mas nacional que se pueda" — **es el caso medido de M1 y el que distingue
FILTRAR de ORDENAR.**
**C5 · EXCLUSION de un conjunto.** "cualquiera menos Redragon" · "todo menos
los chinos"
**C6 · DOS EJES EN TENSION.** "bueno pero barato" · "chico pero potente" ·
"que dure y que no salga mucho"
**C7 · CONDICIONAL.** "si no hay negro, blanco" · "si no tenes ese, algo
parecido"
**C8 · TOLERANCIA / minimo.** "que tenga al menos 8 de RAM" · "de 16 para
arriba"
**C9 · COMPATIBILIDAD.** "que ande con mi PS5" · "que entre en esta mother" ·
"que sirva para Mac"
**C10 · IMPLICITA por contexto.** "para mi hijo de 8 anos" · "para mi mama
que no sabe de tecnologia" · "para un departamento chico"

---

## EJE D · DECIR PARA QUE, Y QUE ESO SEA EL CRITERIO

El cliente no describe el producto. Describe su vida.

**D1 · ACTIVIDAD.** "para jugar" · "para editar video" · "para estudiar" ·
"para laburar de casa" · "para disenar"
**D2 · INTENSIDAD o duracion.** "para escribir mucho todos los dias" · "para
usarlo ocho horas" · "para un uso liviano"
**D3 · AMBIENTE.** "para la oficina" · "para llevar de viaje" · "para el
gimnasio" · "para afuera, que llueve"
**D4 · PERSONA destinataria.** "para un chico" · "para regalo" · "para
alguien grande"
**D5 · PROBLEMA a resolver.** "se me traba la compu" · "me duele la muneca" ·
"se me llena la memoria" · "no me anda el sonido"

---

## EJE E · CANTIDAD QUE HAY QUE DEDUCIR

**E1 · DIRECTA.** "dos teclados"
**E2 · TOTAL con resto implicito.** "7 articulos: 2 notebooks, 1 microfono y
los demas serian memorias" — **es M6, medido, y sale bien.**
**E3 · POR PRESUPUESTO.** "lo que entre en 200 mil" · "armame algo con 150"
**E4 · DISTRIBUTIVA.** "uno para cada uno" · "tres de cada" · "la mitad de
cada cosa"
**E5 · COMPARATIVA con lo anterior.** "el doble de lo que pedi" · "lo mismo
pero para dos"
**E6 · REPARTO del pago.** "divide en setenta treinta" · "mitad y mitad" ·
"una parte ahora y una despues" — **medido, M1.**

---

## EJE F · LA PREMISA QUE TRAE EL CLIENTE

**Este eje sale de la literatura de tip-of-the-tongue y NO lo teniamos.**
El cliente no solo pide: afirma, duda, se equivoca.

**F1 · DUDA DECLARADA.** "creo que se llama asi" · "no se si es ese el
nombre" · "algo asi como K120, no me acuerdo bien"
**F2 · PREMISA FALSA.** "el K120 inalambrico" cuando es con cable · "el que
tiene 16 de RAM" cuando tiene 8 · "ese que estaba en oferta" cuando no
estaba. **Es el mas peligroso para un bot de venta: aceptar la premisa es
mentir con las palabras del cliente.** El repo ya lo tiene como clase,
`dato_falso_inducido`.
**F3 · META-COMENTARIO sobre lo que ya intento.** "ya busque y no encontre" ·
"en la pagina no aparece" · "me dijeron que tenian"
**F4 · CORRECCION a mitad de mensaje.** "dame 3... no, mejor 4" · "el negro,
perdon, el blanco"
**F5 · CONTRADICCION interna.** "el mas barato pero que sea de marca" · "que
no pase de 50 mil, mandame la gama alta"
**F6 · URGENCIA o plazo como condicion.** "lo necesito para manana" · "si no
llega el viernes no me sirve"

---

## EJE G · LA FORMA DEL MENSAJE — ortogonal, multiplica todo

No es una clase de contenido. Es **como llega**, y cada una de las de arriba
puede llegar de cualquiera de estas formas.

**G1 · MULTIPREGUNTA encadenada.** Dos o mas ejes en un solo mensaje. Es el
caso que este proyecto esta midiendo.
**G2 · DESPROLIJO.** Sin puntuacion, con typos, todo en minuscula.
**G3 · AUDIO TRANSCRIPTO.** Muletillas y repeticiones: "pasame ee de acuerdo
a la crisis el presupuesto". **Es literal de M6.**
**G4 · CON RUIDO irrelevante.** Saludo largo, contexto personal, chiste.
**G5 · EN VARIOS MENSAJES cortos seguidos.**
**G6 · CON EMOJIS o abreviaturas.** "xfa", "q", "tmb", "salu2"

---

## 1. EL NUMERO, PARA QUE NO SE DISCUTA DE MEMORIA

    EJE A  nombrar sin el nombre        12 clases
    EJE B  ubicarse en una escala       13 clases
    EJE C  condicion que no es un valor 10 clases
    EJE D  decir para que                5 clases
    EJE E  cantidad a deducir            6 clases
    EJE F  la premisa del cliente        6 clases
    ───────────────────────────────────────────
           CRITERIO                     52 clases
    EJE G  forma del mensaje             6, y multiplican

**Lo que el repo ya cubre bien:** casi todo el eje B duro, E2, E6, C4.
**Lo que esta medido y falla:** nada del eje B duro.
**Lo que NO tiene mecanismo:** el eje D entero, A4, A9, B9, B11, B13, C6,
C10, F2, F3.

---

## 2. LO QUE ESTE ESTUDIO NO DECIDE

No dice que forma tiene el indice. No dice si esto va a enum, a texto libre o
a `anyOf`. **Esa es la ficha siguiente y se decide con esta lista sobre la
mesa**, que es lo que Martin pidio: primero abarcar, despues elegir.

Y no cubre el otro estudio, el de lo que SI resuelve una busqueda contra la
fuente. Ese es aparte y viene despues.

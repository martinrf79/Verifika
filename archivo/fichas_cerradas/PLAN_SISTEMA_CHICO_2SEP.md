# PLAN — EL SISTEMA CHICO. Diagnostico medido y tres caminos.

Autocontenido. Escrito para que lo ejecute cualquier modelo capaz de programar
—Claude Code, Opus, Grok, Cursor— sin leer ninguna conversacion previa.
Fecha: 2-sep-2026. Repo: github.com/martinrf79/Verifika, rama main.

Leer antes de tocar nada: `CLAUDE.md`. Este archivo reemplaza a
`arquitectura/BRIEF_MOTOR_V2.md` como unidad de trabajo: el brief acerto el
diagnostico del reparto invertido y la vara por capa, y este plan lo continua
con lo que se midio despues. Lo que el brief no vio esta en la seccion 2.

TODO NUMERO DE ESTE ARCHIVO SE MIDIO EL 2-SEP-2026 CONTRA EL ARBOL DE MAIN.
Ninguno es una estimacion. Si al leerlo un numero no coincide, gana el repo y
se corrige este archivo el mismo dia.

---

## 0. LA CONCLUSION, EN SEIS LINEAS

1. El error es de cableado y esta localizado. No es el modelo.
2. El sistema no se termina porque la vara no puede medir si termina.
3. El sistema no se achica porque cada alucinacion agrego una guardia, y
   vigilar prosa libre no tiene fondo: es una cinta sin final por construccion.
4. La salida no es una guardia mejor. Es que la segunda llamada deje de
   devolver prosa libre.
5. Eso saca unas 6.000 lineas de `app/` de un movimiento, sin borrar una sola
   regla de negocio, porque las reglas dejan de ser guardias y pasan a ser la
   forma del formulario.
6. Hay un avance de este año que lo hace posible y antes no estaba: JSON Schema
   completo en la salida del modelo.

---

## 1. EL CABLEADO, MEDIDO

### 1.1 El defecto que explica la pregunta que nunca se contesto bien — YA ARREGLADO

`app/core/herramientas.py`, `contexto_json`. Es lo UNICO que la llamada dos ve
del mundo real. Terminaba en `json.dumps(...)[:14000]`: rebanado por CARACTER.

Medido con el catalogo real de `verifika_prod`:

```
1 herramienta    3.620 caracteres   entra entero
2 herramientas   7.328              entra entero
3 herramientas  11.643              entra entero
4 herramientas  11.787              entra entero
5 herramientas  17.061 ->  14.000   CORTADO A MITAD DE PALABRA
```

Con cinco herramientas el modelo recibia, literal, `... por defectos de
fabricacion,` y ahi se terminaba el archivo. JSON invalido, una llave sin
cerrar, un producto entero desaparecido y nada que lo dijera.

**Cinco herramientas es exactamente lo que dispara una pregunta de dificultad
media-alta.** La pregunta simple anda; la compleja llega rota. De ahi salio,
durante meses, la conclusion de que el modelo chico no daba.

Arreglado en el commit `5ed1f1e`: se recorta por ITEM, ninguna herramienta
desaparece, lo recortado se declara con `recortado: {campo, mostrados, de}` y la
instruccion de preguntar en vez de completar, y nunca sale JSON invalido. Vara
en `tests/test_el_redactor_recibe_json_entero.py`, ocho tests. Los turnos de una
a cuatro herramientas salen byte por byte iguales que antes.

### 1.2 Lo que hace que el recorte no haga falta nunca — ABIERTO

El payload se arma con TODOS los campos de TODOS los productos, sin mirar que
pregunto el cliente. Peso de las cinco categorias, 17.061 caracteres:

```
specs                  4.576   26,8%
descripcion            2.278   13,4%   <- no aporta una palabra que no este en otro campo
sirve_para             1.326    7,8%
garantia_detalle       1.156    6,8%
origen                   703    4,1%
```

Proyectado a lo que pide un precio —`id`, `nombre`, `precio`, `stock`— el mismo
turno pesa **3.830 caracteres y entran los 12 productos enteros**, contra 8 de
12 con el recorte de hoy. Con una spec pedida, 4.100. Con garantia y origen
encima, 5.689. Todos entran holgados.

El resolver YA sabe que se pregunto: tiene `declarado` y los puntos del indice.
Nadie usa eso para elegir los campos. Es un caso de manual de lo que la
literatura de este año llama context confusion: material superfluo que empuja al
modelo a la decision equivocada.

### 1.3 El reparto invertido, contado en piezas

Entre la segunda llamada al modelo y el `return texto` corren **23 piezas a
nivel puerta y 46 mutadores contando los internos**. Todas reescriben prosa que
el modelo ya escribio.

Dos de ellas hacen lo contrario entre si sobre el mismo bloque:
`mensaje.sin_cuenta_que_no_cambio`, en `app/core/mensaje.py:782`, resume la
cuenta a una linea; `salida.asegurar_cuenta_si_abrio`, en
`app/core/salida.py:1609`, la repone entera. Corren una despues de la otra en el
mismo turno.

Y el codigo calcula `idx.puntos` —que pregunto el cliente y que material hay
para cada cosa— y **no se lo pasa al modelo como dato**: le manda una
instruccion en prosa al final del prompt, y despues intenta reponer los puntos
faltantes con cirugia de strings sobre la prosa que volvio, en
`salida._punto_omitido_repuesto`, `app/core/salida.py:1262`.

Eso es el nudo. El codigo sabe la respuesta correcta ANTES de preguntar, no se
la da al modelo, y despues parchea el texto para que se parezca a lo que sabia.

### 1.4 El silencio

`app/verifika/grafo.py:801`, funcion `paso`: **cualquier excepcion de
cualquiera de las 17 piezas de las cuatro puertas se atrapa ahi y devuelve el
texto tal como entro**, marcando `levanto:<Tipo>`. Una pieza rota no aparece
como error en ningun log. Aparece como un turno que salio raro.

En el camino vivo hay **72 bloques `except Exception` que atrapan y siguen**.
Los que pierden dato sin decirlo, por orden de costo:

```
hub_venta.py:1405   falla save_conversation -> se pierde TODA la memoria del turno, el texto sale igual
hub_venta.py:978    falla procesar_mensaje_para_lead -> el lead no se crea y el turno sigue normal
hub_venta.py:474    falla certificar_ids -> el resultado se anexa SIN certificar
resolver.py:144     lo mismo, y sin log
hub_venta.py:937    falla el extractor -> se pierden nombre, telefono y direccion
leads.py:168        una consulta fallida devuelve None y el codigo lo lee como "no hay lead"
herramientas.py:1945 se pierde el envio de un destino y la cuenta se arma sin ese costo
calculadora.py:894  se pierden las tarifas de Firestore y cae al mapa del codigo
atadura_prosa.py:233 la atadura entera se anula: las afirmaciones salen sin verificar
orchestrator.py:63  dice "conversacion reiniciada" aunque el reset haya fallado
```

Los ultimos dos son de la familia que el proyecto entero existe para evitar: el
sistema afirma algo que no es cierto.

### 1.5 La maraña

- **200 imports perezosos** en `app/`, 180 de ellos de `app.*`.
- **16 ciclos de import reales**. Los mas apretados: `salida` con `hub_venta`,
  `mensaje` con `salida`, y `guia_venta_prosa` con `contexto_turno` con
  `app.config`, este ultimo con dos de sus tres aristas estaticas.
- Los perezosos son la consecuencia del ciclo, y a la vez lo esconden.
- **16 copias de la misma funcion `_norm`**, en cinco variantes incompatibles
  entre si. Tres normalizan distinto por un `.strip()`.
- **Dos extractores de numeros corren sobre el mismo texto en la misma puerta
  con canonicalizacion contradictoria**: `atadura_prosa._numeros` distingue 19.5
  de 195; `herramientas._montos_del_texto` los colapsa al mismo numero.
- **Cinco definiciones distintas** de "hay un total en el texto".
- Inversion de capa: `app/storage/firestore_client.py:143` importa
  `app.core.fuente_producto`.

### 1.6 Por que el trabajo no termina nunca: la vara no puede medirlo

Esto es lo mas caro de todo el diagnostico, y no es una opinion.

```
app/         22.061 lineas    51 archivos
tests/       36.984 lineas   101 archivos, 1.209 tests, todos verdes
```

De 966 definiciones de test:

- **120 no miran nunca lo que recibe el cliente.** Son candados sobre archivos
  `.md`, sobre el hook de arranque de git, sobre el guard de ramas, sobre el
  propio arnes de pruebas. El test mas lento de toda la bateria, 10,71
  segundos, verifica que `INVENTARIO_BARRIDO.md` coincida con el codigo.
- **14 asserts en todo el repo afirman que el bot contesto lo que le
  preguntaron.** Son los 14 grupos `contiene:` de los guiones. Todo lo demas
  afirma que algo no pasa, o afirma sobre estructuras internas.
- De los 55 turnos grabados, **20 tienen alguna expectativa escrita**. Los otros
  35 se puntuan solo por no mentir, no estar vacios y no repetir.

**Los casetes son un circuito cerrado.** `grabar_casetes.py:252` calcula el piso
reproduciendo los casetes recien grabados; `test_charlas_grabadas.py:170` exige
que ese numero no baje. La salida grabada del modelo produce el numero, y el
test exige que el numero no baje. Si el modelo dijo algo mal y ninguno de los
cuatro criterios lo caza, el error queda ADENTRO del piso, consagrado. El repo
ya lo tiene escrito con todas las letras en `tests/oro/README.md:4`.

**Y `tests/oro` acepta 14 casos rojos.** `banco_pruebas/oro_piso.json`:

```
capa2: 32 de 40      8 rojos aceptados
capa4:  4 de 10      6 rojos aceptados   <- la compuerta, al 40%
capa5: 15 de 15
```

`test_oro.py:38` pide `>= piso`, asi que el CI da verde con la compuerta contra
datos inventados fallando 6 de cada 10 casos.

Resumen de esta seccion en una frase: **hay 37.000 lineas de test que no pueden
bajar y que casi no miden si el bot vende.** Trabajar contra eso no es dificil,
es imposible por diseño. No es falta de esfuerzo ni de constancia.

---

## 2. LO QUE EL BRIEF V2 NO VIO

`BRIEF_MOTOR_V2.md` acierta en casi todo: el reparto esta invertido, no se
recorta pieza por pieza, se escribe un `turno.py` que reemplaza al viejo, la
vara es por capa con casos de oro escritos a mano. Todo eso se conserva.

Pero mantiene la premisa que hace infinito el trabajo: **la llamada tres
devuelve PROSA, y despues una compuerta la juzga.**

Mientras el modelo devuelva prosa libre:

- La compuerta tiene que entender castellano para juzgarla.
- Cada alucinacion nueva es una forma de castellano que la compuerta no
  contemplaba, o sea una guardia nueva.
- Asi se llego de 4 nodos a 18 y de 18 a 46 mutadores. El brief propone volver a
  1. Con prosa libre del otro lado, vuelve a subir.
- Y ya hay evidencia de que no aguanta: la capa 4 de `tests/oro` esta en 4 de 10
  ANTES de ser la unica defensa.

La compuerta boolena por oracion del brief es la misma apuesta que ya se hizo
tres veces, mas chica. Mas chica dura mas, pero termina igual.

---

## 3. LA SALIDA: LA SEGUNDA LLAMADA NO DEVUELVE PROSA, DEVUELVE UN FORMULARIO

### 3.1 La idea, en una linea

El modelo no escribe el mensaje. **Llena un formulario con una casilla por
punto**, y el codigo arma el mensaje con eso.

### 3.2 Por que ahora si y antes no

Gemini agrego este año soporte de JSON Schema completo en la salida, en todos
los modelos activos: `anyOf` para uniones, `$ref` para esquemas recursivos,
`minimum` y `maximum`, `additionalProperties`, `prefixItems`, y orden de
propiedades preservado desde Gemini 2.5 en adelante, incluida la capa de
compatibilidad con la API de OpenAI, que es justo la que usa
`hub_venta._cliente`. O sea: **se puede exigir la forma de la respuesta y
recibirla garantizada**, sin pedirsela por prosa y sin rezar.

Cuando se diseño esta arquitectura eso no estaba disponible. Es el avance
concreto que cambia el juego, y es el unico de esta lista que hay que aplicar si
o si.

### 3.3 El esquema

```json
{
  "puntos": [
    {
      "punto_id": "p3",
      "estado": "contestado | no_se_sabe | ambiguo",
      "texto": "prosa SOLO de este punto, sin numeros de plata",
      "fuente_ids": ["MOU0023"]
    }
  ],
  "pregunta_final": "una sola, o null"
}
```

Reglas de negocio que dejan de ser guardias y pasan a ser la FORMA:

| regla de hoy | pieza que la vigila | como queda |
|---|---|---|
| no inventar plata | `sin_plata_inventada`, `_la_cuenta_y_la_plata`, `_cuenta_no_retipeada`, `plata_inventada`, `montos_respaldados` | el esquema no tiene casilla para plata. El bloque sellado lo pega el codigo. **Imposible por construccion** |
| toda afirmacion atada a su fuente | `atadura_prosa` entero, 472 lineas | `fuente_ids` es campo obligatorio. El codigo verifica que existan en `material`. **10 lineas** |
| contestar todos los puntos | `_punto_omitido_repuesto`, `indice_turno` | hay una casilla por punto y el esquema las exige todas. Casilla vacia = pregunta que escribe el codigo. **Imposible omitir** |
| una sola pregunta | `mensaje.una_sola_pregunta` | `pregunta_final` es un campo, no una lista. **Imposible** |
| no repetir | 13 reglas de `mensaje.componer` | el codigo arma el mensaje desde las casillas: no puede pegar dos veces lo mismo. **Casi todas sobran** |
| ante ambiguo, preguntar | regla cero, hoy por prompt | `estado: ambiguo` es un valor del enum, y el codigo lo convierte en pregunta. **Determinista** |
| no hablar de la maquina | `sin_narracion_interna`, ciega segun ficha 27 | el texto de cada punto es corto y de un solo tema; la narracion interna no tiene donde caer |

### 3.4 Que se borra, medido en lineas de hoy

```
salida.py           1.650
indice_turno.py     1.738
mensaje.py          1.255
hub_venta.py        1.472   (lo reemplaza turno.py, ~600)
grafo.py              810   (la medicion se muda a banco_pruebas/, offline)
atadura_prosa.py      472   (quedan ~10 lineas dentro de turno.py)
invariantes.py         45
                   ------
                    7.442 lineas fuera de app/, contra ~600 que entran
```

`app/` pasa de 22.061 a alrededor de **12.000 lineas**. No llega al 7.306 del
termometro de la ficha 36, y eso hay que decirlo asi: llegar a 7.306 exige
tocar la calculadora, la certificacion o el contrato, y la prioridad uno manda
que no se fuercen. **12.000 con el reparto derecho vale mas que 7.306 con el
reparto invertido.**

Lo que se queda intacto, porque es determinista y esta probado: `herramientas`,
`filtros_catalogo`, `calculadora`, `envio`, `geo_cp`, `estado_venta`, `leads`,
`pago`, `cierre`, `compatibilidad`, `fuente_producto`, `firestore_client`.

---

## 4. TRES CAMINOS. HAY QUE ELEGIR UNO, Y SE PUEDEN COMBINAR

### Opcion A — El formulario. RECOMENDADA

Lo de la seccion 3. La llamada dos devuelve JSON con esquema estricto y el
codigo arma la prosa.

- A favor: cierra la cinta sin final. Las reglas dejan de poder violarse en vez
  de ser vigiladas. Saca 7.400 lineas. Es el diferenciador comercial de verdad:
  no "tenemos guardias contra la alucinacion" sino "el modelo no tiene donde
  escribir un precio".
- En contra: la prosa la arma el codigo, asi que suena mas armada. Se compensa
  dejando que el modelo escriba el texto DE CADA PUNTO, que es donde esta el
  matiz, y el codigo solo ordena y pega.
- Riesgo real: que el esquema quede corto para algun caso y haya que agregarle
  un campo. Eso es un commit, no una guardia.

### Opcion B — El brief V2 tal cual

Prosa libre y una compuerta booleana por oracion.

- A favor: menos cambio conceptual, ya esta escrito y decidido.
- En contra: la compuerta de hoy mide 4 de 10 en `tests/oro`. Es la misma
  apuesta que ya fallo tres veces, mas chica.
- Cuando conviene: si se quiere el recorte de tamaño YA y se acepta seguir
  agregando guardias.

### Opcion C — Sin segunda llamada cuando no hace falta

Cuando `material` cubre todos los puntos y no hay ambiguedad, el codigo arma la
respuesta con plantillas y no llama al modelo por segunda vez.

- A favor: la mitad de los turnos sale gratis, instantanea y con cero
  alucinacion posible. Y la clave paga rinde el doble.
- En contra: prosa mas rigida en esos turnos.
- **C es gratis si se hace A**, porque el renderizador es el mismo: si todas las
  casillas se pueden llenar con `material` sin razonamiento, no se llama.
- Primer paso, barato y sin escribir codigo nuevo: contar sobre los 55 turnos
  grabados cuantos califican. Ese numero decide si C vale la pena.

**Recomendacion: A, y C sale de arriba.** B solo si se quiere el recorte antes
que el arreglo.

---

## 5. LA VARA, QUE ES LA MITAD DEL PROBLEMA

Nada de la seccion 4 sirve si la vara sigue siendo la de hoy. Cuatro cambios,
en este orden, y los tres primeros son gratis.

1. **`tests/oro` deja de aceptar rojos.** `oro_piso.json` pasa a exigir el total
   de cada capa. Los 14 rojos se convierten en la lista de trabajo real, en el
   orden en que estan. Es un commit de umbral, propio y anterior al trabajo,
   como manda la regla 1 de `ARRANQUE.md`.
2. **Los casetes dejan de ser vara.** Quedan solo para que la bateria offline
   pueda correr el turno sin clave, que es lo que el propio brief ya decidio.
   `test_charlas_grabadas.py::test_el_numero_no_baja` se saca o se marca como lo
   que es: una medicion de regresion, no un objetivo.
3. **Los 120 candados de proceso se mudan a una bateria aparte**, que corre en
   el CI y no en cada cambio. Hoy son el 76% de los 208 segundos y el primer
   ruido que ve cualquier sesion nueva. No se borran: se sacan del camino.
4. **La vara del vivo pasa a ser pass^k, no promedio.** pass^k cuenta un caso
   como resuelto solo si las k corridas independientes salen bien. Un bot que
   acierta 8 de 10 se ve fuerte en promedio y se cae en pass^k, porque el
   cliente de WhatsApp no reintenta. Con tres repeticiones, que es lo que el
   brief ya pide, sale gratis: se cambia el promedio por el peor caso, que es lo
   que el brief llamaba PEOR CASO. Es la misma idea con el nombre que tiene
   afuera y con la literatura detras.

---

## 6. ORDEN DE EJECUCION

Una ficha, una sesion, un commit. Se trabaja en `main`, sin ramas. El push se
consulta una vez al final porque deploya. Ningun flag apagado.

```
HECHO  0.  contexto_json deja de cortar por caracter.        commit 5ed1f1e
       1.  oro_piso.json exige el total de cada capa.        1 commit, gratis
           Queda rojo. Es la lista real de trabajo.
       2.  El payload se proyecta por la pregunta:           1 commit
           el resolver elige los campos con `declarado`.
           Vara: las cinco categorias entran enteras
           en menos de 6.000 caracteres, 12 de 12.
       3.  Los 6 rojos de la capa 4 y los 8 de la capa 2,    1 commit por capa
           en el orden en que estan. Sin tocar la vara.
       4.  turno.py con el esquema de la seccion 3.          1 commit
           orchestrator apunta a turno.procesar_turno.
           salida, indice_turno, mensaje, hub_venta, grafo,
           atadura_prosa e invariantes van a archivo/
           con su fila en archivo/README.md.
       5.  pytest verde. Vivo con clave paga, 3 corridas,    1 commit
           manda pass^k. Si no iguala al hub viejo medido
           el mismo dia: git revert del commit 4.
       6.  Modo lead_fuerte y modo cierre por tienda.        1 commit
       7.  Tienda cero de otro rubro. El semaforo.           1 commit
```

Los pasos 1, 2 y 3 no tocan el camino vivo y valen igual si al final se elige la
opcion B. **Se pueden hacer sin decidir nada.**

Como se vuelve atras del paso 4: `git revert` de ese commit devuelve el hub
viejo entero.

---

## 7. QUE HACE UN AGENTE ACA, Y QUE NO

Aplica en un solo lugar, y es el que estaba trabado:

**Los casos de oro.** Hacen falta 40 por capa, con la entrada y la salida
correctas escritas a mano, y `ARRANQUE.md` manda que el que implementa no
escriba la vara. Un agente genera los casos desde las 40 preguntas reales y
`CONSIGNA_PREGUNTAS_REALES.md`; **otro agente distinto, que no vio como se
generaron, los verifica**; Martin revisa la lista final, que es corta. Asi la
regla de que el implementador no toca la vara deja de depender de la disciplina
de la sesion y pasa a estar en la mecanica.

Tambien aplica para el barrido de las miles de preguntas de ecommerce de
dificultad media-alta: generarlas, correrlas contra las capas 2, 4 y 5 —que son
offline y gratis— y quedarse solo con las que rompen algo.

**Donde NO aplica:** en escribir el turno nuevo. Eso es una pieza sola, chica y
con contrato claro; repartirla entre agentes es exactamente como se llego a los
telefonos descompuestos.

---

## 8. LO QUE NO SE TOCA

- Mercado Pago y el CBU estan resueltos: link de demo. Regla 6 de `CLAUDE.md`.
- La clave paga no se pide para grabar casetes. Regla 4.
- El bot pide el nombre y nada mas.
- `data/clientes/` no se toca sin permiso.
- No se borra nada: lo apagado va a `archivo/`, lo reenchufable a `reserva/`.

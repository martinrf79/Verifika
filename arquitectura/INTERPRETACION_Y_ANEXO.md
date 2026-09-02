# LA INTERPRETACION HOY, Y EL ANEXO CON LA RESPUESTA

Autocontenido. Lo ejecuta cualquier modelo capaz de programar sin leer ninguna
conversacion previa. Fecha: 2-sep-2026. Repo: github.com/martinrf79/Verifika.

Todo numero de este archivo se midio contra el arbol de main el 2-sep. Ninguno
es estimacion. Si uno no coincide, gana el repo.

---

## 1. COMO FUNCIONA LA INTERPRETACION HOY, EN DETALLE

### 1.1 Lo que el modelo ve

Una sola llamada. Una sola herramienta visible: `registrar_pedido`
(`herramientas.py:736`). El esquema se genera por turno en
`herramientas.py:739` y pesa **5.938 caracteres**, que viajan en cada mensaje.

Parametros de la llamada, en `hub_venta.py:389`: `temperature=0.0`,
`tool_choice="auto"`, `max_tokens=3000`. La temperatura cero esta bien y esta
justificada con medicion: elegir que declarar es traduccion, no creatividad.

La instruccion, `_INSTRUCCION_UNO` en `hub_venta.py:104`, dice cuatro cosas:
declara todo, un renglon por cada cosa preguntada, conta los items uno por uno,
y lo que no cierra va a contradicciones sin resolverlo.

### 1.2 El molde: diez campos, ninguno obligatorio

```
items            list[ItemDeclarado]   que, categoria, cantidad, destino
restricciones    list[str]             toda condicion y todo extremo, tal cual
destinos         list[str]             localidades de envio
pide_precio      bool                  espera un numero
contradicciones  list[str]             lo que no cierra
reparto_pago     list[PartePago]       la division del pago en numeros
atributos        list[AtributoDeclarado]  de, campo
stock            list[str]             sobre que pregunto si lo tenemos
compatibilidad   list[CompatibilidadDeclarada]  que, para
temas            list[str]             lo que contesta la casa, y la situacion
```

Dos enums salen de la fuente viva, no del codigo:
- `items[].categoria`: los 22 rubros del catalogo. El modelo no puede nombrar un
  rubro que no vendemos.
- `atributos[].campo`: los campos filtrables mas una escapatoria, `SIN_CAMPO`.
  La escapatoria esta bien pensada y esta documentada en `herramientas.py:759`:
  un enum cerrado sin salida no previene el invento, lo fabrica.

### 1.3 Esta parte esta bien, y hay que decirlo

El diseño es correcto: separar DECLARAR de BUSCAR, y que el codigo derive. La
medicion que quedo escrita en `herramientas.py:400`:

```
ENTIENDE el mensaje    interprete viejo 69    el de hoy 91
```

y sobre todo, el de hoy da exactamente 91 en las cinco redacciones, mientras el
viejo iba de 45 a 82 segun como estuviera escrito el mensaje. **Es estable.** La
inestabilidad era el problema y ya se resolvio.

**Conclusion de esta seccion: el modelo entiende. No es ahi donde esta el cuello
de botella.**

---

## 2. DONDE ESTA EL CUELLO: LA DERIVACION ENTIENDE MENOS QUE EL MOLDE

### 2.1 La prueba, y no admite discusion

`tests/oro/capa2` tiene 40 casos donde **la entrada es el declarado CORRECTO
escrito a mano**. No hay modelo en el medio. Se corre con
`python3 banco_pruebas/oro.py`, offline y gratis.

**Con la interpretacion perfecta, la capa 2 da 32 de 40.** Ocho casos no llegan
a tener material, y el modelo no tuvo nada que ver:

```
C2-S04  los dos extremos de toda la tienda en un turno
        no salio NOT0160, no salio MOU0023, dos restricciones sin material
C2-S05  el comparativo contra un producto nombrado
        salio como candidato el propio producto de referencia
C2-S07  la busqueda por USO, "que sirva para jugar"
        restriccion sin material
C2-S08  el pedido ABIERTO, "una PC gamer completa"
        no armo la cuenta, pide_precio sin material
C2-S13  la objecion de precio, "esta caro"
        el tema no volvio con material
C2-S17  la repregunta sobre el producto en foco, "ese"
        compatibilidad sin material
C2-E01  piden una G15 y tenemos la G16
        devolvio rubros que no son
C2-E04  el tema `defectuoso` existe con otro nombre
        volvio vacio
```

**Seis de los ocho son la misma forma**: algo declarado bien que no tiene camino
determinista hasta el material. El modelo entendio; el codigo no sabe que hacer
con lo que entendio.

### 2.2 Tres campos que el modelo llena y nadie lee

1. **`contradicciones`** — cero referencias ejecutables en `resolver.py`; las
   unicas apariciones son comentarios, lineas 639, 642 y 643. El modelo detecta
   que algo no cierra, lo declara como se le pidio, y no lo agarra nadie. Su
   unico destino es abrir un punto en `indice_turno.py:131` que despues se mide
   contra el texto.
2. **`atributos[].campo`** — la derivacion usa solo `de`, en
   `resolver.py:276-282`, y pide la **ficha entera**. El cliente pregunta cuantos
   DPI, el codigo trae los 18 campos de specs y nadie filtra por DPI. El enum con
   escapatoria, que costo diseñar, no acota nada aguas abajo.
3. **`items[].cantidad` y `items[].destino`** — no participan de ninguna
   busqueda. Solo llegan a `cotizar`.

### 2.3 Como se pierde una restriccion

Tres puertas en orden fijo, en `resolver.py:164-191`: extremo, exclusion,
inclusion. Lo que ninguna resuelve:

- **si tiene negacion, se descarta EN SILENCIO** — `resolver.py:190-191`. No va a
  `filtros`, no va a `sueltas`, y no hay log de esa rama.
- si no tiene negacion, se pega como texto a la `descripcion` de todas las
  busquedas del turno.
- **una restriccion sin ningun item que la nombre no dispara nada**: los filtros
  se calculan y no los consume nadie, porque `_buscar` solo se invoca desde los
  items, el stock y los atributos.

Y dos extremos opuestos: `orden = orden or extremo` en `resolver.py:168`. **Gana
el primero, para todo el turno.** Elegir es inventar, y ahi se elige.

### 2.4 Como se poda el material DOS veces antes de llegar

- `resolver.py:1430`: en `_bloques_a_uno` sin cuenta, a todas las busquedas menos
  la primera se les hace `pop("bloque")`.
- `resolver.py:1339-1351`: con cuenta en la mesa, de cada rubro sobrevive **una
  linea**, `f"{cat}: {hecho}"`. Se descartan nombres, precios y el resto de los
  renglones.
- `hub_venta.py:1131-1133`: si `temas` no esta en las familias abiertas, la
  llamada `consultar_temas` entera se saca de lo que ve el redactor, aunque
  `certificar_temas` la haya servido y el punto de politica siga abierto.
- `herramientas.py:1610`: `consultar_temas` corta en 6 temas.
- `herramientas.py:2583`: `contexto_json` recorta por item cuando pasa de 14.000.

### 2.5 Dos politicas opuestas ante el mismo veredicto

La regla cero dice: ante `ambiguous` el modelo esta obligado a preguntar, no a
elegir. Medido:

- **producto ambiguo FRENA** — `resolver.py:270-272`, no se trae la ficha.
- **tema ambiguo SIRVE HASTA TRES POLITICAS** — `herramientas.py:711-715`, el
  bucle corre igual para `exists` y para `ambiguous`.

Son dos politicas distintas ante el mismo veredicto, y la segunda es la causa
medida de que "dame precio de una intermedia" abra cuotas y envio al exterior.

`certificar_tema` puntua por señas, `herramientas.py:666-679`: una seña que entra
entera vale diez por su largo, una palabra propia suelta vale su cuenta, se toma
el maximo y no la suma, y si empatan dos o mas es `ambiguous`.

---

## 3. TUS TRES PUNTOS, MEDIDOS

**Calidad y cobertura del material.** Con el declarado perfecto, 8 de 40 casos
llegan a la segunda llamada sin material para al menos un punto. Y lo que si
llega viene con todos los campos de todos los productos: `specs` es el 26,8% del
peso y `descripcion` el 13,4%, y `descripcion` no aporta **una sola palabra** que
no este en otro campo. Encima el material se poda dos veces mas, en 2.4.

**El esquema que se queda corto.** No hay donde declarar un USO —"para jugar" no
es un campo del catalogo—; no hay donde declarar un PEDIDO ABIERTO —"una PC
gamer completa", donde los rubros los tiene que poner la casa—; no hay forma de
declarar una referencia anaforica —"ese"— que el codigo pueda resolver; y hay
tres campos que se declaran y no lee nadie.

**Verificacion semantica por codigo.** Existe y es buena para producto: tres
veredictos de primera clase y `ambiguous` frena. Para tema no existe: se sirven
hasta tres politicas y se sobrescribe lo que dijo el modelo en `resolver.py:325`.

Los tres puntos que marcaste estan medidos y los tres dan lo que vos decias.

---

## 4. EL ESLABON QUE FALTA, Y ES UNO SOLO

El codigo YA calcula lo que hace falta. `indice_turno.puntos`, linea 101, abre un
punto por cada cosa declarada, con su tipo, su texto y si esta cubierto. Corre en
cada turno.

**Y no se le pasa al modelo.**

Lo unico que viaja a la segunda llamada, en `hub_venta.py:496` y `:501`:

1. `H.contexto_json(llamadas)` — el volcado crudo de las herramientas, sin
   ninguna relacion con los puntos.
2. `obligacion` — una instruccion en prosa al final: *"Tu mensaje NO le contesta
   esto, que el cliente si pidio. Agregalo"*, generada en `indice_turno.py:1695`.

Y despues, cuando el texto vuelve, `salida._punto_omitido_repuesto`, linea 1262,
intenta REPONER con cirugia de strings el punto que faltaba.

O sea: **el codigo sabe punto por punto que pregunto el cliente y que material
tiene para cada uno, le manda al modelo un volcado sin esa estructura mas un
reto en prosa, y despues le parchea el texto.** El modelo tiene que reconstruir
solo la correspondencia entre pregunta y evidencia, desde un JSON de
herramientas.

Eso es el cableado. No es una metafora: es una estructura calculada que no se
enchufa.

---

## 5. EL ANEXO. UNA SOLA COSA

Que el material de la segunda llamada SEA la tabla de puntos, no el volcado.

```json
{"puntos": [
  {"id": "items:1",
   "pregunto": "un mouse inalambrico barato",
   "estado": "con_material",
   "material": [{"id": "MOU0023", "nombre": "Genius DX-110",
                 "precio": "$8.500", "stock": 12}]},
  {"id": "restricciones:2",
   "pregunto": "que sirva para jugar",
   "estado": "sin_material",
   "material": []},
  {"id": "pide_precio:1",
   "estado": "sellado",
   "bloque": "Mouse Genius DX-110 x1 ... Total: $8.500"}
]}
```

Tres estados y nada mas: `con_material`, `sin_material`, `sellado`. El bloque
sellado se pega tal cual; lo demas se redacta.

Que resuelve de un saque:

- **El modelo ve la pregunta al lado de su evidencia.** Eso es lo que hace
  posible el razonamiento. Hoy tiene que aparearlas el, desde un volcado.
- **Un punto sin material es un DATO VISIBLE**, no una linea de reto al final del
  prompt. La honestidad deja de ser una instruccion y pasa a ser estructura.
- **El payload se proyecta por punto.** Medido: el mismo turno de cinco
  categorias pesa 3.830 caracteres en vez de 17.061, con los 12 productos
  enteros. No hace falta recortar nada nunca.
- **Muere la cirugia de strings**: `_punto_omitido_repuesto`, `IT.instruccion`,
  la concatenacion de `obligacion`, y las 46 reescrituras posteriores.

**Esto es el diferenciador.** No es "el modelo no puede escribir un precio", que
es defensivo y lo hace cualquiera. Es "el modelo razona sobre una tabla de
pregunta y evidencia, y cada hueco lo ve". Un bot que sabe exactamente que no
sabe, punto por punto, y pregunta por eso y nada mas.

---

## 6. LO QUE HAY QUE ARREGLAR EN LA DERIVACION: CUATRO COSAS, TRES SACAN CODIGO

1. **Una restriccion que ninguna puerta resuelve NO se descarta.** Viaja al punto
   como `sin_material` con su texto. Hoy se pierde en silencio en
   `resolver.py:190-191`. **Se borran dos lineas.**
2. **Dos extremos opuestos: o viajan los dos, o no viaja ninguno.** Hoy gana el
   primero, `resolver.py:168`. Elegir es inventar. **Es una linea.**
3. **`atributos[].campo` acota la ficha.** Hoy se pide entera y el campo se
   ignora, `resolver.py:276`. Esto ademas achica el payload solo. **Suma tres
   lineas y saca peso.**
4. **`contradicciones` sale como pregunta, siempre.** Hoy no la lee nadie.
   **Es una linea en el armado de puntos.**

Ninguna agrega una pieza. Tres sacan codigo. Y las cuatro se miden con los
mismos casos de oro que ya existen, sin clave y sin modelo.

---

## 7. ORDEN DE EJECUCION

Una ficha, una sesion, un commit. En `main`, sin ramas, sin flags apagadas.

```
1. Los cuatro arreglos de la seccion 6.                     1 commit
   Vara: los casos de oro de capa 2 que hoy fallan por eso.
   C2-S04 y C2-S07 tienen que ponerse verdes.
2. `material_por_punto(declarado, llamadas, idx)` en un       1 commit
   archivo nuevo. Devuelve la tabla de la seccion 5.
   Vara: casos de oro propios, entrada y salida a mano.
   Offline y gratis. No toca el camino vivo todavia.
3. `turno.py` usa la tabla como material de la llamada dos    1 commit
   y el orchestrator apunta ahi. A `archivo/` van
   salida, mensaje, indice_turno, grafo, atadura_prosa,
   invariantes y hub_venta, con su fila en archivo/README.
4. Medicion en vivo, tres corridas, manda el peor caso.       1 commit
   Si no iguala al viejo medido el mismo dia: git revert.
```

El paso 1 se puede hacer hoy, no toca el camino vivo y no necesita clave.

---

## 8. LO QUE SE QUEDA CUANDO SE APAGUE EL RESTO

Las herramientas deterministas que hacen posible la respuesta, y nada mas:

```
fuente de verdad    data/clientes/, fuente_producto, curadas, indice
busqueda y filtros  herramientas, filtros_catalogo, compatibilidad
la plata            calculadora, calc_defensiva, pago, pago_split, envio
el lugar            geo_cp
la casa             guia_venta_prosa, guia_compra, familias
la venta            leads, cierre, camino_cobro, estado_venta, pedido
la infra            main, config, logger, orchestrator, firestore_client,
                    connectors, memoria_larga, antijailbreak, llm_reintento
el turno            turno.py, nuevo
```

Lo que se apaga, a `archivo/`, sin borrar: `salida.py`, `mensaje.py`,
`indice_turno.py`, `grafo.py`, `atadura_prosa.py`, `invariantes.py`,
`hub_venta.py`, `guardas_salida.py`, `huecos.py`, `contexto_turno.py`,
`coherencia_datos.py`, y `resolver.py` una vez que `turno.py` se lleve lo que
sirve.

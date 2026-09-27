# EL FORMULARIO DE CATEGORÍAS — lo que ya está, lo que falta, y las opciones

Escrito el 6-sep-2026 leyendo `main`. **Las partes del sistema no se describen
acá: se nombran por su número y viven en `MAPA_CABLEADO.md`**, que es el único
lugar donde se define qué es T6, J4 o D1. Este archivo es sólo las opciones y el
orden.

**LA DIFERENCIA QUE MARTÍN CORRIGIÓ EL 6-SEP, Y ES EL PUNTO ENTERO.** Lo que hay
hoy y lo que él quiere no son lo mismo:

- **Hoy:** la mesa le manda al modelo el MATERIAL crudo de cada fila, y las
  casillas de texto las llena el modelo en la llamada dos.
- **Lo que él quiere:** el CÓDIGO llena cada casilla con la respuesta ya escrita
  después de la llamada uno, y la llamada dos sólo le pone prosa de venta encima.

En su versión el modelo deja de componer la afirmación y sólo la redacta, así
que la superficie donde puede alucinar es mucho más chica. Eso es el hueco 4, y
está abierto.

---

## 1. LA MITAD DE LA TUBERÍA YA ESTÁ, Y ES LA MITAD CARA

Las piezas de abajo sirven igual para las dos versiones. Lo que cambia entre una
y otra es UNA sola cosa: quién escribe el texto de cada casilla.

| pieza | qué hace | dónde |
|-------|----------|-------|
| formulario de categorías | `RegistrarPedido`, diez campos | `herramientas.RegistrarPedido` |
| llamada uno declara intención | L1, temperatura 0, sólo declara | `turno._pedir_herramientas` |
| el código busca y arma las filas | la mesa: una fila por punto, con estado | `tabla.tabla` |
| el material queda mecánico | cuatro estados y material proyectado | `tabla._material_del_punto` |
| llamada dos escribe | L2 con esquema estricto | `turno._redactar` |
| el código pega la plata | bloque sellado, no se retipea | `tabla.armar` |
| el código conduce la venta | el carril `guion`, al sistema | `tabla._guion` |

Cuatro huecos. El 2 y el 3 se cerraron el 6-sep; el 1 y el 4 siguen abiertos.

---

## 2. HUECO 1 — ABIERTO · texto libre donde debería haber categorías cerradas

Tu frase fue "un formulario con todas las categorías posibles". Hoy el
formulario tiene diez campos, pero **dos de los que más se usan son texto
libre**:

- `atributos[].campo` — qué dato preguntó, string suelto.
- `temas[]` — con las palabras del cliente, string suelto.

`categoria` y `tema` sí tienen enum vivo generado de la fuente en las otras
herramientas; estos dos no. Ahí nacen la parte de fondo de **D4** y **D7**.

### Opción 1A · Enum cerrado, generado de la fuente
El campo se elige de la lista real de columnas del catálogo de esa tienda, igual
que ya se hace con `categoria`. El modelo no puede nombrar un campo que no
existe.
- A favor: mata la adivinanza de raíz. Misma disciplina que el repo ya aplica.
- En contra: el enum viaja en el esquema **en cada turno**, y tu criterio después
  de la prioridad uno es resultado más optimización de tokens.

### Opción 1B · Certificar el campo, como ya se certifica la identidad — **la recomendada**
El campo sigue viajando libre y el código lo pasa por una función determinista
con **los tres veredictos de la regla cero**: `existe`, `ambiguo`, `no_existe`.
Con `ambiguo` la fila sale como `pregunta` y el bot pregunta cuál de los dos; con
`no_existe` sale `sin_material` honesto. Nunca se elige por el cliente.
- A favor: no paga un token de esquema, y convierte D4 de adivinar en silencio a
  preguntar o decir que no lo tiene, que es la prioridad uno.
- En contra: hay que escribir la función y su tabla mínima de flexiones.
- Dónde: reemplaza `tabla._valor_del_campo`, que hoy elige la clave que más
  palabras comparte.

### Opción 1C · Normalizar la fuente
Cada columna del catálogo declara sus alias y su verbo. El código sólo consulta.
- A favor: es el arreglo definitivo y sirve para el motor multitienda.
- En contra: es trabajo de fuente por cada tienda, y la fuente ya tiene una deuda
  más urgente, que es D8.

**Criterio de aceptación:** un campo que la ficha no tiene y otro que existe con
dos nombres parecidos terminan, uno en `sin_material` honesto y el otro en
`pregunta`, y ninguno en una cifra.

---

## 3. HUECO 2 — CERRADO 6-sep · la prosa de venta no llegaba al que escribe

Era **D1**, y es lo que más explicaba que la respuesta saliera correcta y
robótica. Se hizo la opción 2B: un carril `guion` que no es una fila. Las otras
dos opciones quedan escritas por si hay que volver.

- **2A, sumar los campos a la fila del tema.** Descartada: la movida quedaría
  adentro de algo que hay que contestar, y el modelo puede terminar
  escribiéndole al cliente la instrucción interna.
- **2C, una tercera llamada que vista la respuesta.** Descartada: es un proceso
  más que se conflictúa con los otros y paga una llamada entera por turno.

**Cómo se mide:** `tests/test_guion_y_junta.py`, cinco casos, y en producción el
renglón `tabla_armada` ahora dice qué situación de venta condujo el turno.

---

## 4. HUECO 3 — CERRADO 6-sep · el redactor no tenía el arco del mensaje

Se hizo la opción 3B: la conducción entra por el mensaje de **sistema**, al lado
de la identidad del vendedor, no entre los datos del turno. Para el modelo la
diferencia es grande: el sistema es quién es y cómo vende; el usuario es qué le
preguntaron.

- **3A, un campo más en el esquema.** Descartada: compite con `pregunta_final` y
  rompe la regla de una sola pregunta por turno, que costó cerrar.
- **3C, que el arco lo escriba el código.** Descartada por el repo: el código no
  redacta, y los cuatro moldes de `_pregunta_del_codigo` son el máximo.

**Lo que hay que mirar en la próxima prueba real:** que el largo no haya subido.
La regla 2 del objetivo dice que el tope del piso baja después de cada corte y no
vuelve a subir.

---

## 5. HUECO 4 — ABIERTO · que el código llene la casilla, no el modelo

**Éste es tu diseño y es la ficha grande.** Hoy la fila lleva material —
`{"id": "MOU0023", "garantia_meses": 12}` — y el modelo escribe la oración. En tu
versión la fila lleva **la oración ya escrita** — "La garantía es de 12 meses" —
y el modelo sólo la hace sonar a vendedor.

Lo que cambia: el modelo deja de tener permiso para AFIRMAR. Puede reordenar,
unir, dar tono; no puede decir un número que el código no escribió.

### Opción 4A · Respuesta mecánica por tipo de fila
Una función `_respuesta_del_codigo(fila)` hermana de la `_pregunta_del_codigo`
que ya existe: un molde por tipo — atributo, tema, stock, envío,
compatibilidad — que arma el renglón con el material de esa fila.
- A favor: son cinco moldes y ya hay cuatro escritos para las preguntas, así que
  el patrón está probado. Se puede hacer tipo por tipo, midiendo cada uno.
- En contra: `items` no entra fácil, porque una lista de tres productos con sus
  precios no es un renglón.
- Riesgo real: si el modelo tiene la oración ya escrita, puede limitarse a
  copiarla y el mensaje sale más plano que hoy. Se mide con el largo y la
  repetición.

### Opción 4B · Casilla llena sólo donde hoy se alucina
Los tipos donde el modelo compone una AFIRMACIÓN sobre la fuente — atributos,
stock, compatibilidad — pasan a venir escritos; los de venta — items, temas —
siguen como hoy.
- A favor: ataca exactamente los cuatro casos de oro de la capa 4 que no cubre
  nada, sin aplanar la parte que vende.
- En contra: dos regímenes conviviendo, y el repo viene sacando exactamente eso.

### Opción 4C · La casilla llena viaja como referencia, no como reemplazo
La fila lleva material **y** la oración del código, y la instrucción dice que la
oración es la verdad: se puede reformular, no contradecir.
- A favor: no aplana.
- En contra: es una atadura de prosa, que es justo lo que se apagó el 3-sep
  porque no se podía vigilar mecánicamente.

**Antes de elegir hace falta el paso 0 de abajo**, porque las tres se miden con
la misma vara y hoy esa vara marca cero.

---

## 6. EL ORDEN, Y POR QUÉ ESTE Y NO OTRO

**Paso 0 — devolverle la vara a la capa 4.** Hoy son 0 de 10 y el mecanismo que
medían está apagado, o sea D2. Si tocás quién escribe la casilla sin esa vara, no
vas a poder saber si mejoró o si sólo suena mejor, y ése es el lugar donde el
proyecto ya se perdió antes. Cuatro de los diez casos no los cubre nada:
descuento que la fuente no da, datos de cobro fabricados, negar lo que el turno
tiene en la mano, plazo de garantía distinto del de la ficha. **Reescribir un
caso de oro es decisión tuya.**

**Paso 1 — hueco 4, que es tu arquitectura.** Con la vara puesta, elegir entre
4A, 4B y 4C deja de ser una opinión.

**Paso 2 — hueco 1, opción 1B.** Cierra el fondo de D4 y ayuda a D7.

**Fuera de esta lista y sin tapar por ninguna: D8.** La restricción de origen no
se puede cumplir con la fuente de hoy porque el campo es prosa. Es la única
prioridad que el cliente declaró y es tu pregunta de prueba. Decidir qué campo
normalizado se agrega es tuyo, y hasta que exista, cualquier arreglo de código
ahí es cosmético.

---

## 7. CÓMO SE MIDE, offline y sin gastar clave

```
python3 -m pytest -q
```

```
python3 banco_pruebas/oro.py
```

Piso del 6-sep-2026 después de los cuatro arreglos: 493 verdes y 1 xfail en la
batería; 48 de 65 en el banco de oro, con capa 2 en 33 de 40, capa 4 en 0 de 10 y
capa 5 en 15 de 15.

Ningún paso cierra si alguno de esos dos números baja.

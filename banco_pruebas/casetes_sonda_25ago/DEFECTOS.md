# SONDA DEL 25-AGO — los defectos, con turno exacto

## ANTES QUE NADA: LAS GRABACIONES SE PERDIERON

Esta carpeta **no tiene los casetes**. La sonda se grabo en una sesion cuyo
contenedor se reciclo sin pushear, y con el se fueron las grabaciones y los dos
commits que ya tenian el arreglo de compatibilidad escrito. En `git` no quedo
nada: ni objeto suelto, ni rama remota, ni reflog.

Lo que sigue es **lo unico que sobrevivio**: el reporte que Martin escribio a
mano leyendo la sonda. Se guarda tal cual porque los numeros de turno son
irrecuperables de otra forma, y sin ellos la proxima grabacion no se puede
comparar contra nada.

**No es un corpus y no se fija como tal.** La bateria lee
`banco_pruebas/casetes/*.json` y esta carpeta es hermana, asi que no la toca.
Cuando se regrabe, los casetes nuevos van a `casetes/` por el camino de
siempre; este archivo queda como la lista de lo que hay que verificar que
dejo de pasar.

## LOS DEFECTOS

### 1. EL CUARTO FRENO — la oferta pisa una pregunta propia sin contestar
Tres turnos ofrecen encima de una pregunta que el mismo bot acaba de hacer:
**76 t1, 80 t6, 80 t8**. Los tres frenos que existen hoy miran herramienta
ambigua; ninguno mira si el turno dejo una pregunta propia abierta.

### 2. EL DETECTOR DE OFERTA ES LAXO
Cuenta **16 OFRECIDO** y al menos cuatro no son ofertas:
- **71 t3** — cortesia de cierre generica
- **73 t3** — mencion de descuento
- **80 t8** — pedido de confirmacion
- **76 t2** — no nombra ningun producto

Mientras el detector cuente esto, todo lo que se mida sobre oferta esta sucio.

### 3. UNIVERSAL SOBRE EL CATALOGO — alucinacion
**46 t4** y **62 t2** afirman algo general del catalogo que no salio de ninguna
herramienta. Prioridad uno: es invencion, no estilo.

### 4. NOTA INTERNA AL CLIENTE
**80 t6** le mando al cliente el texto "el cliente pide".

### 5. PROMESA SIN DATO
**79 t1** promete un dato y no lo da. `camino_al_cobro` bajo de **9/15 a 7/15**.

## EL ORDEN QUE PIDIO MARTIN

No se regraba todavia. Primero (1) y (2), que son los que ensucian la
medicion; regrabar antes de arreglarlos es pagar la grabacion dos veces.

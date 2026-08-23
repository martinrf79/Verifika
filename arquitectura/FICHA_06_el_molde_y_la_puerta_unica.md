# FICHA 06 — El molde y la puerta única

> **La más grande del plan, y cierra tres pasos de una.** El modelo pasa a ver
> UNA herramienta, el esquema baja de 25.230 a menos de 6.000 bytes, y **por fin
> aparece el número real de omisión.**

---

## ⚠️ LEER ESTO PRIMERO: EL NÚMERO DE OMISIÓN VA A EMPEORAR, Y ESTÁ BIEN

Hoy son **22 puntos sin contestar sobre 206**, un once por ciento. Ese número es
mentira por abajo: las preguntas informativas —atributo, stock, compatibilidad,
política— **no abren punto**, así que lo que no se contesta de ellas no se cuenta.

Cuando el molde las declare, esos puntos van a abrirse **y muchos van a aparecer
sin contestar.** El porcentaje va a subir.

> **Eso no es una regresión: es la verdad apareciendo.** Si nadie lo dice antes,
> alguien va a mirar el número, creer que rompió algo y revertir un acierto.

El número que **sí** tiene que aguantar es el del piso —495 puntos, largo 1.872—,
que mide otra cosa: si el bot contesta bien las charlas grabadas.

---

## QUÉ SE PIDE

Que la llamada UNO **solo declare**, y que el código derive qué buscar.

```
HOY       el modelo ve 9 herramientas y ELIGE.
          25.230 bytes de esquema. En el 57% de los turnos declara
          algo que no busca.

OBJETIVO  el modelo ve 1: registrar_pedido, con las cuatro familias
          nuevas adentro. Menos de 6.000 bytes. El codigo deriva las
          busquedas de lo declarado.
```

**Los campos nuevos NO se suman a los 25 KB: los reemplazan.** Las otras ocho
**no se borran** —no se saca capacidad—: dejan de ser visibles para el modelo y
pasan a ser funciones internas que el código llama.

## LOS TRES TESTS QUE CIERRA

```
test_el_modelo_ve_una_sola_herramienta
test_el_esquema_pesa_menos_de_seis_kilobytes
(y habilita, sin cerrarlo, el numero real de cobertura)
```

Al pasar, `strict=True` los pone rojos: se sacan las dos marcas y
`tests/plan_techo.json` baja de 9 a 7, **en el mismo commit**.

## EL MEJOR CHEQUEO DE ACEPTACIÓN, y es gratis

> **El reconciliador tiene que quedar en CERO faltantes, por construcción.**

Hoy reclama en el 57% de los turnos porque lo declarado y lo buscado no coinciden.
Si el código deriva las búsquedas de la declaración, **no queda nada que
reconciliar**. Si después del cambio sigue reclamando, el código no está derivando
bien y **la unidad no cerró, aunque los tests estén verdes.**

Se mira en el log del turno: `"reconciliador": {"faltantes": 0, ...}`.

## LOS TEMAS: TEXTO LIBRE + CERTIFICACIÓN

El enum de temas pesa 2.299 bytes, el más caro de todos. **Sale, y no es aflojar
la atadura:** el modelo nombra el tema **libre** y el código lo certifica contra
las 738 señas de la fuente.

Es la **regla cero aplicada a un tema en vez de a un producto**: tres veredictos
de primera clase, y ante `ambiguous` **se repregunta, no se elige**. Y se loguea
cada vez que un tema no resuelve, para que si el código se come uno se vea en el
log y no lo pague el cliente.

**Los enum de `categoria` y `campo` NO se tocan.** No están por peso: son la
atadura que impide nombrar una categoría que no vendemos o un campo que la ficha
no tiene.

## LAS DESCRIPCIONES NO SE TIRAN

Las ocho herramientas llevaban su semántica en la descripción del esquema —qué
resuelve cada una, cuándo usarla—. **Eso es lo que le enseñaba al modelo a
declarar bien.** Al sacarlas, esa semántica **se muda a la descripción de los
campos de `registrar_pedido`**, no se pierde.

> Si el modelo empieza a declarar peor después del cambio, el motivo más probable
> es éste. Es lo primero que hay que mirar antes de culpar al diseño.

## EL ORDEN, y no se hace en otro

```
1. registrar_pedido gana los 4 campos, con las descripciones mudadas
2. el codigo deriva las busquedas de lo declarado
   (`_busqueda_de_lo_declarado` deja de ser un parche y pasa a ser
    el camino normal)
3. las 8 salen de `esquemas()` y quedan como funciones internas
4. regrabar los 15 casetes  <- obligatorio: el esquema cambio
5. medir TODO y recien ahi commitear
```

**No se puede saltear el 4.** Los casetes guardan lo que el modelo dijo con el
molde viejo; sin regrabar, las cuatro familias siguen sin abrirse y la medición
no vale.

## QUÉ NO PUEDE ROMPERSE

```
piso: puntos          495 o mas
piso: largo_max       1.872 o menos   (NO puede subir)
piso: llamadas_max    2               (NO puede subir)
casetes               0 huecos Y 0 turnos mudos
bateria               990 passed, cero rojos
reconciliador         faltantes en CERO
```

**Criterio de aborto:** si después de regrabar el piso baja y no se puede
explicar con una línea de log, **se revierte entero** y se parte la unidad. La
base está limpia —la FICHA 03 la dejó así—, y el método de grabación es el mismo,
así que una caída **es atribuible al cambio**. No hay ruido donde esconderse.

## ARCHIVOS QUE SE TOCAN

```
app/core/herramientas.py   el molde, `esquemas()`, la certificacion de temas
app/core/hub_venta.py      derivar las busquedas de lo declarado
banco_pruebas/casetes/     regrabados
```

**DEPLOYA.** El push se consulta.

## ARCHIVOS QUE NO SE TOCAN

```
app/core/indice_turno.py   ya abre las 10 familias (FICHA 02)
los prompts                son otra ficha
tests/                     ninguno se afloja para que pase
```

## CÓMO SE VERIFICA — offline salvo el paso de grabar

```bash
python3 -m pytest tests/test_plan_del_recorte.py -q   # los 2 que cierran
python3 -m pytest -q                                   # nada roto
python3 banco_pruebas/peso_del_turno.py                # el esquema, en bytes
python3 banco_pruebas/peso_reposicion.py               # puntos y reconciliador
```

## LAS TRAMPAS CONOCIDAS

**1. Regrabar: `grabar_casetes.py` sin argumentos graba TODOS.** Hay 94 guiones y
15 casetes: correrlo pelado grabaría 79 de más y se comería la cuota diaria. Se
nombran, de a dos o tres, con `BANCO_PAUSA_S=8`. **Clave gratis, siempre.**

**2. Cero huecos Y cero turnos mudos.** El contador de huecos no ve el turno que
se grabó con las llamadas presentes pero **vacías**. Hay que barrer los dos.

**3. La reposición no se borra en esta ficha.** Tentación natural: si el código
ya deriva las búsquedas, `_busqueda_de_lo_declarado` parece redundante. **No se
toca acá**: juntar las seis reposiciones en una es otro paso del plan, y mezclarlo
con esto hace imposible saber qué movió qué.

**4. `tomar_pedido` no se llamó en ningún turno grabado.** Sale con las otras
siete, pero la señal de compra tiene que seguir saliendo determinista del mensaje
y del carrito, que ya existe. **Si el cierre deja de dispararse, es acá.**

**5. Un turno puede necesitar buscar algo que el cliente no declaró.** Ejemplo: el
cliente dice "y el otro" refiriéndose a algo de la memoria. Eso lo resuelve el
estado, no la declaración. **Si al derivar se pierde el anclaje a la memoria, la
memoria larga se rompe** —y es la prioridad 3 del objetivo—.

## CÓMO SE VUELVE ATRÁS

`git revert`. Es la unidad de mayor riesgo hasta ahora: **si hay duda, se
revierte y se parte en dos**, primero el molde y después la puerta.

---

## LO QUE VIENE DESPUÉS

```
FICHA 07  cada punto termina con un estado terminal
          RESUELTO / AMBIGUO->repregunta / NO SE SABE / CONFLICTO
FICHA 08  la cobertura deja de ser log y pasa a ser PUERTA
```

Con esas dos, **un turno no puede salir dejando algo sin contestar**, y la
omisión —que esta ficha recién va a hacer visible— pasa de ser un número a ser
imposible.

# FICHA 05 — La concisión del turno más pesado, y el tope baja de escalón

> **Es lo único que falta para el verde**, y el verde es lo que deja salir el
> arreglo del Total —un defecto **vivo**— a producción. El gate rojo que pusimos
> para avisar del defecto está bloqueando su propia cura.

---

## QUÉ SE PIDE

Que el turno 2 del guión `76` entre en el tope, **y que el tope baje al número
nuevo.**

## EL NÚMERO

```
HOY       turno 2 de 76:  2.060 caracteres     tope 1.882
OBJETIVO  ese turno bajo el tope, y el tope REFIJADO en el maximo real
          que quede. Si el peor turno queda en 1.740, el tope es 1.740.
```

**Ya medía 2.060 antes de que la FICHA 04 tocara `app/`**: viene de la
regrabación, no del arreglo. Los bloques que agregó la 04 quedaron en 1.644 y
1.821, los dos bajo el tope.

## LA GRASA, ya desglosada — no hay que buscarla

```
 67 caracteres   anuncio de presupuesto HUERFANO que duplica el encabezado
                 del bloque que viene justo abajo
367 caracteres   prosa que repite garantia y contenido de caja que la ficha
                 del producto YA lista
```

Hacen falta 178. Hay 434. **Sobra margen, así que no hay excusa para cortar
cerca del dato.**

## ⚠️ EL RIESGO NO ES CORTAR DE MENOS, ES CORTAR UN DATO

La prioridad uno manda sobre la dos, y ya está escrita en el prompt del redactor:

> *"Lo que se recorta es el relleno, NUNCA el dato ni la pregunta: contestar todo
> lo que te preguntaron y decir el criterio que el cliente puso mandan sobre ser
> breve."*

Y desde la FICHA 02 **eso es medible, no una intención**: si al acortar un punto
pasa de contestado a sin contestar, el mensaje se acortó rompiendo la respuesta.

> **Eso es una regresión disfrazada de mejora**, y es el único modo de falla
> serio de esta unidad. El largo baja y el número se ve lindo mientras el cliente
> recibe menos de lo que preguntó.

## QUÉ NO PUEDE ROMPERSE

```
cobertura         los puntos contestados NO pueden bajar. Se mira antes
                  y despues, con el mismo corpus.
puntos del piso   495 o mas (hoy 495 con el arreglo de la 04)
llamadas_max      2
bateria           todo lo que estaba verde sigue verde
los 3 casetes     los que subieron con la regrabacion no pueden bajar
```

## EL TOPE BAJA, y esto vale más que el arreglo

Hasta hoy el piso **solo impedía que el largo creciera**. Un tope que solo
prohíbe empeorar deja el número donde está para siempre: 1.882 ya subió dos veces
y **nunca bajó**, y `PENDIENTE.md` lo tiene anotado como el primero que tiene que
bajar.

**La regla nueva, y queda para todos los cortes que vienen:**

> Después de cada corte, el tope se fija en el máximo real que quedó, y no puede
> volver a subir.

Así la concisión es un **efecto medido del recorte**, no una tarea aparte que
nunca llega. Cada pieza que se saca de la cadena de salida baja el número un
escalón, y el escalón queda.

## ARCHIVOS QUE SE TOCAN

```
app/core/mensaje.py    el componedor, si el anuncio huerfano sale de ahi
app/core/hub_venta.py  si el anuncio lo repone una pieza de salida
banco_pruebas/casetes/_piso.json   el tope nuevo, DESPUES de medir
```

**DEPLOYA.** El push se consulta.

## ARCHIVOS QUE NO SE TOCAN

```
los casetes        ya estan bien: 0 huecos, 0 turnos mudos
tests/             ninguno se afloja para que pase
```

## CÓMO SE VERIFICA

```bash
# 1. el largo del peor turno, y CUAL es
python3 -m pytest tests/test_charlas_grabadas.py -q

# 2. la cobertura NO bajo  <- el chequeo que importa
python3 banco_pruebas/peso_reposicion.py   # la linea de PUNTOS, antes y despues

# 3. nada roto
python3 -m pytest -q
```

## LAS TRAMPAS CONOCIDAS

**1. La repetición se MIDE, no se opina.** `invariantes.nada_se_dice_dos_veces` y
`no_repite_el_mensaje_anterior` ya existen. Si el corte se justifica con "esto
suena repetido", no alcanza: hay que mostrarlo con el invariante.

**2. Cortar en el prompt es la salida fácil y la peor.** Una regla más en el
prompt no agrega control —está medido en `banco_pruebas/README.md`: el 2-ago se
agregó una regla para tapar un caso y `avanza` bajó de 3/5 a 2/5; después se
sacaron 14 reglas y subió a 5/5—. **Si la grasa la pone el código, se saca del
código.** Un anuncio huérfano que duplica un encabezado que el propio código
escribe abajo es código, no prompt.

**3. El tope se refija UNA vez, al final, con el máximo real.** No de a poco ni
estimado. Y si después del corte el peor turno queda en 1.740, el tope es 1.740,
no 1.882 "por las dudas": dejar aire es dejar que vuelva a crecer.

**4. Ojo con qué turno es el peor después del corte.** Puede pasar a serlo otro.
El tope se fija sobre el máximo del corpus, no sobre el turno que se arregló.

## CÓMO SE VUELVE ATRÁS

`git revert`. El tope viejo queda en el historial.

---

## LO QUE VIENE DESPUÉS

Con esta cerrada, `origin/main` vuelve a verde y **el arreglo del Total llega al
bot**. Recién ahí se retoma el plan grande:

```
FICHA 06  el molde gana las 4 familias Y el modelo pasa a ver UNA
          herramienta. Cierra tres pasos de una: 1 herramienta visible,
          esquema bajo 6 KB, y por fin el numero REAL de omision.
FICHA 07  cada punto termina con un estado terminal
FICHA 08  la cobertura deja de ser log y pasa a ser PUERTA
```

Y queda anotado el defecto de instrumento que la 03 dejó abierto:
`puerta_piso.json` guarda **razones** contra un corpus mutable, así que mueve
numerador y denominador a la vez y no puede decir cuál se movió. No es urgente,
pero mientras siga así sus rojos hay que leerlos con pinzas.

# arquitectura/ — la orden de trabajo

**Esta carpeta es lo único que hace falta leer para trabajar.** Martín le nombra
esta ruta a Claude Code, Claude Code lee la ficha que esté abierta, y el
resultado lo ven los tres en el mismo lugar.

---

## Los dos números que dicen dónde está el proyecto

No hace falta abrir nada. Se corre `pytest -q` y se mira cuántos `PLAN:` y
cuántos `A MEDIAS:` hay. Esos dos números no se copian acá: envejecen.

```
A MEDIAS   algo que se EMPEZÓ y no se terminó.  Tiene que llegar a CERO.
PLAN       algo que TODAVÍA NO SE EMPEZÓ.       Baja al hacerse.
```

La orden de trabajo abierta es `FICHA_43_la_salida_habla_las_familias.md`.
La 41 unificó nombres adentro del molde. La 42 nombró el catálogo de la
pregunta. Los dos termómetros siguen.

---

## Cómo se cierra un paso, y por qué hay un rojo en el medio

Esto confunde la primera vez y conviene tenerlo a mano:

```
1. hoy        el test falla + la marca puesta   → xfailed   batería VERDE
2.            se hace el trabajo
3. un minuto  el test PASA + la marca puesta    → XPASS     batería ROJA ← el aviso
4.            se saca la marca, baja el techo   → passed    batería VERDE, uno menos
```

El paso 3 no es un problema: es **un cartel de obra en una calle que ya está
arreglada.** `strict=True` obliga a sacarlo. Sin eso, un pendiente ya resuelto
seguiría contando como pendiente para siempre y el número mentiría.

---

## Qué hay acá, y qué hay en la raíz

**Acá: la orden de trabajo.** Qué se hace ahora, con qué archivos, qué NO se
toca, cómo se verifica.

| archivo | qué es |
|---|---|
| `README.md` | esta puerta |
| `FICHA_30_la_simplificacion.md` | el diagnóstico del recorte |
| `FICHA_34_el_nexo.md` | primera sesión: el nexo, cerrada |
| `FICHA_35_la_puerta.md` | segunda sesión: la puerta, cerrada |
| `FICHA_36_el_numero.md` | tercera sesión: el número; termómetros siguen |
| `FICHA_41_un_idioma.md` | un idioma, el del molde; cerrada |
| `FICHA_42_el_catalogo_de_la_pregunta.md` | el catálogo de la pregunta; cerrada |
| `FICHA_43_la_salida_habla_las_familias.md` | **abierta**: la salida habla las familias abiertas |
| `PLAN_REDUCCION.md` | **la campaña**: 604 funciones → 181, qué se queda |

**En la raíz: la biblioteca.** Se consulta para entender POR QUÉ, no para saber
qué hacer.

| archivo | qué manda |
|---|---|
| `../PASO0_CENSO.md` | los NÚMEROS medidos, y cómo volver a sacarlos |
| `../DECISIONES.md` | QUÉ se decidió y por qué — 40 líneas |
| `../PLAN_RECORTE.md` | CÓMO se hace cada paso y en qué orden |
| `../ARQUITECTURA.md` | cómo está ordenado el sistema hoy |
| `../tests/test_plan_del_recorte.py` | el plan viejo, lo que queda de las fichas 1 a 25 |
| `../tests/test_plan_de_la_simplificacion.py` | **el plan de ahora**: nexo y puertas |

> **Por qué los cuatro no están físicamente acá.** Reescribir 45 KB de prosa
> para cambiarles la ruta agrega riesgo de transcripción y no gana nada: nadie
> los abre por su ubicación, los abre por el enlace. La división que importa no
> es de carpetas, es de trabajos: **una orden de trabajo se lee para hacer, una
> referencia se lee para entender.** Si igual conviene moverlos, es su propio
> commit y su propia verificación.

---

## Quién escribe qué

```
EL DISEÑO (Cowork)   escribe .md y tests/. Nunca toca app/.
                     Pone los pasos en ROJO.

LA INGENIERÍA        escribe app/. Pone los rojos en VERDE.
(Claude Code)        NO puede modificar un test para que pase.

MARTÍN               aprueba el push, que es lo que deploya.
```

**La regla que sostiene esto:** el que implementa no reescribe la vara. Si el
test lo escribe el diseño y lo pone en verde la ingeniería, el punto ciego no se
comparte. Un test que se afloja para pasar es un test borrado con otro nombre.

Si un test está mal, se discute y se cambia **a propósito**, y el commit explica
el requisito nuevo. Es el único motivo legítimo para editar lo que un test
espera.

---

## Verde no es lo mismo que funciona

Lo más importante de esta carpeta, y hay que decirlo aunque incomode.

**Un test verde prueba lo que el test afirma, no que el bot venda bien.** Este
repo ya vivió el caso: el 29-jul el CI llamaba a los casetes con `|| true`,
imprimía "sin casetes grabados" y estuvo **verde cinco días sin correr nada**.

Por eso cada paso de esta carpeta cierra con tres condiciones, no con una:

1. **Su test pasa**, y pasa sobre el número de casos declarado —no sobre cero.
2. **Ningún número del piso baja.** `casetes/_piso.json` guarda puntos, llamadas
   y largo; si uno empeora, el corte se revierte entero.
3. **La charla completa sigue andando.** Un test de pieza no ve las juntas, y
   las juntas son donde vivieron los dos bugs registrados. Lo único que ve una
   junta es la charla corrida de punta a punta.

Y un paso no se declara hecho por la mitad: **o cierra con las tres, o sigue
abierto.**

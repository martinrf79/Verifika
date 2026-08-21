# FICHA 01 — El grafo registra en las seis etapas

> # ✅ CERRADA — 21-ago-2026, commit `ede944d`
>
> Deployada y verde. **Verificada aparte desde Cowork**, no por el parte:
>
> ```
> el diff de tests/   saco la MARCA, no toco el assert
> app/                puro instrumento, cero cambio de comportamiento
> bateria             985 passed, 11 xfailed  (era 984 / 12)
> censo               32 de 32 nodos registran, ninguno ciego
> ```
>
> **La prueba de que el instrumento nuevo sirve, y es la que importa:** los seis
> numeros de la reposicion que ahora da el grafo — 13%, 4%, 44%, 7%, 7%, 2% —
> son **identicos** a los que `banco_pruebas/peso_reposicion.py` habia medido el
> 18-ago envolviendo las funciones a mano desde afuera. Dos instrumentos que no
> comparten cableado, las mismas 15 charlas, los mismos numeros.
>
> Un instrumento que se mide a si mismo no prueba nada. Estos dos no.
>
> **Lo que aparecio al encender la luz:** `cierre` sale MUERTO —corre en los 54
> turnos y no mueve el texto en ninguno—, asi que los nodos de salida que no
> intervienen pasan de 8 a 9. Y `decisor`, `herramientas`, `redactor` y `memoria`
> salen ESTRUCTURAL al 100%: **no son guardias que se puedan podar, son piezas
> del contrato del turno.** Esa distincion no existia antes de esta ficha.
>
> El texto de abajo queda como registro de lo que se pidio. No se ejecuta de
> nuevo: el candado es que el test pasa sin marca, y volver a quedar ciego lo
> pone rojo.

---

## QUÉ SE PIDIÓ

Que las seis etapas del turno dejen marca en el grafo, no solo `salida`.

## CÓMO SE VE DESDE EL CLIENTE

**No se ve. Y era a propósito.** Esta unidad no toca el mensaje que recibe el
cliente: solo agrega observación.

## EL TEST

```
tests/test_plan_del_recorte.py::test_el_grafo_registra_en_las_seis_etapas
```

## EL NÚMERO

```
ERA       registraban 17 de 32 nodos: solo la etapa `salida`
QUEDO     32 de 32. `peso_del_censo.py` dejo de imprimir el aviso de ciegos.
```

## CÓMO SE VERIFICÓ — offline, sin clave, sin red

```bash
python3 -m pytest -q                        # 985 passed, 11 xfailed
python3 banco_pruebas/peso_del_censo.py     # 32/32, sin aviso de ciegos
python3 banco_pruebas/peso_reposicion.py    # los mismos 6 numeros
```

## LA TRAMPA CONOCIDA, y cómo se sorteó

**1. Un instrumento no puede tumbar lo que mide.** `paso_datos` serializa para
comparar y si eso falla cae a `repr`, y si también falla devuelve vacío: medir
peor es aceptable, tumbar el turno por medir no.

**2. Los nodos que NO transforman texto no se pueden medir comparándolos.** Se
resolvió con dos herramientas distintas y el nombre lo dice: `paso_datos` compara
el estado serializado —y ahí el grafo mide solo—; `veredicto` es para los cinco
que no devuelven lo que reciben, y su criterio de "intervino" lo escribió una
persona en una línea al lado de la llamada. **Que se llamen distinto importa:**
un número medido y un número declarado no valen lo mismo, y ahora se distinguen
leyendo.

**3. Una diferencia con `G.paso` que está bien que exista.** `G.paso` se traga la
excepción y devuelve el texto como entró —ninguna guardia puede dejar mudo al
bot—. `paso_datos` marca y **re-lanza**: una función de datos rota no puede pasar
datos mal en silencio. Mudo es peor que roto en la salida; en los datos es al
revés.

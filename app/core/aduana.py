"""
LA ADUANA — los invariantes corren ANTES de que el mensaje salga, no despues.

POR QUE EXISTE (Martin, 11-ago-2026, y es la tarea uno del dia). El 10-ago se
construyeron los invariantes: nueve propiedades que ninguna respuesta correcta
viola, que no saben cual es la respuesta esperada y por eso convierten
cualquier conversacion en un test. Encontraron el error de plata y seis
defectos mas que nadie habia visto. Pero corrian **despues**: bajaban las
charlas de Firestore y contaban los errores que el cliente YA habia leido.

Martin lo dijo asi: "los errores se contabilizan, se miden, pero luego de que
pasan; hay que diagnosticarlos de antemano para que no se cometan". Eso es esto.
El mismo archivo de reglas, corrido en el ultimo metro del turno: el mensaje ya
esta compuesto entero y todavia no salio. Un invariante corrido despues cuenta
errores; corrido aca, los evita.

LAS DOS COSAS QUE HACE, y la segunda importa tanto como la primera:

  1. REPARA lo que puede PROBAR. Tres clases de defecto que le llegaron a
     Martin -una etiqueta interna fugada, un encabezado que promete una lista y
     no muestra ninguna, un renglon calcado dentro del mismo mensaje- se
     arreglan borrando lo que sobra. Nada mas.
  2. GRITA lo que no puede reparar, en el instante en que pasa y con el
     trace_id. El error de plata del 10-ago costo una hora de leer logs porque
     nadie sabia que estaba ahi. Ahora sale un `aduana_rojo` en el log de Cloud
     Run, con la regla y el detalle, el mismo segundo.

LAS DOS ATADURAS QUE LA HACEN SEGURA, y son la razon por la que esto no es
otra tijera al final -que ya fallo dos veces, ver el comentario del tope en
`mensaje.py`-:

  A. **LA PLATA NO SE TOCA NUNCA.** Despues de cada reparacion se comparan
     TODOS los importes del mensaje, uno por uno. Si cambio aunque sea uno, la
     reparacion se descarta entera y el defecto se loguea sin arreglar. Una
     aduana que corrige un peso es peor que el defecto que arregla.
  B. **SOLO SE APLICA SI DEJA EL MENSAJE MEJOR.** Se vuelven a correr los
     invariantes sobre el texto reparado: se acepta unicamente si quedan MENOS
     violaciones y ninguna NUEVA. Si la reparacion rompe otra cosa, se revierte
     sola.

LO QUE NO HACE, a proposito: no juzga si la respuesta es la correcta -eso no se
puede sin saber la pregunta-, no acorta, no reescribe prosa del modelo y no
deja mudo al bot. Si algo explota, devuelve el texto tal como entro.
"""
import re

from app.logger import get_logger
from app.verifika import invariantes as INV

log = get_logger(__name__)

# Las reglas de PLATA. Una violacion de estas nunca se repara -inventar una
# cuenta seria peor que mandarla mal- y se loguea como ROJO, que es lo que hay
# que mirar primero en produccion.
_ROJAS = frozenset({
    "renglon_no_multiplica",
    "subtotal_no_suma",
    "el_pago_dividido_no_suma_el_total",
    "cobra_distinto_de_lo_que_factura",
    "cobra_distinto_del_total",
    "dos_totales_distintos",
    "producto_cotizado_que_no_existe",
})

_RE_IMPORTE = re.compile(r"\$\s*[\d\.]+")
_RE_TITULO = re.compile(r"^\s*[^\n]{3,60}:\s*$")

# EL MARCADOR, para que el banco pueda ver lo que la aduana ATAJO.
#
# Sin esto pasa algo que confunde: desde que la aduana corre en el camino vivo,
# el explorador puede dar CERO violaciones porque no habia ninguna o porque la
# aduana las arreglo antes de que el mensaje saliera, y los dos casos se leen
# igual. Con el marcador se distinguen. En produccion sube y nadie lo mira, que
# es exactamente lo que tiene que pasar; el log es el que manda ahi.
_marcador: dict = {"reparadas": 0, "rojas": 0, "defectos": 0, "detalle": []}


def marcador() -> dict:
    """Lo que la aduana atajo desde el ultimo reinicio."""
    return {**_marcador, "detalle": list(_marcador["detalle"])}


def reiniciar_marcador() -> None:
    _marcador.update({"reparadas": 0, "rojas": 0, "defectos": 0, "detalle": []})


def _importes(texto: str) -> list:
    """Todos los importes del mensaje, en orden. Es la huella de la plata: si
    cambia entre el texto que entro y el reparado, la reparacion se descarta."""
    return [re.sub(r"\s+", "", x) for x in _RE_IMPORTE.findall(texto or "")]


def _reglas(fallas: list) -> list:
    return [f.get("regla", "") for f in fallas]


# ── LAS REPARACIONES. Cada una borra lo que sobra, ninguna escribe ──────────
def _sin_etiquetas_internas(texto: str) -> str:
    """La etiqueta `<d ID>` de la atadura de prosa, fugada al cliente. Se saca
    con el mismo limpiador que usa la atadura, que conserva el texto de adentro
    y se lleva solo la marca."""
    from app.core.atadura_prosa import sin_etiquetas
    return sin_etiquetas(texto)


def _sin_titulos_sin_lista(texto: str) -> str:
    """Un titulo con nada abajo, o con otro titulo abajo. `mensaje.py` ya corre
    su version; esta caza lo que sobrevivio, que es el `Resumen:` huerfano que
    aparecio en TRES charlas reales distintas."""
    lineas = (texto or "").splitlines()
    fuera = set()
    for i, l in enumerate(lineas):
        if not _RE_TITULO.match(l):
            continue
        siguiente = next((x for x in lineas[i + 1:] if x.strip()), "")
        if not siguiente or _RE_TITULO.match(siguiente):
            fuera.add(i)
    if not fuera:
        return texto
    return re.sub(r"\n{3,}", "\n\n",
                  "\n".join(l for i, l in enumerate(lineas)
                            if i not in fuera)).strip()


def _sin_renglones_calcados(texto: str) -> str:
    """El mismo renglon largo dos veces en el mismo mensaje: queda el primero.

    Los renglones de la CUENTA quedan afuera, por el mismo motivo que en el
    invariante: el mismo producto partido en dos destinos escribe dos renglones
    iguales y esa plata es correcta. Ahi manda la aritmetica, no el parecido.
    """
    lineas = (texto or "").splitlines()
    vistas, fuera = set(), set()
    for i, l in enumerate(lineas):
        clave = INV._n(l)
        if len(clave) < 25 or INV._RE_ITEM.match(l):
            continue
        if clave in vistas:
            fuera.add(i)
        vistas.add(clave)
    if not fuera:
        return texto
    return re.sub(r"\n{3,}", "\n\n",
                  "\n".join(l for i, l in enumerate(lineas)
                            if i not in fuera)).strip()


# regla del invariante -> reparacion que la ataca
_REPARACIONES = (
    ("etiqueta_interna_fugada", _sin_etiquetas_internas),
    ("encabezado_huerfano", _sin_titulos_sin_lista),
    ("renglon_repetido_en_el_mensaje", _sin_renglones_calcados),
)


def _vocabulario(tienda_id: str) -> set:
    """Los nombres reales del catalogo, para que un producto cotizado que no
    existe se vea. Sale del cache de 5 minutos que ya usa cada turno: no agrega
    una lectura a Firestore. Si no se puede leer, se devuelve vacio y ese
    invariante no controla nada, que es su contrato."""
    if not tienda_id:
        return set()
    try:
        from app.storage.firestore_client import get_all_products
        return {str(p.get("nombre") or "") for p in
                get_all_products(tienda_id=tienda_id) if p.get("nombre")}
    except Exception:
        return set()


def revisar_salida(texto: str, anterior: str = "", trace_id: str = "",
                   tienda_id: str = "", vocabulario: set | None = None) -> str:
    """El ultimo control antes de mandar. Devuelve el texto listo para salir.

    Nunca levanta, nunca devuelve vacio: ante cualquier problema propio,
    devuelve el texto tal como entro. Una aduana rota no puede dejar mudo al
    bot."""
    original = texto or ""
    if vocabulario is None:
        vocabulario = _vocabulario(tienda_id)
    try:
        fallas = INV.revisar(original, anterior=anterior,
                             vocabulario=vocabulario or set())
    except Exception as e:  # noqa: BLE001 — el control no puede romper el turno
        log.warning("aduana_error", trace_id=trace_id,
                    error=f"{type(e).__name__}: {str(e)[:120]}")
        return original
    if not fallas:
        return original

    texto_ok = original
    reparadas = []
    for regla, arreglar in _REPARACIONES:
        if regla not in _reglas(fallas):
            continue
        try:
            candidato = arreglar(texto_ok)
        except Exception as e:  # noqa: BLE001
            log.warning("aduana_reparacion_error", trace_id=trace_id,
                        regla=regla, error=str(e)[:120])
            continue
        if not (candidato or "").strip() or candidato == texto_ok:
            continue
        # ATADURA A: la plata tiene que quedar identica, importe por importe.
        if _importes(candidato) != _importes(texto_ok):
            log.warning("aduana_reparacion_descartada", trace_id=trace_id,
                        regla=regla, motivo="movia_la_plata")
            continue
        nuevas = INV.revisar(candidato, anterior=anterior,
                             vocabulario=vocabulario or set())
        # ATADURA B: se acepta solo si quedan MENOS violaciones y ninguna nueva.
        if len(nuevas) >= len(fallas) or (set(_reglas(nuevas)) -
                                          set(_reglas(fallas))):
            log.warning("aduana_reparacion_descartada", trace_id=trace_id,
                        regla=regla, motivo="no_mejoraba")
            continue
        texto_ok, fallas = candidato, nuevas
        reparadas.append(regla)

    if reparadas:
        log.info("aduana_reparado", trace_id=trace_id, reglas=reparadas,
                 largo_antes=len(original), largo_despues=len(texto_ok))
        _marcador["reparadas"] += len(reparadas)
        _marcador["detalle"] += [f"reparada:{r}" for r in reparadas]

    rojas = [f for f in fallas if f.get("regla") in _ROJAS]
    quedan = [f for f in fallas if f.get("regla") not in _ROJAS]
    _marcador["rojas"] += len(rojas)
    _marcador["defectos"] += len(quedan)
    _marcador["detalle"] += [f"{'roja' if f in rojas else 'defecto'}:"
                             f"{f['regla']}" for f in fallas]
    if rojas:
        # ROJO: plata que no cierra o producto que no existe. No se repara -no
        # se inventa una cuenta- pero se ve en el segundo en que pasa, con el
        # trace_id para traer la charla entera.
        log.error("aduana_rojo", trace_id=trace_id,
                  reglas=[f["regla"] for f in rojas],
                  detalle=" | ".join(f["detalle"] for f in rojas)[:400])
    if quedan:
        log.warning("aduana_defecto", trace_id=trace_id,
                    reglas=[f["regla"] for f in quedan],
                    detalle=" | ".join(f["detalle"] for f in quedan)[:400])
    return texto_ok

"""
DIVERGENCIA — mide, sin tocar la respuesta, cuando el SOLVER hizo algo distinto
a lo que leyo el INTERPRETE en los ejes CERRADOS del turno (producto, estado,
opciones A/B).

Es el paso 1 de la estrategia acordada con Martin (6-jul): antes de ENFORZAR la
lectura del interprete sobre el solver, primero MEDIR el tamano real del
problema en el banco de charlas vivas. Este modulo NO cambia nada; solo detecta
y el pipeline lo loguea (evento interprete_libre_divergencia).

Conservador como el resto del sistema: solo marca la divergencia INEQUIVOCA. Es
medicion, no un verificador que pisa; puede tener falsos positivos que se leen y
afinan antes de pasar a enforzar en los pasos 2, 3 y 4.
"""
import unicodedata

# Estados del embudo donde REABRIR el catalogo (mostrar productos nuevos) es
# sospechoso: el cliente ya esta confirmando o dando datos para cerrar. No se
# incluyen saludo/explorando (mostrar es lo esperado) ni posventa/derivar.
_ESTADOS_CERRANDO = {"esperando_confirmacion", "esperando_datos", "cierre"}


def _norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def _tokens(s: str) -> list[str]:
    """Tokens con carne (len > 3) de un nombre o referencia de producto. Descarta
    articulos y palabras cortas que matchearian cualquier cosa."""
    return [t for t in _norm(s).split() if len(t) > 3]


def detectar_divergencias(interp: dict, respuesta: str,
                          ids_mostrados: list[str] | None = None) -> list[dict]:
    """Lista de divergencias entre la lectura del interprete y lo que hizo el
    solver ([] = alineados). Cada item: {eje, clase, detalle}.

    - eje 'producto': el interprete resolvio UN producto y el solver mostro otro
      (mostro productos pero ninguno matchea el resuelto).
    - eje 'opciones': el interprete pidio ofrecer A o B y el solver NO planteo la
      eleccion (no pregunta, o no nombra las dos). Es el caso que hoy corrige la
      guarda A/B; medirlo dice cuanto dispara.
    - eje 'estado': el interprete puso el turno en un estado de cierre y el solver
      REABRIO el catalogo mostrando productos.
    """
    if not isinstance(interp, dict):
        return []
    out: list[dict] = []
    ids_mostrados = ids_mostrados or []
    r = _norm(respuesta)
    mostro_productos = bool(ids_mostrados)

    # ── EJE PRODUCTO ────────────────────────────────────────────────────
    # El interprete resolvio a que producto se refiere el cliente. Si el solver
    # MOSTRO productos pero ninguno de los tokens del resuelto aparece en la
    # respuesta, mostro OTRO producto que el que el cliente pidio.
    resuelto = interp.get("producto_resuelto")
    if resuelto and mostro_productos:
        toks = _tokens(resuelto)
        if toks and not any(t in r for t in toks):
            out.append({
                "eje": "producto",
                "clase": "solver_mostro_otro",
                "detalle": f"resuelto={str(resuelto)[:60]}",
            })

    # ── EJE OPCIONES A/B ────────────────────────────────────────────────
    # El interprete no pudo elegir y pidio ofrecer dos caminos. El solver tiene
    # que plantear la eleccion: preguntar Y nombrar las dos. Si no, eligio por el
    # cliente o no pregunto. Misma logica que _forzar_pregunta_si_ambiguo.
    opciones = interp.get("ofrecer_opciones")
    if isinstance(opciones, list) and len(opciones) >= 2:
        a, b = str(opciones[0]).strip(), str(opciones[1]).strip()
        if a and b:
            pregunta = ("?" in (respuesta or "")) or ("¿" in (respuesta or ""))

            def _menciona(op: str) -> bool:
                tk = _tokens(op)[:3]
                return bool(tk) and any(t in r for t in tk)

            if not (pregunta and _menciona(a) and _menciona(b)):
                out.append({
                    "eje": "opciones",
                    "clase": "no_planteo_eleccion",
                    "detalle": f"A={a[:40]} | B={b[:40]}",
                })

    # ── EJE ESTADO (embudo) ─────────────────────────────────────────────
    # Estado de cierre pero el solver mostro productos nuevos: reabrio el
    # catalogo cuando el turno ya iba a confirmar o pedir datos. Senal cruda
    # (puede ser legitimo: "y en otro color?"), se lee antes de enforzar.
    estado = _norm(interp.get("estado_conversacion"))
    if estado in _ESTADOS_CERRANDO and mostro_productos:
        out.append({
            "eje": "estado",
            "clase": "reabrio_catalogo",
            "detalle": f"estado={estado} ids={len(ids_mostrados)}",
        })

    return out

"""
ESTAMPADO DE LA FAQ CURADA — los numeros nunca viven en el texto.

Cada tema de `faq.json` trae la `respuesta_curada` que escribio Martin y, aparte,
sus `valores` estructurados. El texto lleva huecos `{{concepto}}` y este modulo
los rellena con el valor de ese mismo tema. Una tarifa que cambia se cambia en el
valor y la curada nunca queda vieja: hay UNA sola fuente del numero.

Si un hueco no resuelve, `estampar_valores` devuelve None y el llamador NO sirve
la curada. Una politica a medias -"tenes {{dias}} dias para el cambio"- es peor
que no contestarla.

DOS FUENTES, DOS NATURALEZAS (3-ago). La prosa sin numeros -voz, criterio,
movidas, mensajes fijos- vive en `base_conocimiento.json`. La politica CON
numeros vive aca, en `faq.json`, porque sus `valores` son dato duro y se suben a
Firestore como el catalogo. No es la fuente partida al medio: es dato en el
archivo de dato y prosa en el archivo de prosa.

Lo que este modulo tenia hasta hoy y se BORRO: todo el ACOPLE, unas trescientas
lineas que decidian cuando pegar el bloque curado abajo de la prosa del solver.
Estaba muerto desde el 2-ago, porque dependia de la tool `query_faq` y del dict
de veinte campos del interprete, y ninguna de las dos existe. Las cinco lecciones
de charlas reales que ese codigo encerraba -no repetir el enlatado, un solo
cierre por mensaje, no pedir un dato que la charla ya tiene, la politica general
no tapa el dato exacto, y con pedido en juego la politica acompaña- NO se
perdieron: pasaron a `identidad.charla` en la fuente, o sea que ahora se las dice
al modelo en cada turno en vez de corregirlo despues.
"""
import re

from app.logger import get_logger

log = get_logger(__name__)

_HUECO_RE = re.compile(r"\{\{(\w+)\}\}")


def _money(n) -> str:
    try:
        return "$" + f"{int(round(n)):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(n)


def _fmt_valor(v: dict) -> str | None:
    """Renderiza un valor estructurado como texto legible segun su unidad y
    modalidad. None si no hay forma segura de renderizarlo."""
    unidad = str(v.get("unidad") or "").strip().lower()
    if v.get("modalidad") == "rango":
        mn, mx = v.get("monto_min"), v.get("monto_max")
        if isinstance(mn, (int, float)) and isinstance(mx, (int, float)):
            return f"entre {_money(mn)} y {_money(mx)}"
        return None
    # Umbral (ej envio_gratis): el dato util no es el monto (0) sino el umbral.
    for k in ("umbral_ars", "base_ars"):
        u = v.get(k)
        if isinstance(u, (int, float)) and u > 0:
            return _money(u)
    m = v.get("monto")
    if not isinstance(m, (int, float)):
        return None
    if unidad == "porcentaje":
        return f"{int(m)}%"
    if unidad in ("", "ars", "pesos", "peso", "$"):
        return _money(m)
    # Cantidad no monetaria (cuotas, dias): el numero pelado.
    return str(int(m))


def estampar_valores(texto: str, faq_tema: dict) -> str | None:
    """Rellena cada hueco {{concepto}} con el valor estructurado de ese concepto
    en la MISMA FAQ. Si un hueco no resuelve, devuelve None: una curada a medias
    no se sirve (el turno cae al camino normal y queda el warning)."""
    valores = {str(v.get("concepto") or ""): v
               for v in (faq_tema.get("valores") or [])}

    fallo = []

    def _rep(m):
        v = valores.get(m.group(1))
        r = _fmt_valor(v) if v else None
        if r is None:
            fallo.append(m.group(1))
            return m.group(0)
        return r

    out = _HUECO_RE.sub(_rep, texto)
    if fallo:
        log.warning("curada_hueco_sin_valor", huecos=fallo[:5],
                    tema=faq_tema.get("tema"))
        return None
    return out

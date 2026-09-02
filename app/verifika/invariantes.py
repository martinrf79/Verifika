"""
LOS DOS HELPERS QUE EL VIVO USA.

El termometro —`revisar`, `revisar_charla` y las reglas— salio de app/ en
la FICHA 48. Vive en `banco_pruebas/invariantes.py`. Snapshot en
`archivo/invariantes_20260902.py`.

POR QUE QUEDAN ESTOS DOS ACA. `pago.py` llama `pago_parcial` y `salida.py`
usa `_RE_ITEM`. El Dockerfile copia `app/` y no `banco_pruebas/`. Un parser
de la cuenta que el cobro necesita no puede vivir fuera de la imagen.

El formato del renglon lo escribe el codigo una sola vez y lo leen dos:
el cobro, para saber cuanto pedir, y el termometro, para gritar si no
coinciden. Escrito dos veces, el dia que cambie el formato uno de los dos
deja de ver la seña en silencio, que es como nacio el error del 10-ago.
"""
import re
import unicodedata

# "- 2x Mouse Genius DX-110 Negro: $8.500 c/u = $17.000"
_RE_ITEM = re.compile(
    r"^\s*-\s*(?P<cant>\d+)\s*x\s+(?P<nombre>.+?):\s*\$(?P<unit>[\d\.]+)\s*"
    r"c/u\s*=\s*\$(?P<sub>[\d\.]+)\s*$", re.MULTILINE)

# "Sena 20%: $42.200 (pago parcial)" — lo escribe `_label_extra` de la
# calculadora y es la marca de que el cliente NO paga el total ahora.
_RE_PAGO_PARCIAL = re.compile(
    r"^\s*[^:\n]{2,40}?\s*:\s*\$(?P<monto>[\d\.]+)\s*\(pago parcial\)\s*$",
    re.IGNORECASE | re.MULTILINE)


def _n(s) -> str:
    s = unicodedata.normalize("NFKD", re.sub(r"\s+", " ", str(s or "")).strip().lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def _plata(s) -> int:
    return int(str(s).replace(".", ""))


def pago_parcial(mensaje: str) -> int | None:
    """Lo que el cliente paga AHORA cuando la cuenta lleva una seña. None si la
    cuenta no marca ningun pago parcial."""
    m = _RE_PAGO_PARCIAL.search(mensaje or "")
    return _plata(m.group("monto")) if m else None

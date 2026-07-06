"""
MEMORIA REFERENCIAL BORROSA — el caso "el que te dije antes, no me acuerdo cuál".

Paso 3 del plan 6-jul. Cuando el cliente se refiere a un producto ANTERIOR de la
charla de forma vaga, el que decide QUE producto es no puede ser el solver
adivinando un id: el CODIGO es dueño de la memoria. Este modulo detecta la
referencia borrosa de forma determinista y arma una GUIA que se inyecta al solver
ANTES de que responda (mismo patron que guia_compra):

  - un unico producto visto  -> se ANCLA ese ([[PROD:id]] real, estampado por el
    codigo), el solver no elige.
  - varios vistos            -> se manda PREGUNTAR cual, no adivinar.
  - ninguno en memoria       -> se manda NO inventar, pedir que lo nombre de nuevo.

Es guia previa, no pisa la salida: compone con todos los verificadores de despues.
Logica pura, sin LLM ni Firestore (los productos vistos llegan por parametro).
"""
import re
import unicodedata

# Frases con las que un cliente referencia un producto anterior sin nombrarlo.
# Conservadas: expresiones especificas de "eso que ya hablamos", no cualquier
# demostrativo suelto ("ese", "aquel") que daria falsos positivos.
_RE_REFERENCIA = re.compile(
    r"que te dije|que te habia (dicho|comentado)|"
    r"el que (te )?(dije|mencione|nombre|pedi|comente)|"
    r"no me acuerdo|no recuerdo|"
    r"que vimos|que habiamos visto|que me mostraste|que mostraste|"
    r"\bel de antes\b|\blos de antes\b|\bel anterior\b|\bla anterior\b|"
    r"\bel primero\b|\bel segundo\b",
    re.IGNORECASE,
)


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def es_referencia_memoria(mensaje: str) -> bool:
    """El mensaje referencia un producto anterior de la charla sin nombrarlo."""
    return bool(_RE_REFERENCIA.search(_norm(mensaje)))


def guia_memoria(mensaje: str, productos_vistos: list | None) -> str:
    """Guia para el solver cuando el cliente referencia algo anterior. "" si no
    es una referencia borrosa. El codigo manda sobre la memoria: ancla el unico
    visto, o manda preguntar/no inventar. Se agrega al mensaje del solver."""
    if not es_referencia_memoria(mensaje):
        return ""
    vistos = [p for p in (productos_vistos or [])
              if isinstance(p, dict) and p.get("id") and p.get("nombre")]

    if len(vistos) == 1:
        p = vistos[0]
        return (f"\n\n[MEMORIA: el cliente se refiere a un producto que YA vimos "
                f"en esta charla: {p['nombre']}. Es ESE. Anclá tu respuesta a "
                f"[[PROD:{p['id']}]] y no adivines otro producto ni otro id.]")

    if len(vistos) >= 2:
        listado = ", ".join(str(p["nombre"]) for p in vistos[:6])
        return (f"\n\n[MEMORIA: el cliente se refiere a uno de estos productos que "
                f"YA vimos, pero no queda claro cuál: {listado}. NO adivines cuál: "
                f"preguntale cuál de esos era antes de seguir.]")

    return ("\n\n[MEMORIA: el cliente cree que mencionó un producto antes, pero no "
            "hay ninguno en la memoria de esta charla. No inventes uno: decile que "
            "no te quedó registrado y pedile que lo nombre de nuevo.]")

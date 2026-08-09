"""
EL INDICE DEL TURNO: el nexo entre lo que se INTERPRETO y lo que se RESPONDIO.

POR QUE EXISTE (Martin, 9-ago-2026, y lo venia pidiendo hace sesiones).

El sistema tiene dos mitades bien hechas y NADA que las ate:

  - La INTERPRETACION -`registrar_pedido`, el interprete de hoy- entiende bien.
    Medido el 8-ago: 100 sobre 100 en las cinco redacciones, 15 de 15 corridas,
    y la lista de "lo que no entiende" quedo VACIA.
  - La RESPUESTA -la redaccion final, el solver de hoy- se cae igual.

El reconciliador que ya existe compara lo declarado contra las LLAMADAS: sabe si
buscaste el rubro, si aplicaste la condicion, si armaste la cuenta. **Nadie mira
si el punto llego al TEXTO.** Un punto puede estar perfectamente ejecutado y no
salir dicho, y eso es exactamente lo que se mide fallando:
`cada_unidad_con_destino` falla entre 9 y 12 de cada 15 corridas. El cliente dice
a donde va cada cosa, el sistema lo entiende, lo guarda, y el mensaje no lo dice.

QUE HACE ESTE MODULO, y es una sola idea. Cada cosa que el cliente pidio se
convierte en un PUNTO con id estable. Despues se marca, punto por punto, si esa
cosa aparece en la respuesta. El resultado es una lista chica y legible:

    item:1   2 auriculares          -> atendido
    item:2   2 mouse                -> atendido
    destino:2 Concordia             -> FALTA
    pago:1   reparto 70/30          -> atendido

LO QUE NO HACE, y es a proposito. No inventa contenido, no reescribe prosa y no
decide por el cliente. Marca. Lo que se hace con un punto que falta lo decide
quien lo consume: hoy, decirselo al redactor con el punto concreto en la mano en
vez de una instruccion generica.

POR QUE CONTRA EL TEXTO Y NO CONTRA EL ESTADO. Es la regla de tau-bench que ya
usa `objetivo.py`: se juzga por lo observado, no por lo que el agente cuenta que
hizo. El cliente no lee el estado interno: lee el mensaje.
"""
import re
import unicodedata

from app.logger import get_logger

log = get_logger(__name__)


def _n(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def _raiz(palabra: str) -> str:
    """La palabra sin su plural naive. "memorias" y "memoria" son el mismo
    punto, y "auriculares" tiene que encontrarse en "Auriculares Redragon"."""
    p = _n(palabra).strip()
    for cola in ("es", "s"):
        if len(p) > 4 and p.endswith(cola):
            return p[:-len(cola)]
    return p


def _aparece(termino: str, texto: str) -> bool:
    """¿El termino esta en el texto?

    SE COMPARA POR RAIZ CORTA Y DESDE EL ARRANQUE DE PALABRA, y las dos cosas
    tienen su motivo medido. El cliente dijo "partes CHINAS" y el bot escribio
    "de origen CHINO": con la palabra entera el punto figuraba sin atender
    cuando estaba dicho, y un indice que marca en falso es peor que no tener
    indice, porque manda a agregar algo que ya esta. Y el ancla `\\b` al
    arranque evita que "mouse" se de por dicho porque el texto nombre otra cosa
    que lo contenga en el medio."""
    t = _n(texto)
    partes = []
    for w in _n(termino).split():
        if len(w) < 3:
            continue
        r = _raiz(w)
        # De 5 letras para arriba alcanza el prefijo: chin(as|o|a), memoria(s),
        # auricular(es). Mas corto que eso se busca entero, para no pegarle a
        # cualquier palabra.
        partes.append(r[:4] if len(r) >= 5 else r)
    if not partes:
        return False
    return all(re.search(rf"\b{re.escape(p)}", t) for p in partes)


# ── LOS PUNTOS: cada cosa que el cliente pidio, con su id ────────────────────
def puntos(declarado: dict) -> list:
    """Lo interpretado, desarmado en puntos con id estable.

    El id es `tipo:n` y se arma del ORDEN en que el modelo declaro, que es el
    orden del mensaje del cliente. Estable dentro del turno, que es lo que hace
    falta para atar interpretacion con respuesta.
    """
    fuera: list = []
    if not declarado:
        return fuera

    for i, it in enumerate((declarado.get("items") or []), 1):
        que = str(it.get("que") or "").strip()
        if not que:
            continue
        cant = it.get("cantidad") or 1
        fuera.append({"id": f"item:{i}", "tipo": "item", "termino": que,
                      "texto": f"{cant} {que}"})

    for i, r in enumerate((declarado.get("restricciones") or []), 1):
        r = str(r or "").strip()
        if r:
            fuera.append({"id": f"condicion:{i}", "tipo": "condicion",
                          "termino": r, "texto": r})

    for i, d in enumerate((declarado.get("destinos") or []), 1):
        d = str(d or "").strip()
        if d:
            fuera.append({"id": f"destino:{i}", "tipo": "destino",
                          "termino": d, "texto": f"envio a {d}"})

    for i, c in enumerate((declarado.get("contradicciones") or []), 1):
        c = str(c or "").strip()
        if c:
            fuera.append({"id": f"duda:{i}", "tipo": "duda", "termino": c,
                          "texto": c})

    if declarado.get("reparto_pago"):
        pcts = [str(int(float(p.get("porcentaje") or 0)))
                for p in declarado["reparto_pago"]
                if p.get("porcentaje")]
        if pcts:
            fuera.append({"id": "pago:1", "tipo": "pago",
                          "termino": " ".join(pcts),
                          "texto": f"reparto del pago {'/'.join(pcts)}"})

    if declarado.get("pide_precio"):
        fuera.append({"id": "precio:1", "tipo": "precio", "termino": "",
                      "texto": "el precio de lo que pidio"})

    return fuera


# ── LA COBERTURA: que punto llego al texto y cual no ─────────────────────────
_RE_TOTAL = re.compile(r"(?im)^\s*total(?:\s+final)?\s*:")
_RE_PREGUNTA = re.compile(r"\?")


def _cubierto(punto: dict, texto: str) -> bool:
    """UN CRITERIO POR TIPO, y todos miran el texto que lee el cliente.

    No es una sola regla porque los puntos no se contestan igual: un rubro se
    contesta nombrandolo, un destino nombrando la localidad, una duda
    PREGUNTANDO, y el precio con un total. Meter todo en una regla sola es lo
    que hace que una guardia muerda a su vecina.
    """
    tipo = punto.get("tipo")
    termino = punto.get("termino") or ""

    if tipo in ("item", "destino"):
        return _aparece(termino, texto)

    if tipo == "condicion":
        # De la condicion importa la palabra que la hace unica -"chinas",
        # "blanco", "logitech"-, no el relleno con que se dijo. Si alguna de
        # esas palabras esta en el texto, la condicion se nombro.
        vacias = {"que", "las", "los", "una", "unas", "unos", "con", "sin",
                  "menos", "menor", "minima", "minimo", "cantidad", "partes",
                  "posible", "posibles", "componentes", "sean", "sea", "tenga",
                  "tengan", "para", "por", "del", "mas", "muy", "todo", "todos",
                  "quiero", "necesito", "divide", "dividir", "presupuesto"}
        claves = [w for w in _n(termino).split()
                  if len(w) >= 4 and w not in vacias]
        return any(_aparece(w, texto) for w in claves) if claves else True

    if tipo == "duda":
        # Una duda se atiende PREGUNTANDO. Que el texto nombre el objeto de la
        # duda y tenga una pregunta: sin el signo, la nombro al pasar.
        claves = [w for w in _n(termino).split() if len(w) >= 5][:6]
        nombrada = any(_aparece(w, texto) for w in claves) if claves else False
        return bool(nombrada and _RE_PREGUNTA.search(texto or ""))

    if tipo == "pago":
        return all(p in _n(texto) for p in (termino or "").split())

    if tipo == "precio":
        return bool(_RE_TOTAL.search(texto or ""))

    return True


def cobertura(declarado: dict, texto: str, trace_id: str = "") -> dict:
    """El indice del turno: cada punto interpretado, con su estado en la
    respuesta. Devuelve `{puntos, faltan}` y lo deja en el log, que es donde se
    puede leer despues sin adivinar."""
    ps = puntos(declarado)
    if not ps:
        return {"puntos": [], "faltan": []}
    marcados = []
    for p in ps:
        ok = _cubierto(p, texto or "")
        marcados.append({**p, "atendido": ok})
    faltan = [p for p in marcados if not p["atendido"]]
    log.info("indice_turno", trace_id=trace_id,
             total=len(marcados), sin_atender=len(faltan),
             detalle=[f"{p['id']}={'ok' if p['atendido'] else 'FALTA'}"
                      for p in marcados],
             faltan=[p["texto"][:60] for p in faltan][:5])
    return {"puntos": marcados, "faltan": faltan}


def instruccion(faltan: list) -> str:
    """Los puntos sin atender, convertidos en una obligacion CONCRETA para la
    redaccion.

    POR QUE ASI Y NO CON UNA INSTRUCCION GENERICA. Ya esta medido dos veces en
    este repo que "te falto algo, fijate" no mueve al modelo: ante una
    correccion generica pidio cero herramientas 3 de 3 veces. Un punto con su
    texto -"no dijiste que va a Concordia"- es una cosa sola y verificable, que
    es lo unico que se le puede pedir a un redactor.
    """
    if not faltan:
        return ""
    lineas = ["Tu mensaje NO le contesta esto, que el cliente sí pidió. "
              "Agregalo, sin repetir lo que ya escribiste:"]
    for p in faltan:
        lineas.append(f"- {p['texto']}")
    return "\n".join(lineas)

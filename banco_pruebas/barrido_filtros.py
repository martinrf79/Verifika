"""
EL BARRIDO DE LOS FILTROS — cada campo de la ficha contra cada operador, con
valores sacados de la ficha misma.

POR QUE EXISTE, y tiene fecha y caso (Martin, 12-ago-2026): probo en WhatsApp
"¿que garantia tiene?" y el bot no contesto con la garantia. El dato estaba
cargado en los 880 productos. Lo que fallo no fue el dato ni el modelo: fue que
la CONDICION del cliente nunca se verifica contra la ficha, y nadie barria ese
cruce.

Y ese es el reclamo de fondo, textual: "si con cada nueva pregunta hay que hacer
un arreglo nuevo, el bot no razona". Un arreglo por pregunta no termina nunca.
Barrer la superficie entera —41 campos por 5 operadores— si termina, y despues
cualquier pregunta nueva cae adentro de una celda ya probada.

QUE ES LA SUPERFICIE. `filtros_catalogo.campos_filtrables` deriva el registro
de campos del CATALOGO VIVO: las columnas llenas mas las claves de `specs`.
Multiplicado por los cinco operadores da la grilla completa de lo que un cliente
puede preguntar sobre un atributo. La grilla se cuenta y el barrido la cubre
entera; no hay "algunos casos" ni "los mas importantes".

DE DONDE SALEN LOS VALORES, que es lo unico que hace honesta a la prueba: de la
FUENTE. Para cada campo se leen los valores que de verdad tienen los productos
—`color: Negro`, `ram: 16GB`, `bluetooth: si, bluetooth integrado`— y se
pregunta por ellos. Ningun valor escrito a mano. Con eso aparece la propiedad
mas fuerte de todas:

  EL VALOR DE LA FICHA VUELVE A SU FICHA. Si `Negro` esta escrito en la ficha de
  un producto y se filtra por `color contiene Negro`, ESE producto tiene que
  estar en el resultado. Cuando no vuelve, el filtro da cero, la herramienta
  contesta que no hay, y el bot le dice que no al cliente con el dato en la
  mano. Es exactamente la forma del error de la garantia, y es una propiedad
  que ninguna respuesta correcta puede violar.

TAMBIEN SE BARRE LO TORCIDO, porque el modelo lo manda: un operador de
comparacion sobre un campo de texto, un campo que no existe, un valor vacio, la
escapatoria `sin_campo_en_la_fuente`. Ahi la propiedad no es que funcione: es
que se DESCARTE CON MOTIVO ESCRITO. Un filtro que se pierde en silencio es peor
que uno que falla, porque el modelo cree que se aplico y afirma sobre algo que
nadie verifico.

CORRE OFFLINE Y GRATIS: catalogo real, cero llamadas al modelo.
"""
import re
import sys
import unicodedata
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

TIENDA = "verifika_prod"

# Cuantos valores distintos de la fuente se prueban por campo. Tres alcanza para
# tocar el valor comun, uno del medio y uno raro; mas que eso repite la misma
# forma y hace lento el barrido sin cubrir nada nuevo.
VALORES_POR_CAMPO = 3


def _norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c)).strip()


def campos(tienda_id: str = TIENDA) -> dict:
    """El registro de campos filtrables, tal cual lo deriva el codigo vivo del
    catalogo. Es el denominador del barrido y no se escribe a mano."""
    from app.core.filtros_catalogo import campos_filtrables
    return dict(campos_filtrables(tienda_id))


def operadores() -> tuple:
    from app.core.filtros_catalogo import OPERADORES
    return tuple(OPERADORES)


def _productos(tienda_id: str = TIENDA) -> list:
    from app.storage.firestore_client import get_all_products
    return [p for p in (get_all_products(tienda_id=tienda_id) or [])
            if isinstance(p, dict)]


def valores_de(campo: str, prods: list, tope: int = VALORES_POR_CAMPO) -> list:
    """Los valores REALES de ese campo en el catalogo, con su producto testigo.

    Devuelve [{valor, testigo}], donde `testigo` es el id del producto del que
    se leyo el valor. El testigo es lo que convierte la prueba en una propiedad:
    sin el, "el filtro devolvio 12 productos" no dice nada; con el, se puede
    exigir que UNO en particular —el dueño del dato— este ahi.

    Se toman los mas frecuentes primero y despues uno del fondo: el comun cubre
    el caso de todos los dias y el raro cubre el borde de un solo producto.
    """
    from app.core.filtros_catalogo import _valor_crudo
    vistos: dict = {}
    for p in prods:
        v = _valor_crudo(p, campo)
        if v in (None, "", [], {}) or isinstance(v, (dict, list)):
            continue
        clave = str(v).strip()
        if not clave:
            continue
        vistos.setdefault(clave, []).append(p)
    if not vistos:
        return []
    orden = sorted(vistos.items(), key=lambda kv: -len(kv[1]))
    elegidos = orden[:max(1, tope - 1)]
    if len(orden) > len(elegidos):
        elegidos.append(orden[-1])          # el valor de un solo producto
    return [{"valor": k, "testigo": (ps[0].get("id") or ps[0].get("nombre")),
             "cuantos": len(ps)}
            for k, ps in elegidos]


def _valor_de_numero(prod: dict, campo: str):
    """El valor numerico de un campo, leido con el MISMO lector que usa el
    codigo vivo. Se usa para armar los cortes de la prueba de monotonia: si el
    barrido leyera los numeros por su cuenta, estaria comparando el codigo
    contra otra interpretacion de la fuente en vez de contra la fuente."""
    from app.core.filtros_catalogo import _a_numero, _valor_crudo
    v = _valor_crudo(prod, campo)
    return None if v in (None, "", [], {}) else _a_numero(v)


def _palabra_util(valor: str) -> str:
    """Una palabra sola sacada del valor de la ficha, que es como pregunta el
    cliente: la ficha dice "si, bluetooth integrado" y el cliente pregunta por
    "bluetooth". Se saca la puntuacion y se elige la primera palabra con cuerpo.
    """
    for w in re.split(r"[^0-9a-z]+", _norm(valor)):
        if len(w) >= 4:
            return w
    primera = _norm(valor).split(",")[0].strip()
    return primera.split(" ")[0] if primera else ""


def casos(tienda_id: str = TIENDA) -> list:
    """La grilla entera: cada campo por cada operador, con valores de la fuente.

    Cada caso trae `espera`, que es lo que NINGUNA respuesta correcta puede
    violar, decidido por el tipo del campo y el operador —nunca por un resultado
    grabado—:
      trae_al_testigo   el producto del que salio el valor tiene que estar
      excluye_al_testigo    `no_contiene` sobre su propio valor lo tiene que sacar
      descartado        la condicion no se puede aplicar y hay que DECIRLO
    """
    reg = campos(tienda_id)
    prods = _productos(tienda_id)
    fuera = []
    for campo, tipo in reg.items():
        vals = valores_de(campo, prods)
        if not vals:
            continue
        for op in operadores():
            for v in vals:
                crudo = v["valor"]
                if op in ("mayor", "menor") and tipo != "numero":
                    # La grilla se cubre igual: la celda existe y el codigo
                    # tiene que rechazarla con motivo, no aplicarla mal.
                    fuera.append({"campo": campo, "tipo": tipo, "operador": op,
                                  "valor": crudo, "testigo": v["testigo"],
                                  "espera": "descartado"})
                    continue
                if op in ("mayor", "menor"):
                    fuera.append({"campo": campo, "tipo": tipo, "operador": op,
                                  "valor": str(crudo), "testigo": v["testigo"],
                                  "espera": "trae_al_testigo"})
                    continue
                if op == "no_contiene":
                    fuera.append({"campo": campo, "tipo": tipo, "operador": op,
                                  "valor": str(crudo), "testigo": v["testigo"],
                                  "espera": "excluye_al_testigo"})
                    continue
                fuera.append({"campo": campo, "tipo": tipo, "operador": op,
                              "valor": str(crudo), "testigo": v["testigo"],
                              "espera": "trae_al_testigo"})
                if op == "contiene" and tipo != "numero":
                    p = _palabra_util(crudo)
                    if p and p != _norm(crudo):
                        fuera.append({"campo": campo, "tipo": tipo,
                                      "operador": op, "valor": p,
                                      "testigo": v["testigo"],
                                      "espera": "trae_al_testigo",
                                      "como_pregunta_el_cliente": True})
    return fuera


# ── LO TORCIDO: lo que el modelo manda cuando no entiende ───────────────────
#
# No es un caso hipotetico. Cada una de estas formas se midio saliendo del
# modelo vivo: campos inventados, el numero con su unidad pegada, el operador de
# comparacion sobre un color. La propiedad no es que anden: es que el codigo
# diga QUE no pudo aplicar y por que, para que el modelo no de por cumplida una
# condicion que nadie verifico.
def torcidos(tienda_id: str = TIENDA) -> list:
    from app.core.filtros_catalogo import SIN_CAMPO
    reg = campos(tienda_id)
    texto = next((c for c, t in reg.items() if t == "texto"), "color")
    numero = next((c for c, t in reg.items() if t == "numero"), "precio_ars")
    return [
        {"campo": "peso", "operador": "menor", "valor": "500",
         "espera": "descartado",
         "porque": "campo inventado: la ficha dice peso_gramos"},
        {"campo": "medidas", "operador": "contiene", "valor": "chico",
         "espera": "descartado",
         "porque": "campo inventado: la ficha dice dimensiones"},
        {"campo": "", "operador": "contiene", "valor": "algo",
         "espera": "descartado", "porque": "campo vacio"},
        {"campo": texto, "operador": "mayor", "valor": "5",
         "espera": "descartado",
         "porque": "comparacion sobre un campo de texto"},
        {"campo": numero, "operador": "menor", "valor": "muy poco",
         "espera": "descartado", "porque": "el valor no es un numero"},
        {"campo": numero, "operador": "menor", "valor": "",
         "espera": "descartado",
         "porque": "valor vacio en una comparacion"},
        {"campo": SIN_CAMPO, "operador": "contiene",
         "valor": "cancelacion de ruido activa", "espera": "descartado",
         "porque": "la escapatoria: el catalogo no expresa lo que pidio"},
        {"campo": texto.upper(), "operador": "contiene", "valor": "negro",
         "espera": "se_aplica",
         "porque": "el campo con mayusculas, que el modelo manda seguido: se "
                   "tolera y se filtra, no se descarta"},
        {"campo": numero, "operador": "menor", "valor": "500 gramos",
         "espera": "se_aplica",
         "porque": "el numero con la unidad pegada, medido en vivo: se lee el "
                   "numero y se filtra"},
        {"campo": texto, "operador": "igual", "valor": "",
         "espera": "descartado",
         "porque": "valor vacio sobre texto. Hasta el 11-sep se aplicaba y "
                   "dejaba el catalogo en cero, en silencio"},
    ]


def correr(tienda_id: str = TIENDA) -> dict:
    """CORRE la grilla entera y devuelve `{casos, fallas}`.

    POR QUE NO EXISTIA HASTA HOY, y es la misma enfermedad que este repo ya
    documenta con el `|| true` del CI: la grilla estaba armada, contada y
    cubierta al 100%, y la CORRIA una sesion a mano cuando se acordaba. Un
    barrido que nadie ejecuta es una lista de casos, no una vara. Desde el
    11-sep lo corre la bateria, y dice sobre CUANTOS casos paso.

    Las tres esperas salen del tipo del campo y del operador, nunca de un
    resultado grabado:

      trae_al_testigo     el producto del que salio el valor tiene que volver
      excluye_al_testigo  `no_contiene` sobre su propio valor lo tiene que sacar
      descartado          la condicion no se puede aplicar y hay que DECIRLO

    Y los TORCIDOS -lo que el modelo manda cuando se equivoca- tienen una sola
    espera, que es la regla de Martin del 2-ago: nunca vuelve vacia sin motivo
    escrito. Un campo inventado no filtra en silencio; se descarta y se dice.
    """
    from app.core.filtros_catalogo import aplicar
    prods = _productos(tienda_id)
    fallas = []

    def _uno(campo, operador, valor):
        class F:
            pass
        F.campo, F.operador, F.valor = campo, operador, valor
        r = aplicar(prods, [F()], tienda_id)
        return r, {str(p.get("id")) for p in r["productos"]}

    casos_ok = 0
    for c in casos(tienda_id):
        r, ids = _uno(c["campo"], c["operador"], c["valor"])
        testigo = str(c.get("testigo") or "")
        mal = ""
        if c["espera"] == "trae_al_testigo" and testigo and testigo not in ids:
            mal = "el valor de la ficha no volvio a su ficha"
        elif c["espera"] == "excluye_al_testigo" and testigo and testigo in ids:
            mal = "la exclusion dejo adentro al producto que la motivo"
        elif c["espera"] == "descartado" and not r["descartados"]:
            mal = "se aplico una condicion que no se puede aplicar"
        if mal:
            fallas.append({**c, "falla": mal})
        else:
            casos_ok += 1

    for c in torcidos(tienda_id):
        r, _ = _uno(c["campo"], c["operador"], c["valor"])
        # LO TORCIDO TIENE DOS DESENLACES VALIDOS Y NINGUN TERCERO. O el codigo
        # NO PUEDE aplicarlo y lo dice con motivo -nunca vacia sin motivo
        # escrito, la regla de Martin del 2-ago-, o lo TOLERA y filtra igual,
        # que es lo que corresponde cuando el modelo escribe el campo en
        # mayuscula o le pega la unidad al numero. Lo que no vale es el tercero:
        # aplicar algo que no se entiende y devolver cero en silencio.
        mal = ""
        if c["espera"] == "descartado" and not r["descartados"]:
            mal = "se aplico en silencio algo que no se puede aplicar"
        elif c["espera"] == "se_aplica" and r["descartados"]:
            mal = "se descarto algo que habia que tolerar"
        if mal:
            fallas.append({**c, "falla": mal})
        else:
            casos_ok += 1

    return {"casos": casos_ok + len(fallas), "fallas": fallas,
            "productos": len(prods)}


def cobertura(tienda_id: str = TIENDA) -> dict:
    """Cuanto de la grilla toca el barrido. El denominador sale del catalogo
    vivo, asi que si mañana la fuente suma una columna, la cobertura baja sola y
    el candado lo dice en el mismo push."""
    reg = campos(tienda_id)
    cs = casos(tienda_id)
    celdas = {(c, o) for c in reg for o in operadores()}
    cubiertas = {(c["campo"], c["operador"]) for c in cs}
    pendientes = sorted(f"{c} {o}" for c, o in (celdas - cubiertas))
    return {
        "campos": len(reg),
        "operadores": len(operadores()),
        "celdas": len(celdas),
        "cubiertas": len(cubiertas),
        "casos": len(cs) + len(torcidos(tienda_id)),
        "torcidos": len(torcidos(tienda_id)),
        "pendientes": pendientes,
        "cobertura": round(100.0 * len(cubiertas) / max(1, len(celdas)), 1),
    }


if __name__ == "__main__":
    from banco_pruebas import sim_firestore
    sim_firestore.install()
    c = cobertura()
    print(f"campos {c['campos']} x operadores {c['operadores']} = "
          f"{c['celdas']} celdas")
    print(f"cubiertas {c['cubiertas']} ({c['cobertura']}%), "
          f"{c['casos']} casos ({c['torcidos']} torcidos)")
    if c["pendientes"]:
        print("sin cubrir:", c["pendientes"][:12])
    r = correr()
    print(f"corridos {r['casos']} casos sobre {r['productos']} productos: "
          f"{len(r['fallas'])} fallas")
    for f in r["fallas"][:10]:
        print(f"   {f['campo']} {f['operador']} {f['valor']!r}: {f['falla']}")

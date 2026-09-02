"""LA LINEA DEL COBRO MATABA LA OFERTA — el codigo leyendo su propia prosa.

EL DEFECTO, MEDIDO (FICHA 21). `camino_cobro.linea_de_cobro` estampa al final
del mensaje "Podes pagar por transferencia bancaria o con link de pago. Para
armarlo solo necesito tu nombre." Esa linea contiene "link de pago" y "tu
nombre", que son dos literales de `_RE_CERRANDO`. La pasada final de
`indice_turno.cobertura` —la que decide que oferta queda DIFERIDA y la guarda
en la conversacion— leia el texto YA estampado, daba el turno por CERRANDO y
apagaba la oferta con motivo tipado. Y apagarla no es diferirla: `pendientes`
sale vacio, asi que el turno siguiente no la reabre. La oferta no se posterga,
se MUERE. Cuatro ofertas sobre quince charlas, entre ellas el Teclado Logitech
K120 de la charla 71.

POR QUE NO SE ARREGLA SACANDO LAS DOS PALABRAS DE LA LISTA. Porque el defecto
no son esas dos palabras: es que `punto_de_oferta` no puede distinguir la prosa
del modelo de la prosa del codigo, y desde adentro de la funcion NO HAY forma de
distinguirlas —las dos son el mismo str—. Sacar "link de pago" y "tu nombre"
tapa este caso y deja la costura abierta para la proxima puerta que estampe
algo. Es la regla 13 de ARRANQUE.md: el codigo no lee como modelo lo que
escribio el codigo.

EL ARREGLO ES LA FRONTERA. `hub_venta` guarda el texto del modelo justo antes
de la primera puerta —el unico momento del turno en que las dos versiones
existen por separado— y lo pasa a `cobertura` como `texto_del_modelo`. Todo lo
demas se sigue midiendo contra el texto final, que es lo que el cliente lee.

SE PRUEBA POR LOS DOS LADOS (regla 12): que la prosa del CODIGO ya no apaga la
oferta, Y que un cierre escrito por el MODELO la sigue apagando. Un arreglo que
solo probara la primera mitad convertiria el freno del cierre en un adorno.

CORRE OFFLINE: sin modelo, sin clave, sin red.
"""
import ast
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from app.core import indice_turno as IT  # noqa: E402

_MOUSE = {"herramienta": "buscar_productos",
          "pedido": {"descripcion": "mouse logitech"},
          "resultado": {"estado": "encontrado", "productos": [
              {"id": "MOU-001", "nombre": "Mouse Logitech M170 Negro",
               "precio": "$12.000"}]}}

_DEL_MODELO = ("El Mouse Logitech M170 Negro sale $12.000. "
               "Te lo cargo al pedido y te paso el total.")

# LAS TRES FORMAS DE PROSA QUE ESTAMPA EL CODIGO DESPUES DEL MODELO, textuales.
# No son inventadas para el test: son las que emiten `camino_cobro.linea_de_cobro`
# y `guia_pedido.mensaje_presupuesto_sellado`.
_ESTAMPADAS = {
    "cobro sin descuento":
        "Podés pagar por transferencia bancaria o con link de pago. "
        "Para armarlo solo necesito tu nombre.",
    "cobro con descuento":
        "Podés pagar por transferencia bancaria, con 10% de descuento, o con "
        "link de pago. Para armarlo solo necesito tu nombre.",
    "cierre del presupuesto sellado":
        "¿Lo dejamos confirmado? Decime la forma de pago: "
        "transferencia (10% de descuento) o Mercado Pago.",
}

# Cierres que escribe EL MODELO. Estos SI tienen que apagar la oferta.
_DEL_MODELO_CERRANDO = {
    "pide el nombre": "Perfecto. ¿A nombre de quién lo preparo?",
    "pide la direccion": "Listo. ¿A qué dirección te lo mando?",
    "pide como abona": "Genial. ¿Cómo lo abonás?",
}

_CASOS = set()


def _oferta(texto: str):
    """El punto de oferta y lo pendiente, con un producto certificado."""
    return IT.punto_de_oferta([_MOUSE], [], texto, [], [], [])


# ── LADO 1: LA PROSA DEL CODIGO YA NO DECIDE NADA ───────────────────────────

def test_la_prosa_que_estampa_el_codigo_no_apaga_la_oferta():
    """El defecto exacto: la linea del cobro daba el turno por CERRANDO."""
    fallan = []
    for nombre, estampada in _ESTAMPADAS.items():
        _CASOS.add(f"estampada:{nombre}")
        # ASI SE VE EL TEXTO FINAL, y por eso el defecto era invisible: la
        # linea se pega al final del mensaje del modelo, sin costura.
        final = _DEL_MODELO + "\n\n" + estampada
        punto_final, _ = _oferta(final)
        if (punto_final or {}).get("no_corresponde") != "cerrando":
            fallan.append(f"{nombre}: el escenario del defecto ya no se "
                          f"reproduce, asi que el test no prueba nada")
        # Y ASI SE JUZGA AHORA: contra lo que escribio el modelo y nada mas.
        punto, pendientes = _oferta(_DEL_MODELO)
        if (punto or {}).get("no_corresponde"):
            fallan.append(f"{nombre}: la oferta salio apagada con motivo "
                          f"'{punto.get('no_corresponde')}' juzgando SOLO el "
                          f"texto del modelo")
        del pendientes
    assert not fallan, "\n  ".join([""] + fallan)


def test_cobertura_juzga_la_oferta_con_el_texto_del_modelo():
    """La frontera existe en la API, que es lo unico que el turno puede pasar."""
    declarado = {"productos": [{"termino": "mouse logitech"}]}
    fallan = []
    for nombre, estampada in _ESTAMPADAS.items():
        _CASOS.add(f"cobertura:{nombre}")
        final = _DEL_MODELO + "\n\n" + estampada
        idx = IT.cobertura(declarado, final, "test", llamadas=[_MOUSE],
                           texto_del_modelo=_DEL_MODELO)
        ofertas = [p for p in idx["puntos"] if p.get("tipo") == "oferta"]
        if not ofertas:
            fallan.append(f"{nombre}: el punto de oferta ni se abrio")
            continue
        if ofertas[0].get("no_corresponde") == "cerrando":
            fallan.append(f"{nombre}: `texto_del_modelo` no se uso, la prosa "
                          f"del codigo siguio dando el turno por cerrando")
    assert not fallan, "\n  ".join([""] + fallan)


def test_sin_texto_del_modelo_se_cae_al_texto_y_no_al_vacio():
    """Las pasadas que corren ANTES de las puertas no lo pasan y no lo necesitan.

    Y el `""` tiene que valer como texto del modelo vacio, no como 'no me lo
    dijeron': por eso la guarda es `is None` y no un `or`."""
    _CASOS.add("cae_al_texto")
    declarado = {"productos": [{"termino": "mouse logitech"}]}
    cerrando = "Listo. ¿A nombre de quién lo preparo?"
    idx = IT.cobertura(declarado, cerrando, "test", llamadas=[_MOUSE])
    ofertas = [p for p in idx["puntos"] if p.get("tipo") == "oferta"]
    assert ofertas and ofertas[0].get("no_corresponde") == "cerrando", (
        "sin `texto_del_modelo` la pasada tiene que juzgar `texto`, que ahi "
        "todavia ES del modelo")


# ── LADO 2: EL FRENO DEL CIERRE SIGUE SIENDO UN FRENO (regla 12) ────────────

def test_el_cierre_que_escribe_el_modelo_sigue_apagando_la_oferta():
    """Si esto se rompe, el arreglo convirtio el freno 5 en un adorno."""
    fallan = []
    for nombre, texto in _DEL_MODELO_CERRANDO.items():
        _CASOS.add(f"modelo_cerrando:{nombre}")
        punto, pendientes = _oferta(texto)
        if (punto or {}).get("no_corresponde") != "cerrando":
            fallan.append(f"{nombre}: el turno cerraba y la oferta no se apago "
                          f"(motivo: {(punto or {}).get('no_corresponde')!r})")
        if pendientes:
            fallan.append(f"{nombre}: un turno que cierra no difiere nada")
    assert not fallan, "\n  ".join([""] + fallan)


# ── EL CANDADO DEL CAMINO VIVO ──────────────────────────────────────────────

def _llamadas_a_cobertura(fuente: str) -> list:
    """Cada `IT.cobertura(...)` del archivo, con los nombres que le pasa."""
    fuera = []
    for n in ast.walk(ast.parse(fuente)):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        if not (isinstance(f, ast.Attribute) and f.attr == "cobertura"):
            continue
        fuera.append({
            "linea": n.lineno,
            "kw": {k.arg for k in n.keywords if k.arg},
            "primer_pos": (n.args[1].id if len(n.args) > 1
                           and isinstance(n.args[1], ast.Name) else ""),
        })
    return fuera


def test_la_pasada_final_del_turno_pasa_el_texto_del_modelo():
    """EL CANDADO. El arreglo vale por el camino VIVO, no por la firma.

    La pasada final de `hub_venta` es la que guarda `oferta_diferida` en la
    conversacion: si deja de pasar `texto_del_modelo`, la regresion vuelve
    entera y en silencio, porque el parametro tiene default. Se mira el codigo
    y no un log: es la unica forma de que el candado corra offline."""
    _CASOS.add("candado_hub_venta")
    fuente = (_RAIZ / "app" / "core" / "hub_venta.py").read_text(encoding="utf-8")
    finales = [c for c in _llamadas_a_cobertura(fuente)
               if c["primer_pos"] == "texto"]
    assert finales, ("no se encontro en hub_venta ninguna pasada de cobertura "
                     "sobre el texto FINAL: si se renombro, este candado quedo "
                     "midiendo el vacio y hay que reescribirlo")
    sin_frontera = [c["linea"] for c in finales
                    if "texto_del_modelo" not in c["kw"]]
    assert not sin_frontera, (
        f"hub_venta mide la oferta contra el texto final sin pasar "
        f"`texto_del_modelo` en la(s) linea(s) {sin_frontera}. Es la FICHA 21: "
        f"la prosa que estampan las puertas vuelve a decidir por el modelo.")


def test_la_frontera_se_guarda_antes_de_la_primera_puerta():
    """`texto_del_modelo` tiene que capturarse ANTES de que ninguna puerta corra.

    Capturarlo despues seria guardar un texto ya estampado, que es exactamente
    el defecto con un nombre nuevo."""
    _CASOS.add("frontera_antes_de_las_puertas")
    fuente = (_RAIZ / "app" / "core" / "hub_venta.py").read_text(encoding="utf-8")
    lineas = fuente.split("\n")
    captura = next((i for i, l in enumerate(lineas)
                    if l.strip() == "texto_del_modelo = texto"), None)
    assert captura is not None, "hub_venta ya no guarda la frontera del modelo"
    puertas = [i for i, l in enumerate(lineas)
               if 'G.paso("procedencia"' in l or 'G.paso("plata"' in l
               or 'G.paso("obligacion"' in l]
    assert puertas, "cambiaron los nombres de las puertas: reescribir el candado"
    assert captura < min(puertas), (
        f"la frontera se guarda en la linea {captura + 1}, despues de que la "
        f"primera puerta ya corrio (linea {min(puertas) + 1}): el texto "
        f"guardado ya viene estampado")


def test_sobre_cuantos_casos_se_midio():
    """REGLA 3: un test dice sobre CUANTOS casos paso, o pasa por vacio."""
    assert len(_CASOS) == 12, (
        f"se midieron {len(_CASOS)} casos y tienen que ser 12: las 3 formas de "
        f"prosa estampada leidas por los 2 caminos -la funcion y `cobertura`-, "
        f"los 3 cierres escritos por el modelo, el default sin frontera, y los "
        f"2 candados del camino vivo. {sorted(_CASOS)}")

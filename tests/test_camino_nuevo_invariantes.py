"""LA DEFENSA DEL CAMINO NUEVO, SIN MODELO — lo que el codigo garantiza aunque
el traductor escriba cualquier cosa (23-sep-2026).

POR QUE. Gemini obliga el esquema y DeepSeek no: con DeepSeek la unica atadura
es el codigo. Que el camino nuevo no invente no puede depender de que modelo
traduce, asi que se prueba con fichas MALAS a proposito —productos que el
cliente no dijo, rubros y conceptos fuera de lista, posiciones que no existen,
cifras inventadas, tipos rotos— por validar, memoria, compilador y motor, y se
afirma lo que ninguna ficha puede romper:

  1. ningun id que no este en el catalogo;
  2. ningun id que no venga de lo mostrado antes o de un modelo que el cliente
     escribio en ESTE mensaje;
  3. ninguna cifra de precio que el cliente no escribio en la charla;
  4. las opciones de una repregunta son productos reales;
  5. nada se confirma para comprar sin que el turno anterior lo haya
     propuesto con los mismos items: el paso 7;
  6. no se cae.

Y los errores de sentido que se encontraron el 23-sep quedan como casos
fijos: cada uno daba vuelta lo que el cliente pidio.
"""
import random
import re

import pytest

from banco_pruebas import compilador as C
from banco_pruebas import memoria as M
from banco_pruebas import traductor as T
from banco_pruebas.leer_interpretacion import _norm


@pytest.fixture
def tab(firestore_doble):
    return T.tablero()


# ── LOS ERRORES DE SENTIDO, FIJOS ──────────────────────────────────────────

@pytest.mark.parametrize("valor,fuerza,dice,esperado", [
    # Un "no" o un "sin" que no niega la marca no la excluye.
    ("logitech", "debe", "no se, quiero un mouse logitech", "contiene"),
    ("logitech", "debe", "busco un teclado sin cable, marca logitech",
     "contiene"),
    # La negacion pegada al valor si la excluye.
    ("redragon", "debe", "cualquiera menos redragon", "no_contiene"),
    ("redragon", "debe", "que no sean redragon", "no_contiene"),
    ("redragon", "evita", "nada de redragon", "no_contiene"),
])
def test_la_negacion_se_lee_pegada_al_valor(tab, valor, fuerza, dice,
                                            esperado):
    a = C.aterrizar("marca", valor, fuerza, "mouse", dice)
    assert [x["operador"] for x in a["condiciones"]] == [esperado]


@pytest.mark.parametrize("valor,esperado", [
    ("no mas de 200 mil", [("menor", "200000")]),
    ("no menos de 50 mil", [("mayor", "50000")]),
    ("mas de 900 mil", [("mayor", "900000")]),
    ("hasta 80 mil", [("menor", "80000")]),
    ("200 mil", [("menor", "200000")]),
    ("desde 30 mil", [("mayor", "30000")]),
    # La unidad del ultimo numero vale para el rango entero.
    ("entre 50 y 100 lucas", [("mayor", "50000"), ("menor", "100000")]),
    ("de 150 a 300 mil", [("mayor", "150000"), ("menor", "300000")]),
])
def test_el_precio_no_queda_al_reves(tab, valor, esperado):
    a = C.aterrizar("precio_ars", valor, "debe", "monitor", valor)
    assert [(x["operador"], x["valor"]) for x in a["condiciones"]] == esperado


def test_el_genero_no_cambia_el_valor_del_catalogo(tab):
    a = C.aterrizar("pais_marca", "chino", "evita", "tablet",
                    "lo menos chino posible")
    assert [(x["operador"], _norm(x["valor"])) for x in a["condiciones"]] == \
        [("evita", "china")]


def test_una_cifra_que_no_dijo_no_llega_al_pedido(tab):
    """"Que no sea muy cara" sin numero, con el traductor escribiendo un
    techo: el techo no entra. Es M11, ahora del lado del codigo."""
    texto = "quiero un monitor que no sea muy caro"
    ficha = {"partes": [{
        "dice": texto, "quiere": "buscar", "origen": "tienda",
        "rubro": "monitor", "producto": "", "cantidad": 0, "destino": "",
        "refiere": "no", "posiciones": [], "para": "",
        "criterios": [{"concepto": "precio_ars", "valor": "hasta 500 mil",
                       "fuerza": "debe"}]}],
        "afirma": [], "reescrita": texto, "criterios_generales": [],
        "reparto": []}
    r, _ = M.turno(texto, M.estado_nuevo(), tab, lambda _t: ficha)
    conds = [x for c in r["pedido"]["consultas"]
             for x in c.get("condiciones") or []
             if x.get("campo") == "precio_ars"]
    assert conds == []


# ── LA FICHA MALA A PROPOSITO ──────────────────────────────────────────────

_MENSAJES = [
    "mostrame {r}", "cuanto sale el {p}?", "tenes {r}?", "quiero 2 {r} {m}",
    "el segundo", "y el otro?", "de esos el mas barato",
    "mandamelo a Rosario", "{r} de no mas de {n} mil",
    "no se, quiero un {r} {m}", "dale, lo quiero", "algo mas barato?",
    "{r} que no sean {m}", "hola", "precio del {p} y del {q}",
    "{r} hasta {n} mil", "tengo {n} lucas para un {r}",
    "{r} entre {n} y {n2} mil",
]
_BASURA = ["G502 Ultra", "iPhone 15", "Zenbook X99", "teclado",
           "asdf 123", "K120, G203", None, 42]


def _ficha_mala(rng, texto, tab, cat, a):
    """Tres de cada cuatro partes son CREIBLES —copian el mensaje, usan las
    listas— pero se equivocan donde duele: un producto que el cliente no
    nombro, una cifra que no dijo, una posicion que no existe. La cuarta es
    basura de tipos. Las creibles son las que pasan la validacion y llegan a
    la memoria y al compilador, que es lo que se quiere probar."""
    rubros = tab["rubros"] + ["otro", "ninguno", "toda_la_tienda"]
    conceptos = list(tab["conceptos"]) + ["otro", "compatible_con"]
    partes = []
    for _ in range(rng.randint(1, 3)):
        creible = rng.random() < 0.75
        prod = rng.choice(
            [a["modelo"], a["modelo"], "", "",
             rng.choice(cat)["modelo"], rng.choice(_BASURA)])
        dichas = re.findall(r"\d+", texto)
        cifra = rng.choice(dichas * 2 + [rng.randint(1, 999)])
        partes.append({
            "dice": texto if creible else rng.choice(
                [texto[:12], "algo que no dijo"]),
            "quiere": rng.choice(list(T.INTENCIONES)) if creible
            else rng.choice(["vender", None]),
            "origen": "tienda" if creible else rng.choice(
                list(T.ORIGENES) + ["inventado"]),
            "rubro": rng.choice([a["categoria"], rng.choice(rubros)])
            if creible else rng.choice(["heladeras", None]),
            "producto": prod,
            "criterios": [_criterio(rng, cifra, conceptos)
                          for _ in range(rng.randint(0, 2))] + (
                              [] if creible else ["roto", None]),
            "cantidad": rng.choice([0, 1, 3, -2, 10 ** 6]),
            "destino": rng.choice(["", "", "Rosario", "Marte"]),
            "refiere": rng.choice(list(T.REFIERE)) if creible else "aquel",
            "posiciones": rng.choice([[], [1], [2, 3], [-1], [99], [0],
                                      ["dos"]]),
            "para": ""})
    return {"partes": partes + rng.choice([[], ["roto"], [None]]),
            "afirma": rng.choice([[], [{"sobre": "x", "dice": "y"}], ["z"]]),
            "reescrita": texto,
            "criterios_generales": rng.choice(
                [[], [{"concepto": "precio_ars", "valor": "hasta 90 mil",
                       "fuerza": "debe"}]]),
            "reparto": rng.choice([[], [{"medio": "transferencia",
                                         "porcentaje": 70}]])}


def _criterio(rng, cifra, conceptos):
    """Un criterio con un valor de SU tipo: el precio con una cifra dicha o
    inventada, la marca con o sin negar, el color."""
    concepto = rng.choice(["precio_ars", "precio_ars", "marca", "color",
                           rng.choice(conceptos)])
    valores = {
        "precio_ars": [f"hasta {cifra} mil", f"no mas de {cifra} mil",
                       f"{rng.randint(1, 999)} mil", "barato",
                       f"entre {cifra} y {rng.randint(1, 999)} lucas"],
        "marca": ["logitech", "no redragon", "cualquiera menos hp"],
        "color": ["negro", "blanco", "rosa"]}
    return {"concepto": concepto,
            "valor": rng.choice(valores.get(concepto, ["algo", ""])),
            "fuerza": rng.choice(list(T.FUERZAS))}


def _escribio(prod, msg):
    """¿Algun token con numero o palabra del modelo esta en el mensaje?"""
    m = _norm(msg)
    pegado = m.replace(" ", "")
    toks = [w for w in re.findall(r"\w+", _norm(prod.get("modelo")))
            if len(w) >= 2]
    return any(w in re.findall(r"\w+", m) or (any(c.isdigit() for c in w) and w in pegado)
               for w in toks)


def test_ninguna_ficha_rompe_los_invariantes(tab):
    rng = random.Random(23092026)
    cat = M.catalogo()
    ids_catalogo = {p["id"] for p in cat}
    por_id = {p["id"]: p for p in cat}
    turnos = violaciones = 0
    fallas = []
    cuenta = {"ids": 0, "memoria": 0, "repregunta": 0, "precio": 0,
              "propone": 0}
    for _charla in range(300):
        estado = M.estado_nuevo()
        # LA CIFRA VALE SI LA DIJO EN CUALQUIER TURNO DE LA CHARLA: "de esos
        # el mas barato" hereda el techo que puso antes, y eso es memoria.
        cifras = set()
        antes = {"accion": None}
        for _t in range(4):
            a, b = rng.sample(cat, 2)
            texto = rng.choice(_MENSAJES).format(
                p=f"{a['marca']} {a['modelo']}", q=b["modelo"],
                r=a["categoria"], m=b["marca"], n=rng.randint(10, 900),
                n2=rng.randint(900, 2000))
            ficha = _ficha_mala(rng, texto, tab, cat, a)
            vistos = {i for lista in estado["listas"] for it in lista
                      for i in it["ids"]} | {
                i for it in estado["foco"] for i in it["ids"]}
            r, estado = M.turno(texto, estado, tab, lambda _t, _f=ficha: _f)
            turnos += 1
            pedido = r["pedido"]
            cifras |= set(C._cifras(texto))
            cuenta["repregunta"] += bool(pedido.get("repreguntar"))
            cuenta["memoria"] += any(set(c.get("ids") or []) & vistos
                                     for c in pedido["consultas"])
            cuenta["ids"] += any(c.get("ids") for c in pedido["consultas"])
            cuenta["precio"] += any(x.get("campo") == "precio_ars"
                                    for c in pedido["consultas"]
                                    for x in c.get("condiciones") or [])
            for c in pedido["consultas"]:
                for i in c.get("ids") or []:
                    if i not in ids_catalogo:
                        fallas.append(f"id fuera del catalogo {i}: {texto}")
                    elif i not in vistos and not _escribio(por_id[i], texto):
                        fallas.append(f"id que no se mostro ni se dijo {i} "
                                      f"({por_id[i]['modelo']}): {texto}")
                for x in c.get("condiciones") or []:
                    if x.get("campo") == "precio_ars" and \
                            int(x.get("valor") or 0) not in cifras:
                        fallas.append(f"cifra inventada {x}: {texto}")
            com = pedido["comercial"]
            cuenta["propone"] += com["accion"] == "proponer"
            if com["accion"] == "confirmado" and (
                    antes["accion"] != "proponer"
                    or com["items"] != antes["items"]):
                fallas.append(f"confirmado sin propuesta: {texto}")
            for ids, _n in com["items"]:
                if not set(ids) <= ids_catalogo:
                    fallas.append(f"item comercial fuera del catalogo {ids}")
            antes = com
            for rep in pedido.get("repreguntar") or []:
                for i in rep.get("opciones") or []:
                    if i not in ids_catalogo:
                        fallas.append(f"opcion fuera del catalogo {i}")
            violaciones = len(fallas)
    # SOBRE CUANTOS CASOS PASO (regla 10.6): los caminos que importan se
    # recorrieron de verdad, no solo los turnos vacios.
    print(cuenta)
    assert turnos == 1200
    assert cuenta["ids"] >= 60 and cuenta["memoria"] >= 15
    assert cuenta["repregunta"] >= 30 and cuenta["precio"] >= 20
    assert cuenta["propone"] >= 8
    assert violaciones == 0, "\n".join(fallas)


def _un_turno(tab, texto, **parte):
    p = {"dice": texto, "quiere": "precio", "origen": "tienda",
         "rubro": "ninguno", "producto": "", "criterios": [], "cantidad": 0,
         "destino": "", "refiere": "no", "posiciones": [], "para": ""}
    p.update(parte)
    ficha = {"partes": [p], "afirma": [], "reescrita": texto,
             "criterios_generales": [], "reparto": []}
    r, _ = M.turno(texto, M.estado_nuevo(), tab, lambda _t: ficha)
    return r["pedido"]


def test_un_rubro_equivocado_del_modelo_repregunta_y_no_elige(tab):
    """"La samsung" anotada como notebook: Samsung no tiene notebooks. Se
    mira todo el catalogo y se repregunta, en vez de contestar nada."""
    p = _un_turno(tab, "cuanto sale la samsung?", rubro="notebook",
                  producto="samsung")
    assert p.get("repreguntar")
    assert not any(c.get("ids") for c in p["consultas"])


def test_el_catalogo_entero_nunca_certifica_un_producto(tab):
    """"logitec k 120" en teclados: la busqueda en todo el catalogo daba un
    cooler por seguro. Afuera del rubro solo se pregunta."""
    p = _un_turno(tab, "precio del teclao logitec k 120", rubro="teclado",
                  producto="logitec k 120")
    for c in p["consultas"]:
        assert not any(i.startswith("COO") for i in c.get("ids") or [])

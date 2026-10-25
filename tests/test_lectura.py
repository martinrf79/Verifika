"""LA LECTURA DE LOS DOS EJES Y SU PASO A LA AGENDA — sin modelo (25-oct-2026, FICHA 81).

Reemplaza a `test_ficha.py`: la ficha nativa salio del camino vivo, y su requisito cambio con el ok de Martin.

  1. la bateria: las lecturas grabadas de `banco_pruebas/primera_ejes/sueltos_cob_rep0.jsonl`, con su segunda vuelta,
     por el adaptador y el ejecutor de verdad. Las 48, por el pedido que queda con la vara de `medir_ficha`; las 58, por
     las casillas de lo que lee el cliente. El techo solo baja.
  2. cada forma normal y cada definicion del adaptador, por su clase: lo que define, no un caso.
  3. la cobertura: la frase que se pierde se marca; la que va en "todo" no.
  4. lo que la tienda tiene y lo que no, que dice el codigo con cualquier lectura.
"""
import asyncio
import json
import os
import sys

import pytest

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(AQUI)
DOC = os.path.join(REPO, "banco_pruebas", "pedido_documento")
GRABADAS = os.path.join(REPO, "banco_pruebas", "primera_ejes", "sueltos_cob_rep0.jsonl")
TECHO = os.path.join(AQUI, "lectura_techo.json")
TIENDA = "verifika_prod"


@pytest.fixture(scope="module")
def M():
    cwd = os.getcwd()
    sys.path.insert(0, DOC)
    import medir_pedido
    os.chdir(cwd)
    return medir_pedido


@pytest.fixture(scope="module")
def L(M):
    from app.core.flujo import lectura
    return lectura


def _grabadas() -> dict:
    return {(r["fuente"], r["id"]): r for r in map(json.loads, open(GRABADAS, encoding="utf-8")) if r.get("salida")}


def _estado(renglones=(), mostrados=()):
    from app.core.flujo import borrador as B
    from app.core.flujo import catalogo as K
    bo = B.leer({})
    for i, (que, cant, dest) in enumerate(renglones, 1):
        bo["renglones"].append({"L": f"L-{i}", "que": que, "cantidad": cant, "color": "", "destino": dest,
                                "condicion": "", "cita": "", "confirmado": True})
    bo["siguiente"] = len(bo["renglones"]) + 1
    ms = [{"id": pid, "nombre": K.por_id(pid, TIENDA)["nombre"], "precio": 0} for pid in mostrados]
    return {"mostrados": ms, "pedido": [], "busqueda": {}, "abiertas": [], "borrador": bo}


def _p(hace, sobre, que="", **k):
    return {"cliente": "", "hace": hace, "sobre": sobre, "que": que, **k}


def _salida(*partes, **todo):
    return {"partes": list(partes), "todo": todo}


def _acciones(agenda):
    return [(p["accion"], p.get("rubro") or p.get("tema") or p.get("destino") or p.get("producto") or p.get("que") or "")
            for p in agenda["preguntas"]]


# ══ 1. LA BATERIA ════════════════════════════════════════════════════════════

def test_las_lecturas_grabadas_dejan_el_pedido_bien(M, L):
    from fichas import CHARLAS
    from experimento import limpio
    g = _grabadas()
    cuenta, malas = {"BIEN": 0, "DUDO": 0, "MAL SIN AVISAR": 0}, []
    for ch in CHARLAS:
        for i, tu in enumerate(ch["turnos"]):
            salida = g[("48", f"{ch['id']} t{i}")]["salida"]

            async def agenda_de(msg, historial, estado, _s=salida):
                return L.a_agenda(_s, estado, TIENDA, msg)
            r = asyncio.run(M.turno(tu, agenda_de))
            c = M.M.calificar(tu, json.dumps(r["ficha"], ensure_ascii=False))
            cuenta[c["veredicto"]] += 1
            if c["veredicto"] != "BIEN":
                malas.append(f"{ch['id']} t{i} {c['veredicto']}: {c['fallas']}")
    techo = json.load(open(TECHO, encoding="utf-8"))
    print(f"\nLECTURA, LAS 48: {cuenta['BIEN']} de {sum(cuenta.values())} bien, {cuenta['DUDO']} con duda, "
          f"{cuenta['MAL SIN AVISAR']} mal sin avisar; techo {techo['no_bien_48']} y {techo['mal_sin_avisar_48']}")
    assert cuenta["DUDO"] + cuenta["MAL SIN AVISAR"] <= techo["no_bien_48"], "\n".join(malas)
    assert cuenta["MAL SIN AVISAR"] <= techo["mal_sin_avisar_48"], "\n".join(malas)


def test_las_lecturas_grabadas_responden_las_58(L):
    from banco_pruebas import cableado58 as C58
    from banco_pruebas.agendas58 import AGENDAS, EXPLICAR
    from app.core import llm_reintento
    puerta = llm_reintento._cliente
    g = _grabadas()
    turnos = {f"{r['charla']} t{r['turno']}": r for r in
              map(json.loads, open(os.path.join(REPO, "banco_pruebas", "vara_dato_58.jsonl"), encoding="utf-8"))}
    interp = C58.instalar()
    malos, total = [], 0
    try:
        for ch in C58.charlas():
            ags = list(AGENDAS.get(ch["id"]) or [])
            for i in range(len(ags)):
                cid = f"{ch['id']} t{i}"
                if not ch["turnos"][i]["casillas"] or ("58", cid) not in g:
                    continue
                ag = L.a_agenda(g[("58", cid)]["salida"], turnos[cid]["estado"], TIENDA, turnos[cid]["msg"])
                r = C58.correr({**ch, "turnos": ch["turnos"][:i + 1]}, ags[:i] + [ag], interp, EXPLICAR)
                total += 1
                if not all(v is True for _, v in r[-1]["casillas"]):
                    malos.append(cid)
    finally:
        llm_reintento._cliente = puerta
    techo = json.load(open(TECHO, encoding="utf-8"))["mal_58"]
    print(f"\nLECTURA, LAS 58 SUELTAS: {total - len(malos)} de {total} con sus casillas; techo de las mal {techo}")
    assert len(malos) <= techo, malos


# ══ 2. LA FORMA NORMAL Y LAS DEFINICIONES ════════════════════════════════════

def test_el_cruce_lleva_cada_par_a_una_accion(L):
    assert L.cruce("pide_ver", "rubro") == "buscar" and L.cruce("pregunta", "producto") == "producto"
    assert L.cruce("pregunta", "producto", con=True) == "compatibilidad" and L.cruce("pregunta", "lugar") == "envio"
    assert L.cruce("elige", "producto") == "comprar" and L.cruce("elige", "pago") == "cuenta"
    assert L.cruce("pregunta", "tema") == "politica" and L.cruce("pregunta", "tecnologia") == "explicar"


def test_un_lugar_suelto_reparte_lo_pedido(L):
    """"Dos teclados y dos mouse; un envio a Cordoba y otro a Rio Tercero": los lugares sueltos son el reparto."""
    s, reglas = L.normalizar(_salida(_p("pide_ver", "rubro", "teclado", rubro="teclado", cantidad=2),
                                     _p("pide_ver", "rubro", "mouse", rubro="mouse", cantidad=2),
                                     _p("elige", "lugar", "Cordoba", destino="Cordoba"),
                                     _p("elige", "lugar", "Rio Tercero", destino="Rio Tercero")), TIENDA)
    assert "reparto_de_lugares" in reglas and "ver_con_destino" in reglas
    assert [(p["hace"], p["que"], p["cantidad"], p["destino"]) for p in s["partes"]] == [
        ("elige", "teclado", 1, "Cordoba"), ("elige", "teclado", 1, "Rio Tercero"),
        ("elige", "mouse", 1, "Cordoba"), ("elige", "mouse", 1, "Rio Tercero")]


def test_el_reparto_va_por_la_cantidad_de_cada_lugar(L):
    """"Tres teclados; dos van a Rosario y uno a Neuquen"."""
    s, _ = L.normalizar(_salida(_p("pide_ver", "rubro", "teclado", rubro="teclado", cantidad=3),
                                _p("elige", "pedido", "dos sobrinos", cantidad=2, destino="Rosario"),
                                _p("elige", "pedido", "un sobrino", cantidad=1, destino="Neuquen")), TIENDA)
    assert [(p["cantidad"], p["destino"]) for p in s["partes"]] == [(2, "Rosario"), (1, "Neuquen")]


def test_dos_rubros_en_una_parte_son_dos_partes(L):
    s, _ = L.normalizar(_salida(_p("elige", "rubro", "mouse y teclado", rubro="mouse", destino="Rosario")), TIENDA)
    assert [(p["que"], p["destino"]) for p in s["partes"]] == [("mouse", "Rosario"), ("teclado", "Rosario")]


def test_un_destino_con_dos_lugares_reparte_la_cantidad(L):
    s, _ = L.normalizar(_salida(_p("pide_ver", "rubro", "parlante", rubro="parlante", cantidad=2,
                                   destino="Ushuaia y Salta")), TIENDA)
    assert [(p["cantidad"], p["destino"], p["hace"]) for p in s["partes"]] == [(1, "Ushuaia", "elige"),
                                                                                (1, "Salta", "elige")]


def test_una_parte_repetida_se_cuenta_una_vez(L):
    s, _ = L.normalizar(_salida(_p("cambia", "pedido", "L-1", cantidad=2), _p("cambia", "pedido", "L-1", cantidad=2)),
                        TIENDA)
    assert len(s["partes"]) == 1


def test_el_color_en_plural_es_el_de_la_tienda_y_la_condicion_sin_es(L):
    p = L._definir({"variante": "negros", "si_cumple": "es inalambrico"}, TIENDA)
    assert p == {"variante": "negro", "si_cumple": "inalambrico"}


def test_sacar_si_pasa_un_monto_es_el_tope_con_lo_que_sale(L):
    ag = L.a_agenda(_salida(_p("elige", "producto", "MX Master 3S", variante="negro"),
                            _p("saca", "producto", "MX Master 3S", si_cumple="pasa de 300 mil")), _estado(), TIENDA,
                    "sumame un MX Master 3S negro, si pasa de 300 mil saca el MX")
    cuenta = next(p for p in ag["preguntas"] if p["accion"] == "cuenta")
    assert cuenta["tope"] == 300000 and cuenta["si_pasa"] == "MX Master 3S"


def test_cambiar_el_destino_sin_pedido_cotiza_el_lugar_nuevo(L):
    ag = L.a_agenda(_salida(_p("cambia", "pedido", "G203", destino="Cordoba")), _estado(), TIENDA, "era para Cordoba")
    assert _acciones(ag) == [("envio", "Cordoba")]


def test_que_le_sirve_de_un_rubro_a_lo_suyo_es_compatibilidad(L):
    ag = L.a_agenda(_salida(_p("pregunta", "tecnologia", "memoria ram", rubro="memoria ram", con="notebook")),
                    _estado(), TIENDA, "tengo una notebook, que memoria ram le sirve?")
    p = ag["preguntas"][0]
    assert p["accion"] == "compatibilidad" and p["con"] == "notebook" and p["falta_modelo"] is True


def test_el_precio_con_destino_tambien_es_el_envio(L):
    ag = L.a_agenda(_salida(_p("pregunta", "producto", "G203", destino="Posadas", quiere_saber="precio con envio")),
                    _estado(), TIENDA, "cuanto me sale el G203 con envio?")
    assert _acciones(ag) == [("producto", "G203"), ("envio", "Posadas")]
    assert ag["preguntas"][0]["quiere_saber"] == "precio"


def test_elegir_lo_que_ya_esta_en_el_pedido_cambia_su_cantidad(L):
    from app.core.flujo import catalogo as K
    pid = str(K.identificar("K120", "negro", TIENDA)["producto"]["id"])
    estado = _estado([("K120 negro", 1, "")], [pid])
    ag = L.a_agenda(_salida(_p("elige", "mostrado", "M-1", cantidad=3)), estado, TIENDA, "sumame 3 de esos")
    assert [p.get("cambia") for p in ag["preguntas"] if p["accion"] == "comprar"] == [[{"es": "L-1", "cantidad": 3}]]


def test_un_renglon_repartido_en_dos_destinos_sale_y_entra_repartido(L):
    """"Que sean tres: uno a Tandil y los otros a CABA", con un renglon de teclados."""
    ag = L.a_agenda(_salida(_p("elige", "producto", "L-1", cantidad=1, destino="Tandil"),
                            _p("elige", "producto", "L-1", cantidad=2, destino="CABA")),
                    _estado([("teclado", 2, "")]), TIENDA, "uno a Tandil y los otros a CABA")
    compra = next(p for p in ag["preguntas"] if p["accion"] == "comprar")
    assert compra["saca"] == ["L-1"]
    assert [(a["producto"], a["cantidad"], a["destino"]) for a in compra["agrega"]] == [("teclado", 1, "Tandil"),
                                                                                        ("teclado", 2, "CABA")]


def test_la_compra_que_depende_de_una_pregunta_lleva_su_condicion(L):
    ag = L.a_agenda(_salida(_p("pregunta", "producto", "G305", con="Mac"),
                            _p("elige", "producto", "G305", depende_de=1, vale_si="si")), _estado(), TIENDA,
                    "si el G305 anda con Mac, me lo llevo")
    compra = next(p for p in ag["preguntas"] if p["accion"] == "comprar")
    assert compra["si"] == {"de": 1, "da": "si"}


def test_el_modelo_de_lenguaje_no_elige_productos(L):
    """Un modelo que el cliente no nombro ni leyo no entra: con un orden, lo elige el codigo en el rubro."""
    ag = L.a_agenda(_salida(_p("elige", "producto", "Teclado Logitech G915", rubro="teclado", orden="mas caro")),
                    _estado(), TIENDA, "el mejor teclado que tengas")
    compra = next(p for p in ag["preguntas"] if p["accion"] == "comprar")
    assert compra["agrega"][0]["producto"] == "teclado"
    assert any(p["accion"] == "buscar" and p["orden"] == "mas caro" for p in ag["preguntas"])


# ══ 3. LA COBERTURA ══════════════════════════════════════════════════════════

def test_la_frase_perdida_se_marca_y_la_de_todo_no(L):
    msg = "Necesito tres mouse. Dos mouse van a Rosario, el resto a Neuquen. Pago por transferencia"
    salida = _salida(_p("pide_ver", "rubro", "mouse", rubro="mouse", cantidad=3, destino="Rosario"),
                     pago=[{"medio": "transferencia", "porcentaje": 100}])
    assert L.sin_cubrir(msg, salida, TIENDA) == ["Dos mouse van a Rosario, el resto a Neuquen"]


def test_sin_nada_que_falte_no_hay_segunda_vuelta(L):
    async def pedir(*a, **k):
        raise AssertionError("no tenia que llamar al modelo")
    salida = _salida(_p("pregunta", "producto", "G305"))
    assert asyncio.run(L.releer("cuanto sale el G305?", [], _estado(), salida, TIENDA, pedir)) == (salida, False)


# ══ 4. LO QUE LA TIENDA TIENE Y LO QUE NO: lo dice el codigo ════════════════

def _responde(preguntas: list) -> str:
    from app.core.flujo import estado as E, redaccion
    from app.core.flujo.ejecutor import ejecutar
    for i, p in enumerate(preguntas, 1):
        p.setdefault("n", i)
        p.setdefault("cita", "x")
    t = ejecutar({"preguntas": preguntas}, E.leer({}), TIENDA, explicar=lambda q: "")
    return redaccion.texto(t.hechos, t.preguntas, False)


@pytest.mark.parametrize("pregunta, dice", [
    ("peso", "Peso: 139 gramos"),                      # un campo arriba de todo, no en las specs
    ("de que material es", "Material: Plastico ABS"),
    ("garantia", "Garantia: 24 meses"),                 # dos campos empatan: el de respuesta directa
    ("si es resistente al agua", "no es resistente al agua"),
    ("cuanto dura la carga", "Bateria:"),               # por la frase del alias de la tienda
])
def test_cada_campo_del_catalogo_es_un_dato(M, pregunta, dice):
    assert dice in _responde([{"accion": "producto", "producto": "G305", "quiere_saber": pregunta}])


@pytest.mark.parametrize("pregunta", ["cuanto consume en watts", "que temperatura soporta"])
def test_lo_que_no_esta_en_la_ficha_lo_dice_el_codigo(M, pregunta):
    t = _responde([{"accion": "producto", "producto": "G305", "quiere_saber": pregunta}])
    assert f"No tengo el dato de {pregunta}" in t


def test_un_tema_que_la_faq_no_tiene_no_se_adivina(M):
    """"Instalacion a domicilio" encontraba por parecido la regla de cambio de direccion."""
    assert _responde([{"accion": "politica", "tema": "instalacion a domicilio"}]) == \
        "Sobre eso no tengo información escrita."


def test_lo_que_la_tienda_no_vende_no_trae_otra_cosa(M):
    assert _responde([{"accion": "buscar", "rubro": "toda la tienda", "condiciones": ["drones"]}]) == \
        "No tengo drones en la tienda."


def test_la_duda_pasa_el_control_del_vendedor():
    """Lo que dice el vendedor sale al cliente solo sin montos ni productos que no esten a la vista."""
    from app.core.flujo import interprete
    assert interprete.controlar("¿Para cuantas personas es?", "", TIENDA)
    assert not interprete.controlar("¿Te sirve el G305 a $80.500?", "", TIENDA)

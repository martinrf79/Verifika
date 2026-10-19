"""LO QUE RECIBE EL INTERPRETE — la agenda, el marcador y la libreta, sin modelo (20-oct-2026).

Antes de gastar una corrida con el modelo se prueba gratis lo que le damos:
  1. el contrato: los seis ejemplos de la consigna cumplen la agenda, y el control ve lo que falta;
  2. el peso: lo que recibe el modelo en cada turno de las 58 y las K entra en tres mil tokens;
  3. la suficiencia: cada dato de la agenda escrita a mano sale de lo que el modelo ve en ese turno. Lo que no, lo
     tendria que adivinar, y eso se arregla en el marcador o en la libreta, no en la consigna. El techo solo baja.
"""
import json
import os
import re

import pytest

from banco_pruebas import cableado58 as CB
from banco_pruebas import suficiencia as S
from banco_pruebas.agendas58 import AGENDAS

TECHO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "suficiencia_techo.json")
TIENDA = "verifika_prod"


@pytest.fixture(scope="module")
def vistas():
    from app.core import llm_reintento
    puerta = llm_reintento._cliente
    v = S.vistas()
    yield v
    llm_reintento._cliente = puerta


def test_los_seis_ejemplos_cumplen_el_contrato():
    from app.core.flujo import agenda as A, interprete as I
    for libreta, mensaje, _, salida in I.EJEMPLOS:
        assert A.faltas(mensaje, salida, set(re.findall(r"\b[MLR]-\d+\b", libreta))) == [], mensaje
    print(f"\nEJEMPLOS: {len(I.EJEMPLOS)} de {len(I.EJEMPLOS)} cumplen la agenda")


def test_el_control_ve_lo_que_falta():
    from app.core.flujo import agenda as A
    mensaje = "tenes el G305? y hacen factura A?"
    bien = {"preguntas": [{"n": 1, "cita": "tenes el G305?", "accion": "producto", "producto": "G305"},
                          {"n": 2, "cita": "y hacen factura A?", "accion": "politica", "tema": "factura"}]}
    assert A.faltas(mensaje, bien, set()) == []
    sin_la_segunda = {"preguntas": bien["preguntas"][:1]}
    assert any("factura" in f for f in A.faltas(mensaje, sin_la_segunda, set()))
    fuera_del_menu = {"preguntas": [{**bien["preguntas"][0], "accion": "responder"}, bien["preguntas"][1]]}
    assert any("menu" in f for f in A.faltas(mensaje, fuera_del_menu, set()))
    sin_dato = {"preguntas": [{**bien["preguntas"][0], "producto": ""}, bien["preguntas"][1]]}
    assert any("producto" in f for f in A.faltas(mensaje, sin_dato, set()))
    fuera_de_la_libreta = {"preguntas": [{**bien["preguntas"][0], "producto": "M-3"}, bien["preguntas"][1]]}
    assert any("M-3" in f for f in A.faltas(mensaje, fuera_de_la_libreta, {"M-1", "M-2"}))
    depende_de_nada = {"preguntas": [bien["preguntas"][0], {**bien["preguntas"][1], "si": {"de": 7, "da": "si"}}]}
    assert any("7" in f for f in A.faltas(mensaje, depende_de_nada, set()))


def test_el_candado_no_deja_una_pregunta_sin_estado():
    """Una pregunta que el ejecutor no puede cumplir no se pierde en silencio: se repregunta con su cita."""
    from app.core.flujo import estado as E
    from app.core.flujo.ejecutor import ejecutar
    t = ejecutar({"preguntas": [{"n": 1, "cita": "y me lo envolves para regalo?", "accion": "envolver"}]},
                 E.leer({}), TIENDA)
    assert t.estados == {1: "sin_estado"}
    assert any("y me lo envolves para regalo?" in q for q in t.preguntas), t.preguntas


def test_una_agenda_a_mano_por_turno_y_dentro_del_menu():
    from app.core.flujo import agenda as A
    charlas = CB.charlas()
    preguntas = 0
    for c in charlas:
        assert len(AGENDAS[c["id"]]) == len(c["turnos"]), c["id"]
        for ag in AGENDAS[c["id"]]:
            for p in A.preguntas(ag):
                preguntas += 1
                assert p["accion"] in A.ACCIONES, (c["id"], p)
                if p["accion"] in A.OBLIGATORIO:
                    assert p.get(A.OBLIGATORIO[p["accion"]]), (c["id"], p)
    print(f"\nAGENDAS: {len(charlas)} charlas, {sum(len(c['turnos']) for c in charlas)} turnos, {preguntas} preguntas")


def test_el_marcador_reconoce_lo_de_la_tienda_y_no_inventa():
    from banco_pruebas import clon_produccion as C
    C.preparar_entorno()
    C.instalar()
    from app.core.flujo import marcador
    casos = [
        ("dos memorias y un mouse", ['"memorias" es el rubro memoria ram', '"mouse" es el rubro mouse']),
        ("tenes el G305?", ['"g305" es el producto Mouse Logitech G305 Lightspeed']),
        ("divide en setenta treinta", ["70 y 30 por ciento"]),
        ("mitad transferencia y mitad mercado pago", ["50 y 50 por ciento"]),
        ("si pasa de 300 mil saca el MX", ["300.000 pesos"]),
        ("hacen factura A?", ["el tema factura"]),
        ("tienen 50 off, no?", ["el tema promociones"]),
        ("aceptan tarjeta de debito?", ["el tema formas_pago"]),
    ]
    for mensaje, esperado in casos:
        t = marcador.tabla(mensaje, TIENDA)
        assert all(e in t for e in esperado), (mensaje, t)
    # Una busqueda no es un producto, y un monto tampoco.
    for mensaje in ("quiero un mouse inalambrico, preferentemente Logitech", "una notebook por menos de 200 mil"):
        assert "el producto" not in marcador.tabla(mensaje, TIENDA), mensaje
    print(f"\nMARCADOR: {len(casos) + 2} casos")


def test_lo_que_recibe_el_modelo_entra_en_tres_mil_tokens(vistas):
    from app.core.flujo import interprete as I
    pesos = [(sum(len(m["content"].encode()) for m in I.mensajes(msj, h, e, TIENDA)) // 4, cid, t + 1)
             for cid, t, msj, e, h in vistas]
    mayor = max(pesos)
    assert mayor[0] <= 3000, f"{mayor[1]} T{mayor[2]}: {mayor[0]} tokens"
    print(f"\nPESO: {len(pesos)} turnos, el mayor {mayor[0]} tokens en {mayor[1]} T{mayor[2]}, "
          f"el promedio {sum(p[0] for p in pesos) // len(pesos)}")


def test_lo_que_recibe_el_modelo_alcanza(vistas):
    from banco_pruebas.agendas58 import AGENDAS as G
    faltas = [(cid, t + 1, *f) for cid, t, msj, e, h in vistas
              for f in S.faltas(G[cid][t], msj, e, h, TIENDA)]
    techo = json.load(open(TECHO, encoding="utf-8"))["datos_a_adivinar"]
    detalle = "\n".join(f"{f[0]} T{f[1]} pregunta {f[2]}: {f[3]}, {f[4]}" for f in faltas)
    assert len(faltas) <= techo, f"{len(faltas)} datos a adivinar contra un techo de {techo}:\n{detalle}"
    preguntas = sum(len(G[cid][t]["preguntas"]) for cid, t, *_ in vistas)
    print(f"\nSUFICIENCIA: {preguntas - len({(f[0], f[1], f[2]) for f in faltas})} de {preguntas} preguntas con todo "
          f"lo que necesitan a la vista; {len(faltas)} datos a adivinar, techo {techo}\n{detalle}")

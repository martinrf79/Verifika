"""LA FORMA NORMAL — lo que dijo el modelo, en la forma que el ejecutor cumple (21-oct-2026, FICHA 74).

Dos candados:
  cada regla   una agenda como la escriben los modelos, y la forma en que queda; y una que la regla no toca.
  el piso      las traducciones grabadas del modelo de produccion en las 525 de `traduccion58`, pasadas por el flujo
               vivo con el codigo de hoy y calificadas con la vara: `banco_pruebas/forma_normal/regrado.py`. Grabado
               dio 455; con la forma normal, 506. Sin modelo.
"""
import pytest

from banco_pruebas import cableado58 as R

PISO_PRODUCCION = 506


@pytest.fixture(scope="module")
def tienda():
    from app.core import llm_reintento
    puerta = llm_reintento._cliente
    R.instalar()
    yield "verifika_prod"
    llm_reintento._cliente = puerta


def _estado(**kw):
    from app.core.flujo.estado import VACIO
    import copy
    e = copy.deepcopy(VACIO)
    e.update(kw)
    return e


def _normal(agenda, estado, tienda):
    from app.core.flujo import interprete
    from app.core.flujo.normal import normalizar
    ag, reglas = normalizar({"preguntas": agenda}, estado, tienda, interprete.numeros(estado))
    return [{k: v for k, v in p.items() if k not in ("n", "cita")} for p in ag["preguntas"]], reglas


def _pedido_completo(tienda):
    """Un borrador de un renglon resuelto, y su pedido derivado."""
    from app.core.flujo import borrador as B
    b = B.leer({})
    B.aplicar(b, {"agrega": [{"producto": "G203", "color": "negro", "cantidad": 1, "destino": "Rosario"}]})
    b["renglones"][0]["confirmado"] = True
    res = B.resolver(b, tienda)
    return _estado(borrador=b, pedido=B.articulos(res, B.faltantes(b, res)))


def test_un_si_sin_efecto_con_el_pedido_completo_es_la_cuenta(tienda):
    e = _pedido_completo(tienda)
    assert e["pedido"]
    for agenda in ([{"accion": "comprar", "confirma": ["L-1"]}], [{"accion": "comprar", "acepta": []}],
                   [{"accion": "otro", "que": "dato"}]):
        assert _normal(agenda, e, tienda) == ([{"accion": "cuenta"}], ["si_sin_efecto"])
    # Un si que cambia algo, o un dato con datos del cliente, no.
    assert _normal([{"accion": "comprar", "cambia": [{"es": "L-1", "cantidad": 2}]}], e, tienda)[1] == []
    assert _normal([{"accion": "otro", "que": "saludo"}], e, tienda)[1] == []


def test_precio_y_envio_sin_pedido_suman(tienda):
    out, reglas = _normal([{"accion": "producto", "producto": "G203", "quiere_saber": "precio"},
                           {"accion": "envio", "destino": "Posadas"}], _estado(), tienda)
    assert reglas == ["precio_con_envio"] and out[-1] == {"accion": "cuenta"}
    assert _normal([{"accion": "producto", "producto": "G203", "quiere_saber": "inalambrico"},
                    {"accion": "envio", "destino": "Posadas"}], _estado(), tienda)[1] == []


def test_la_regla_de_envios_con_un_lugar_es_un_envio_por_lugar(tienda):
    out, reglas = _normal([{"accion": "politica", "tema": "costo_envio", "cita": "cuanto sale el envio a Posadas?"}],
                          _estado(), tienda)
    assert out == [{"accion": "envio", "destino": "Posadas"}]
    out, _ = _normal([{"accion": "envio", "destino": "Rosario y Mendoza"}], _estado(), tienda)
    assert out == [{"accion": "envio", "destino": "Rosario"}, {"accion": "envio", "destino": "Mendoza"}]
    # Una ciudad con su provincia es un lugar; sin lugar, la politica queda.
    assert _normal([{"accion": "envio", "destino": "Posadas, Misiones"}], _estado(), tienda)[1] == []
    assert _normal([{"accion": "politica", "tema": "costo_envio", "cita": "hacen envios?"}], _estado(), tienda)[1] == []


def test_la_regla_de_envios_sin_lugar_usa_el_del_cliente(tienda):
    from app.core.flujo import borrador as B
    b = B.leer({})
    b["cliente"]["localidad"] = "Posadas"
    out, _ = _normal([{"accion": "politica", "tema": "costo_envio", "cita": "con envio?"}], _estado(borrador=b), tienda)
    assert out == [{"accion": "envio", "destino": "Posadas"}]


def test_un_destino_en_el_mensaje_es_el_del_pedido_sin_destino(tienda):
    out, reglas = _normal([{"accion": "buscar", "rubro": "mouse", "cantidad": 2, "orden": "mas barato"},
                           {"accion": "comprar", "agrega": [{"producto": "mouse", "cantidad": 2}]},
                           {"accion": "envio", "destino": "Cordoba"}], _estado(), tienda)
    assert "un_destino_para_el_pedido" in reglas and out[1]["agrega"][0]["destino"] == "Cordoba"


def test_la_cuenta_de_lo_buscado_o_lo_nombrado_entra_al_pedido(tienda):
    out, reglas = _normal([{"accion": "buscar", "rubro": "mouse", "cantidad": 2, "orden": "mas barato"},
                           {"accion": "cuenta"}, {"accion": "envio", "destino": "Cordoba"}], _estado(), tienda)
    assert "cuenta_de_lo_buscado" in reglas
    assert out[1] == {"accion": "comprar", "agrega": [{"producto": "mouse", "cantidad": 2, "destino": "Cordoba"}]}
    out, reglas = _normal([{"accion": "producto", "producto": "G305", "color": "negro", "cantidad": 2},
                           {"accion": "cuenta"}], _estado(), tienda)
    assert reglas == ["cuenta_de_lo_nombrado"]
    assert out[1] == {"accion": "comprar", "agrega": [{"producto": "G305", "cantidad": 2, "color": "negro"}]}


def test_la_garantia_de_un_producto_nombrado_es_su_dato(tienda):
    out, reglas = _normal([{"accion": "politica", "tema": "garantia_como_usar", "cita": "el G305 tiene garantia?"}],
                          _estado(), tienda)
    assert reglas == ["dato_del_producto"] and out[0]["accion"] == "producto" and out[0]["quiere_saber"] == "garantia"
    assert _normal([{"accion": "politica", "tema": "garantia", "cita": "que garantia tienen?"}], _estado(), tienda)[1] == []


def test_las_letras_de_la_libreta_dicen_la_operacion(tienda):
    e = _estado(mostrados=[{"id": "MOU0007", "nombre": "x", "precio": ""}])
    out, _ = _normal([{"accion": "comprar", "confirma": ["M-1"]}], e, tienda)
    assert out == [{"accion": "comprar", "confirma": [], "agrega": [{"producto": "M-1", "cantidad": 1}]}]
    out, _ = _normal([{"accion": "comprar", "cambia": [{"es": "M-1", "destino": "Cordoba"}]}], e, tienda)
    assert out == [{"accion": "envio", "destino": "Cordoba"}]
    p = _pedido_completo(tienda)
    out, _ = _normal([{"accion": "comprar", "agrega": [{"producto": "L-1", "destino": "Salta"}]}], p, tienda)
    assert out == [{"accion": "comprar", "agrega": [], "cambia": [{"es": "L-1", "destino": "Salta"}]}]


def test_un_color_que_la_tienda_no_tiene_no_es_un_cambio(tienda):
    p = _pedido_completo(tienda)
    out, reglas = _normal([{"accion": "comprar", "cambia": [{"es": "L-1", "color": "indistinto"}]},
                           {"accion": "cuenta"}], p, tienda)
    assert reglas == ["color_ajeno"] and out == [{"accion": "cuenta"}]
    assert _normal([{"accion": "comprar", "cambia": [{"es": "L-1", "color": "blanco"}]}], p, tienda)[1] == []


def test_la_compatibilidad_de_un_rubro_con_algo_que_no_es_equipo_es_una_busqueda(tienda):
    out, reglas = _normal([{"accion": "compatibilidad", "producto": "placa de video", "con": "fuente de 550 watts"}],
                          _estado(), tienda)
    assert out == [{"accion": "buscar", "rubro": "placa de video", "condiciones": ["fuente de 550 watts"],
                    "orden": "nada"}]
    # Con un equipo del vocabulario sigue siendo compatibilidad: "que memoria va en mi notebook".
    assert _normal([{"accion": "compatibilidad", "producto": "memoria ram", "con": "notebook"}], _estado(), tienda)[1] == []


def test_una_lista_con_un_dato_que_filtra_se_resuelve_por_el_dato(tienda):
    out, reglas = _normal([{"accion": "producto", "producto": ["G305", "G203"], "quiere_saber": "inalambrico"}],
                          _estado(), tienda)
    assert reglas == ["lista_con_dato"] and out == [{"accion": "producto", "producto": "G305",
                                                     "quiere_saber": "inalambrico", "ofrece": True}]
    # Lo mismo con lo mostrado, que es lo que trababa en vivo el 21-oct: "de esos, el que sea inalambrico".
    from app.core.flujo import catalogo as K
    e = _estado()
    e["mostrados"] = [{"id": str(p["id"]), "nombre": p["nombre"], "precio": ""} for p in K.productos(tienda)
                      if p.get("modelo") in ("G305 Lightspeed", "G203 Lightsync") and p.get("color") == "Negro"]
    out, _ = _normal([{"accion": "producto", "producto": ["M-1", "M-2"], "quiere_saber": "inalambrico"}], e, tienda)
    assert len(out) == 1 and out[0]["ofrece"]
    # Sin un dato que filtre, lo nombrado va uno por uno.
    out, _ = _normal([{"accion": "producto", "producto": ["G305", "G203"], "quiere_saber": "precio"}], _estado(), tienda)
    assert [p["producto"] for p in out] == ["G305", "G203"]


def test_un_rubro_que_la_cita_no_nombra_sale_de_la_agenda(tienda):
    out, reglas = _normal([{"accion": "buscar", "rubro": "mouse", "cita": "dos mouse"},
                           {"accion": "buscar", "rubro": "todos", "orden": "mas caro",
                            "cita": "el precio no seria tan importante"}], _estado(), tienda)
    assert reglas == ["rubro_inventado"] and len(out) == 1
    assert _normal([{"accion": "buscar", "rubro": "mouse", "cita": "un mouse"},
                    {"accion": "buscar", "rubro": "drones", "cita": "y drones tienen?"}], _estado(), tienda)[1] == []


def test_el_piso_de_las_traducciones_grabadas_de_produccion(tienda):
    from banco_pruebas.forma_normal import regrado
    res = regrado.correr(modelos=("prod",))
    bien = sum(r["bien"] for r in res.values())
    print(f"\nFORMA NORMAL: {bien} de {len(res)} traducciones grabadas de produccion salen bien; grabado, "
          f"{sum(r['antes'] for r in res.values())}")
    assert len(res) == 525
    assert bien >= PISO_PRODUCCION


@pytest.mark.parametrize("cid,n,texto,agenda", [
    ("C32", 0, "entre el G305 y el G203, dame el que sea inalambrico",
     [{"accion": "comprar", "agrega": [{"producto": ["G305", "G203"], "cantidad": 1}], "si_cumple": "inalambrico"}]),
    ("C56", 0, "tienen 50 off, no? entonces si el K120 negro sale menos de 10 mil llevo dos",
     [{"accion": "politica", "tema": "promociones", "afirma": "50% off"},
      {"accion": "comprar", "agrega": [{"producto": "K120", "color": "negro", "cantidad": 2}],
       "si_cumple": "menos de 10 mil"}]),
    ("C29", 0, "Me llevo el G305 si es compatible con Mac.",
     [{"accion": "comprar", "agrega": [{"producto": "G305", "cantidad": 1}], "si_cumple": "compatible con Mac"}]),
], ids=["el_que_cumple", "no_cumple_el_precio", "cumple_la_compatibilidad"])
def test_la_compra_con_condicion_la_juzga_el_codigo(tienda, cid, n, texto, agenda):
    """"si_cumple" en una compra: el codigo mira cada producto contra la condicion y lleva el que la cumple."""
    from banco_pruebas.forma_normal import regrado
    r = regrado.calificar(cid, n, texto, {"preguntas": [{"n": i, "cita": "", **p} for i, p in enumerate(agenda, 1)]})
    assert r["bien"], (r["malas"], r["respuesta"])


@pytest.mark.xfail(strict=True, reason="PLAN: el menu ofrece si_cumple, banco_pruebas/forma_normal/menu_si_cumple.patch. "
                                       "Entra cuando la cuota gratis de Gemini mida las 525 y las variantes sin bajar")
def test_el_menu_ofrece_la_compra_con_condicion():
    from app.core.flujo import agenda as A
    assert '"si_cumple"' in A.ACCIONES["comprar"]

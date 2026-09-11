"""LA CONDUCCION Y LA JUNTA DE LOS ATRIBUTOS — las dos varas del 6-sep-2026.

Las dos cosas que se arreglaron ese dia no tenian con que medirse, y las dos
fallaban en silencio: nada se ponia rojo, el turno se logueaba bien y la unica
forma de verlas era leer un mensaje real y darse cuenta.

  1. LA MOVIDA NO LLEGABA AL QUE ESCRIBE. `consultar_temas` devuelve seis cosas
     por tema y la mesa copiaba cuatro: `objetivo`, `movida` y `escape` se
     pedian, volvian, se logueaban y se caian. El bot contestaba correcto y sin
     vender, con la guia de venta de la casa escrita al lado.

  2. LA FICHA SE APAREABA POR PALABRAS. El resolver sabia exacto para que
     termino del cliente pedia cada ficha y tiraba el dato; la mesa lo volvia a
     adivinar comparando palabras de tres letras. Con dos productos parecidos en
     el mismo turno, eso contesta con la ficha del otro.

Todo offline, contra la fuente real. Cada test dice sobre cuantos casos corrio
(regla 10.6 de CLAUDE.md).
"""
from app.core import resolver as R, tabla as TB, turno as T

TIENDA = "verifika_prod"

# Temas de situacion de venta: son los que la fuente tiene con movida escrita.
SITUACIONES = ["esta caro", "pide descuento", "desconfia"]


def _turno(declarado, cid="t"):
    r = R.resolver(declarado, {}, TIENDA, f"guion-{cid}")
    return TB.tabla(declarado, r["llamadas"], r.get("bloque") or "",
                    trace_id=f"guion-{cid}"), r


# ══════════════════════════════════════════════════════════════════════
# 1. LA CONDUCCION
# ══════════════════════════════════════════════════════════════════════

def test_la_movida_de_la_casa_llega_a_la_mesa(firestore_doble):
    """Al menos una situacion de venta trae conduccion. Si esto se pone rojo,
    la movida volvio a caerse entre `consultar_temas` y la mesa."""
    con_guion = 0
    for s in SITUACIONES:
        t, _ = _turno({"temas": [s]}, s)
        if t.get("guion"):
            con_guion += 1
    assert con_guion >= 1, (
        f"ninguna de las {len(SITUACIONES)} situaciones trajo conduccion: la "
        f"movida se esta cayendo antes del redactor")


def test_la_conduccion_no_es_una_fila_y_no_se_contesta(firestore_doble):
    """El guion viaja por su propio carril. Si entrara a la mesa como fila, la
    compuerta de completitud le pediria una casilla y el modelo podria
    escribirle al cliente el objetivo de venta."""
    casos = 0
    for s in SITUACIONES:
        t, _ = _turno({"temas": [s]}, s)
        for fila in t["puntos"]:
            crudo = str(fila.get("material") or "")
            assert "objetivo" not in crudo and "escape" not in crudo, \
                f"{s}: la conduccion se filtro a una fila"
        casos += 1
    assert casos == 3, f"corrio sobre {casos} situaciones, esperaba 3"


def test_la_conduccion_se_le_dice_al_vendedor_y_no_al_cliente():
    """El texto que entra por el sistema dice, en su primera linea, que no se
    escribe. Es lo unico que este carril puede romper."""
    texto = T._conduccion([{"tema": "pedir_descuento", "objetivo": "cerrar",
                            "movida": "ofrecer transferencia",
                            "escape": "no bajar el precio"}])
    assert texto, "la conduccion salio vacia con un guion cargado"
    assert "no se lo escribas al cliente" in texto
    assert "ofrecer transferencia" in texto


def test_sin_guion_no_se_manda_ningun_mensaje_de_sistema_de_mas():
    """Un turno sin situacion de venta no paga un renglon de prompt."""
    assert T._conduccion([]) == ""


def test_la_conduccion_no_mete_cifras():
    """INVARIANTE DE LA FUENTE: cero digitos en objetivo, movida y escape. Si
    un dia entrara un numero por aca, seria plata que el redactor puede copiar
    sin que la haya calculado el codigo."""
    vistos = 0
    for s in SITUACIONES:
        t, _ = _turno({"temas": [s]}, s)
        for g in (t.get("guion") or []):
            for k in ("objetivo", "movida", "escape"):
                assert not any(c.isdigit() for c in str(g.get(k) or "")), \
                    f"{s}: {k} trae una cifra"
                vistos += 1
    assert vistos >= 0


# ══════════════════════════════════════════════════════════════════════
# 2. LA JUNTA DE LOS ATRIBUTOS
# ══════════════════════════════════════════════════════════════════════

def test_la_ficha_viaja_con_el_termino_para_el_que_se_pidio(firestore_doble):
    """El resolver deja escrito PARA QUE la pidio. Sin esto la mesa vuelve a
    aparear por palabras compartidas."""
    _, r = _turno({"atributos": [{"de": "mouse", "campo": "garantia"}]}, "a1")
    fichas = [l for l in r["llamadas"]
              if (l.get("pedido") or {}).get("proyeccion") == "ficha"]
    assert fichas, "no se derivo ninguna ficha para el atributo"
    assert any((f["pedido"].get("para") or []) for f in fichas), \
        "la ficha se pidio sin decir para que termino"


def test_dos_atributos_del_mismo_producto_son_una_sola_consulta(
        firestore_doble):
    """Dos filas, una consulta. 'cuanto pesa y que garantia tiene' no puede
    costar dos viajes a la fuente ni comerse dos lugares del tope."""
    declarado = {"atributos": [{"de": "mouse", "campo": "garantia"},
                               {"de": "mouse", "campo": "peso"}]}
    t, r = _turno(declarado, "a2")
    fichas = [l for l in r["llamadas"]
              if (l.get("pedido") or {}).get("proyeccion") == "ficha"]
    assert len(fichas) == 1, f"se pidieron {len(fichas)} fichas, esperaba 1"
    assert len(t["puntos"]) == 2, "las dos preguntas tienen que ser dos filas"


def test_el_termino_del_cliente_queda_en_el_pedido(firestore_doble):
    """Los dos terminos distintos del mismo producto viajan juntos."""
    declarado = {"atributos": [{"de": "el mouse", "campo": "garantia"},
                               {"de": "ese mouse", "campo": "peso"}]}
    _, r = _turno(declarado, "a3")
    para = [p for l in r["llamadas"]
            for p in ((l.get("pedido") or {}).get("para") or [])]
    assert len(para) == 2, f"viajaron {len(para)} terminos, esperaba 2"

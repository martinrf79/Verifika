"""LA TABLA DE PUNTOS — la mesa que ve la segunda llamada.

Todo corre offline, contra el catalogo y la FAQ reales del repo. Sin modelo, sin
clave, sin casetes: la entrada es el declarado escrito a mano y la salida se
compara contra la fuente.

Cada test dice sobre cuantos casos corrio (regla 10.6 de CLAUDE.md).
"""
import glob
import json

import pytest

from app.core import resolver as R, herramientas as H, tabla as TB
from app.core.tabla import puntos as PUNTOS

TIENDA = "verifika_prod"
ORO = sorted(glob.glob("tests/oro/capa2/*.json"))


def _turno(declarado, cid="t"):
    """El turno resuelto de verdad: se derivan las busquedas y se ejecutan
    contra la fuente. Lo unico escrito a mano es el declarado."""
    r = R.resolver(declarado, {}, TIENDA, f"tabla-{cid}")
    return TB.tabla(declarado, r["llamadas"], r.get("bloque") or ""), r


# ══════════════════════════════════════════════════════════════════════
# LA FORMA
# ══════════════════════════════════════════════════════════════════════

def test_hay_una_fila_por_punto_y_con_el_mismo_id(firestore_doble):
    """La tabla no inventa filas ni se come ninguna: los ids son exactamente
    los del indice, que salen de lo DECLARADO y no de lo buscado."""
    casos = 0
    for f in ORO:
        c = json.load(open(f))
        t, _ = _turno(c["declarado"], c["id"])
        esperados = [p["id"] for p in PUNTOS(c["declarado"])]
        assert [p["id"] for p in t["puntos"]] == esperados, c["id"]
        casos += 1
    assert casos == 40, f"corrio sobre {casos} casos, esperaba 40"


def test_cada_fila_dice_que_se_pregunto_y_en_que_estado_esta(firestore_doble):
    validos = {"con_material", "sin_material", "sellado", "pregunta"}
    filas = 0
    for f in ORO:
        c = json.load(open(f))
        t, _ = _turno(c["declarado"], c["id"])
        for p in t["puntos"]:
            assert p["pregunto"], f"{c['id']} {p['id']} sin texto de pregunta"
            assert p["estado"] in validos, f"{c['id']} {p['estado']}"
            assert isinstance(p["material"], list)
            filas += 1
    assert filas >= 90, f"solo se miraron {filas} filas"


# ══════════════════════════════════════════════════════════════════════
# LO QUE LA FUENTE NO DICE, NO VIAJA
# ══════════════════════════════════════════════════════════════════════

def test_un_dato_que_la_ficha_no_tiene_sale_vacio(firestore_doble):
    """EL CASO C4-01 CORTADO EN LA RAIZ. El modelo saco '8000 DPI' de su
    entrenamiento porque le llegaba la ficha ENTERA de un mouse que no declara
    dpi: tenia diecisiete campos de donde sacar un numero con pinta de spec.
    Con la tabla, el material de ese punto sale VACIO y no hay de donde."""
    declarado = {"items": [],
                 "atributos": [{"de": "el Genius DX-110", "campo": "dpi"}]}
    t, _ = _turno(declarado, "dpi")
    fila = t["puntos"][0]
    assert fila["material"] == [], f"viajo algo y no debia: {fila['material']}"
    assert fila["estado"] == "sin_material"


def test_el_dato_que_la_ficha_SI_tiene_viaja_solo_el(firestore_doble):
    """Y el reverso, que es la otra mitad de la vara: cuando el dato existe
    viaja, y viaja SOLO el. La garantia si, los otros dieciseis campos no."""
    declarado = {"items": [],
                 "atributos": [{"de": "el Genius DX-110", "campo": "garantia"}]}
    t, _ = _turno(declarado, "gar")
    fila = t["puntos"][0]
    assert fila["estado"] == "con_material", fila
    dato = fila["material"][0]
    assert "24" in str(dato), f"no vino la garantia real: {dato}"
    plano = json.dumps(fila["material"], ensure_ascii=False)
    for prohibido in ("dimensiones", "peso_gramos", "contenido_caja",
                      "uso_recomendado", "descripcion"):
        assert prohibido not in plano, f"viajo {prohibido} sin que lo pidieran"


def test_el_cliente_no_escribe_el_nombre_de_la_columna(firestore_doble):
    """'lector de huella digital' contra la clave `lector_huella`, y
    'cancelacion de ruido activa' contra `cancelacion_ruido`. No comparten
    prefijo: si el puente fuera solo por prefijo, la ficha se daria por vacia
    teniendo el dato, y el bot diria que no sabe algo que la fuente SI dice.

    Se prueba sobre la ficha real, sin pasar por la identidad: que 'la Notebook
    HP 245 G9' sea ambigua entre la Gris y la Plata es otra cosa y tiene su
    propia vara mas abajo."""
    ficha = H.ejecutar("consultar_productos",
                       {"product_id": "NOT0019", "proyeccion": "ficha"},
                       TIENDA)["producto"]
    # 'garantia' resuelve a la clave `garantia` de specs y no a `garantia_meses`
    # de arriba, porque a igualdad de palabras compartidas gana la clave mas
    # corta. Es lo que se quiere: specs dice "12 meses", con la unidad puesta, y
    # `garantia_meses` dice 12 pelado. La que NO puede ganar es
    # `garantia_detalle`, que es el parrafo entero.
    casos = [("lector de huella digital", "lector_huella"),
             ("cuanta ram tiene", "ram"),
             ("garantia", "garantia")]
    for pedido, clave in casos:
        valor = TB._valor_del_campo(ficha, pedido)
        esperado = ficha.get(clave, (ficha.get("specs") or {}).get(clave))
        assert valor == esperado, \
            f"{pedido!r} tenia que resolver a {clave}: dio {valor!r}"
    assert len(casos) == 3, "se probaron menos formas de las escritas"


def test_el_puente_por_palabras_no_pega_cualquier_cosa(firestore_doble):
    """La otra mitad: `peso` no puede alcanzar `precio`. Un puente que pega de
    mas es peor que uno que no pega, porque contesta con el campo equivocado."""
    ficha = {"precio_ars": 100, "stock": 5, "specs": {}}
    assert TB._valor_del_campo(ficha, "peso") is None
    assert TB._valor_del_campo(ficha, "cuantos dpi") is None


# ══════════════════════════════════════════════════════════════════════
# EL NO HONESTO ES MATERIAL
# ══════════════════════════════════════════════════════════════════════

def test_una_busqueda_vacia_deja_material_para_contestar(firestore_doble):
    """Un rubro que no vendemos no deja el punto sin nada: deja el hecho de que
    no hay, y los rubros que si vendemos. Es con lo que se escribe un no honesto
    con salida, en vez de un no seco o una invencion."""
    declarado = {"items": [], "stock": ["una heladera"]}
    t, _ = _turno(declarado, "nohay")
    fila = t["puntos"][0]
    assert fila["estado"] == "con_material", fila
    m = fila["material"][0]
    assert m.get("no_hay"), f"no dice que no hay: {m}"
    # La herramienta contesta de dos formas segun el caso: con los rubros que si
    # vendemos, o con el rubro real de la casa. Cualquiera de las dos sirve para
    # escribir el no honesto; lo que no puede pasar es que no venga ninguna.
    assert m.get("si_vendemos") or m.get("rubro_real"), \
        f"el no honesto salio sin salida: {m}"


# ══════════════════════════════════════════════════════════════════════
# LA REGLA CERO, HECHA ESTRUCTURA
# ══════════════════════════════════════════════════════════════════════

def test_la_identidad_ambigua_sale_como_pregunta_con_los_candidatos(
        firestore_doble):
    """`ambiguous` es el unico veredicto ante el cual el codigo tiene PROHIBIDO
    elegir. Antes el punto llegaba vacio y el modelo no tenia con que preguntar
    bien; ahora llega con los candidatos y la pregunta se escribe sola."""
    declarado = {"items": [],
                 "atributos": [{"de": "la Asus TUF F15", "campo": "garantia"}]}
    t, _ = _turno(declarado, "amb")
    fila = t["puntos"][0]
    assert fila["estado"] == "pregunta", fila
    cands = fila["material"][0]["cual_de_estos"]
    assert len(cands) >= 2, f"una ambiguedad con menos de dos candidatos: {cands}"


def test_una_contradiccion_siempre_es_pregunta(firestore_doble):
    """Aunque el turno tuviera con que contestarla: resolverla es elegir por el
    cliente."""
    declarado = {"items": [{"que": "mouse", "cantidad": 2}],
                 "contradicciones": ["pide 2 mouse y nombra 3 destinos"]}
    t, _ = _turno(declarado, "contra")
    fila = [p for p in t["puntos"] if p["id"].startswith("contradicciones")][0]
    assert fila["estado"] == "pregunta" and fila["material"] == []


def test_la_cuenta_va_sellada_y_una_sola_vez(firestore_doble):
    """El bloque es lo unico que el modelo no redacta, asi que no se reparte
    entre las filas: viaja aparte, entero, una vez."""
    declarado = {"items": [{"que": "mouse Genius DX-110", "categoria": "mouse",
                            "cantidad": 2}], "pide_precio": True}
    t, r = _turno(declarado, "cuenta")
    assert "Total" in (t.get("bloque") or ""), t.get("bloque")
    fila = [p for p in t["puntos"] if p["id"] == "pide_precio:1"][0]
    assert fila["estado"] == "sellado" and fila["material"] == []
    assert json.dumps(t["puntos"], ensure_ascii=False).count("Total:") == 0


# ══════════════════════════════════════════════════════════════════════
# EL PESO
# ══════════════════════════════════════════════════════════════════════

def test_la_tabla_pesa_mucho_menos_que_el_volcado(firestore_doble):
    """Sobre los mismos 40 casos y la misma fuente. El volcado manda todos los
    campos de todos los productos; la tabla manda lo que la pregunta pide."""
    hoy = nuevo = 0
    for f in ORO:
        c = json.load(open(f))
        t, r = _turno(c["declarado"], c["id"])
        hoy += len(H.contexto_json(r["llamadas"]))
        nuevo += len(json.dumps(t, ensure_ascii=False, default=str))
    assert nuevo < hoy * 0.5, \
        f"la tabla pesa {nuevo} contra {hoy} del volcado: la proyeccion no bajo"
    assert hoy > 200000, f"el volcado midio {hoy}, el caso cambio"


def test_ninguna_tabla_desborda_el_tope(firestore_doble):
    casos = 0
    for f in ORO:
        c = json.load(open(f))
        t, _ = _turno(c["declarado"], c["id"])
        peso = len(json.dumps(t, ensure_ascii=False, default=str))
        assert peso <= TB.TOPE, f"{c['id']} pesa {peso}"
        casos += 1
    assert casos == 40, f"corrio sobre {casos} casos, esperaba 40"


# ══════════════════════════════════════════════════════════════════════
# LA COBERTURA CONTRA LOS CASOS DE ORO
# ══════════════════════════════════════════════════════════════════════

# Los cuatro que la tabla NO trae, y por que. Ninguno es un defecto de la tabla:
# tres son rojos que el banco de oro ya marcaba antes de que esto existiera, y
# el cuarto es una diferencia DELIBERADA que Martin tiene que revisar.
CONOCIDOS = {
    "C2-S08:pide_precio:1":
        "el pedido ABIERTO no deriva rubros ni cuenta. Rojo del banco de oro.",
    "C2-S13:temas:2":
        "'me haces ese precio' no lo certifica ningun tema. Rojo del banco.",
    "C2-S17:compatibilidad:1":
        "'ese' no ancla al producto del turno anterior. Rojo del banco.",
    "C2-S10:atributos:1":
        "PARA REVISAR: la ficha de AUR0001 no tiene NINGUN campo sobre "
        "cancelacion de ruido, ni arriba ni en specs ni en la prosa. El caso de "
        "oro lo da por cubierto porque la ficha viajo; la tabla dice que no hay "
        "dato, que es la misma regla que corta el '8000 DPI'. Si la respuesta "
        "correcta es 'no lo tengo confirmado', el caso de oro es el que se "
        "corrige, y eso lo decide Martin.",
}


def test_la_tabla_trae_lo_que_los_casos_de_oro_declaran_cubierto(
        firestore_doble):
    trae = pierde = 0
    inesperados = []
    for f in ORO:
        c = json.load(open(f))
        cubre = (c.get("espera") or {}).get("cubre") or []
        if not cubre:
            continue
        t, _ = _turno(c["declarado"], c["id"])
        estado = {p["id"]: p["estado"] for p in t["puntos"]}
        for pid in cubre:
            if estado.get(pid) in ("con_material", "sellado", "pregunta"):
                trae += 1
            else:
                pierde += 1
                if f"{c['id']}:{pid}" not in CONOCIDOS:
                    inesperados.append(f"{c['id']} {pid} -> {estado.get(pid)}")
    assert not inesperados, "la tabla perdio material nuevo: " + str(inesperados)
    assert trae == 103 and pierde == 4, \
        f"la cobertura se movio: trae {trae}, pierde {pierde}"


def test_los_cuatro_que_faltan_estan_explicados():
    assert len(CONOCIDOS) == 4
    for k, v in CONOCIDOS.items():
        assert len(v) > 40, f"{k} no dice por que"


# ══════════════════════════════════════════════════════════════════════
# EL ARMADO — la vuelta
# ══════════════════════════════════════════════════════════════════════

def _mesa_de_muestra(firestore_doble):
    declarado = {
        "items": [{"que": "mouse inalambrico", "categoria": "mouse",
                   "cantidad": 1}],
        "restricciones": ["que no sea caro"],
        "atributos": [{"de": "el mouse", "campo": "garantia"}],
        "destinos": ["Cordoba"],
        "pide_precio": True,
    }
    return _turno(declarado, "armar")[0]


def test_el_orden_lo_manda_la_mesa_y_no_la_respuesta(firestore_doble):
    """Si el modelo devuelve los puntos desordenados, el mensaje sale en el
    orden en que el cliente pregunto. El orden es del codigo."""
    mesa = _mesa_de_muestra(firestore_doble)
    ids = [p["id"] for p in mesa["puntos"] if p["estado"] != "sellado"]
    resp = {"puntos": [{"id": i, "texto": f"<{i}>"} for i in reversed(ids)]}
    salida = TB.armar(resp, mesa)
    posiciones = [salida.index(f"<{i}>") for i in ids]
    assert posiciones == sorted(posiciones), salida


def test_la_cuenta_la_pega_el_codigo_y_el_modelo_no_la_toca(firestore_doble):
    """La casilla sellada se ignora venga lo que venga: si el modelo retipeo la
    cuenta, se descarta y va el bloque del codigo."""
    mesa = _mesa_de_muestra(firestore_doble)
    sellada = [p for p in mesa["puntos"] if p["estado"] == "sellado"]
    assert sellada, "el caso perdio la cuenta"
    resp = {"puntos": [{"id": sellada[0]["id"],
                        "texto": "Total: $999.999 con envio incluido"}]}
    salida = TB.armar(resp, mesa)
    assert "999.999" not in salida, "salio la cuenta retipeada por el modelo"
    assert mesa["bloque"].strip() in salida, "no salio el bloque del codigo"


def test_un_punto_con_material_que_el_modelo_saltea_no_se_tapa_preguntando(
        firestore_doble):
    """Preguntarle al cliente por algo que el sistema sabia contestar es peor
    que no decirlo: lo hace trabajar a el y suena descolgado. Se mide como
    defecto y el mensaje sale sin ese punto."""
    mesa = _mesa_de_muestra(firestore_doble)
    con = [p for p in mesa["puntos"] if p["estado"] == "con_material"]
    resp = {"puntos": [{"id": con[0]["id"], "texto": "contesto solo este"}]}
    salida = TB.armar(resp, mesa)
    assert "confirmas" not in salida and "precisas" not in salida, salida


def test_si_queda_un_punto_sin_material_y_el_modelo_no_pregunta_pregunta_el_codigo():
    mesa = {"puntos": [
        {"id": "items:1", "pregunto": "1 mouse", "estado": "con_material",
         "material": [{"id": "MOU0023"}]},
        {"id": "restricciones:1", "pregunto": "que le dure años",
         "estado": "sin_material", "material": []}]}
    salida = TB.armar({"puntos": [{"id": "items:1", "texto": "Tengo el Genius."}]},
                      mesa)
    assert "que le dure años" in salida
    assert salida.count("?") == 1, f"salio mas de una pregunta: {salida}"


def test_una_sola_pregunta_por_mensaje():
    """Dos puntos abiertos no dan dos preguntas. La regla vieja
    `una_sola_pregunta` de `mensaje.componer` deja de hacer falta: no puede
    haber dos porque el armado escribe una."""
    mesa = {"puntos": [
        {"id": "restricciones:1", "pregunto": "que le dure años",
         "estado": "sin_material", "material": []},
        {"id": "stock:1", "pregunto": "si hay stock de una heladera",
         "estado": "sin_material", "material": []}]}
    salida = TB.armar({"puntos": []}, mesa)
    assert salida.count("?") == 1, salida


MOLDES = [
    ("contradicciones:1", "pediste 2 mouse y nombraste 3 destinos"),
    ("restricciones:1", "que le dure años"),
    ("atributos:1", "cancelacion de ruido de los HyperX"),
    ("stock:1", "si hay stock de una heladera"),
    ("temas:1", "la politica de cambios"),
]


@pytest.mark.parametrize("pid,que", MOLDES)
def test_la_pregunta_del_codigo_sale_legible(pid, que):
    """La unica prosa que el codigo escribe. Se prueba que salga en castellano
    y sin pegotes: el molde crudo daba 'Sobre si hay stock de...' y
    'los hyperx' con la mayuscula comida."""
    q = TB._pregunta_del_codigo({"id": pid, "pregunto": que})
    assert q.endswith("?"), q
    assert "Sobre si hay" not in q, q
    assert "hyperx" not in q, f"se comio la mayuscula del producto: {q}"
    assert 25 < len(q) < 200, q


def test_cuantos_moldes_de_pregunta_se_probaron():
    assert len(MOLDES) == 5, f"se probaron {len(MOLDES)}, esperaba 5"


def test_la_cuenta_va_al_final_y_antes_de_la_pregunta(firestore_doble):
    """El orden del molde dejaba el presupuesto en el MEDIO del mensaje, entre
    el envio y la garantia, y partia la lectura al medio. Un presupuesto se lee
    al final, justo antes de la pregunta que cierra. Es lo unico que se saca del
    orden en que pregunto el cliente."""
    mesa = _mesa_de_muestra(firestore_doble)
    ids = [p["id"] for p in mesa["puntos"] if p["estado"] != "sellado"]
    resp = {"puntos": [{"id": i, "texto": f"<{i}>"} for i in ids],
            "pregunta_final": "Te lo armo?"}
    salida = TB.armar(resp, mesa)
    pos_cuenta = salida.index("Total:")
    assert all(salida.index(f"<{i}>") < pos_cuenta for i in ids), \
        f"la cuenta no quedo despues de todos los puntos:\n{salida}"
    assert pos_cuenta < salida.index("Te lo armo?"), \
        f"la cuenta quedo despues de la pregunta:\n{salida}"


def test_la_prosa_del_codigo_no_escribe_mal_el_castellano():
    """Tres formas que el armado crudo producia y que un lector de voz canta:
    'garantia de el mouse', 'Sobre si hay stock de', y 'no LO tengo' para un
    campo femenino. El codigo escribe poco, pero lo que escribe se lee."""
    casos = [
        ({"id": "atributos:1", "pregunto": "garantia de el mouse"},
         ["de el ", " no lo tengo"]),
        ({"id": "stock:1", "pregunto": "si hay stock de una heladera"},
         ["Sobre si hay"]),
        ({"id": "atributos:1", "pregunto": "los dpi de el mouse logitech"},
         ["de el ", " no lo tengo"]),
    ]
    for fila, prohibidos in casos:
        q = TB._pregunta_del_codigo(fila)
        for p in prohibidos:
            assert p not in q, f"{p!r} salio en: {q}"
    assert len(casos) == 3, f"se probaron {len(casos)} formas, esperaba 3"

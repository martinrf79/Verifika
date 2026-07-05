"""
AREA: Redactor — "el LLM elige, el codigo redacta" (redactor.py).

El render es determinista: dado un PLAN (piezas + huecos de texto libre) arma el
mensaje final estampando cada dato duro de la fuente. Se lockea:
  1. cada tipo de pieza sale de SU fuente (producto del catalogo, politica curada
     verbatim, presupuesto/envio del contexto del turno);
  2. multi-area: varias piezas conviven, ninguna se cae (el bug del 5-jul);
  3. conservador: pieza sin dato (id inexistente, tema sin curada) se descarta,
     no se inventa ni deja renglon fantasma;
  4. validar_plan filtra lo que el solver pudo devolver mal.
"""
from app.core import redactor as R


# ── 1. Cada pieza sale de su fuente ──────────────────────────────────────────

def test_pieza_producto_sale_del_catalogo(firestore_doble):
    from app.storage.firestore_client import get_all_products
    prod = next(p for p in get_all_products(tienda_id="verifika_prod")
                if isinstance(p.get("precio_ars"), int))
    plan = {"piezas": [{"tipo": "producto", "id": prod["id"]}]}
    out = R.renderizar(plan, "verifika_prod")
    assert prod["nombre"] in out
    assert "$" in out


def test_pieza_producto_id_inexistente_se_descarta(firestore_doble):
    plan = {"saludo": "buenas!",
            "piezas": [{"tipo": "producto", "id": "NOEXISTE999"}]}
    out = R.renderizar(plan, "verifika_prod")
    # El saludo queda, la pieza fantasma no deja rastro.
    assert out == "buenas!"


def test_pieza_politica_sale_curada_verbatim(firestore_doble):
    plan = {"piezas": [{"tipo": "politica", "tema": "cuotas"}]}
    out = R.renderizar(plan, "verifika_prod")
    assert "cuotas" in out.lower()
    assert "{{" not in out  # los huecos de la curada quedaron estampados


def test_pieza_politica_tema_inexistente_se_descarta(firestore_doble):
    plan = {"pregunta": "algo mas?",
            "piezas": [{"tipo": "politica", "tema": "no_existe"}]}
    out = R.renderizar(plan, "verifika_prod")
    assert out == "algo mas?"


def test_presupuesto_y_envio_vienen_del_contexto(firestore_doble):
    plan = {"piezas": [{"tipo": "presupuesto"}, {"tipo": "envio"}]}
    ctx = {"presupuesto": "Total: $17.000", "envio": "Envio a Rosario $7.500"}
    out = R.renderizar(plan, "verifika_prod", ctx)
    assert "Total: $17.000" in out and "Rosario" in out


def test_presupuesto_sin_contexto_se_descarta(firestore_doble):
    plan = {"saludo": "hola", "piezas": [{"tipo": "presupuesto"}]}
    out = R.renderizar(plan, "verifika_prod", {})
    assert out == "hola"


# ── 2. Multi-area: el caso que rompio el 5-jul ───────────────────────────────

def test_multi_area_ninguna_pieza_se_cae(firestore_doble):
    # Cliente pregunto por retiro/ubicacion Y cuotas: las DOS politicas salen,
    # cada una su bloque. Antes se servia una sola y la otra quedaba muda.
    plan = {"saludo": "buenas!",
            "piezas": [{"tipo": "politica", "tema": "ubicacion"},
                       {"tipo": "politica", "tema": "cuotas"}],
            "pregunta": "algo mas te ayudo?"}
    out = R.renderizar(plan, "verifika_prod")
    assert "cuotas" in out.lower()
    # La ubicacion tiene su propio bloque, no quedo tapada por las cuotas.
    ubi = R._bloque_politica("ubicacion", "verifika_prod")
    assert ubi and ubi in out
    assert out.startswith("buenas!")
    assert out.rstrip().endswith("algo mas te ayudo?")


def test_orden_saludo_piezas_transicion_pregunta(firestore_doble):
    plan = {"saludo": "hola", "transicion": "cualquier cosa avisame",
            "pregunta": "te sirve?",
            "piezas": [{"tipo": "politica", "tema": "cuotas"}]}
    out = R.renderizar(plan, "verifika_prod")
    i_saludo = out.index("hola")
    i_cuotas = out.lower().index("cuotas")
    i_trans = out.index("cualquier cosa")
    i_preg = out.index("te sirve?")
    assert i_saludo < i_cuotas < i_trans < i_preg


# ── 3. Dedup y huecos ────────────────────────────────────────────────────────

def test_hueco_que_repite_una_pieza_no_se_duplica(firestore_doble):
    bloque = R._bloque_politica("cuotas", "verifika_prod")
    plan = {"piezas": [{"tipo": "politica", "tema": "cuotas"}],
            "transicion": bloque}  # el solver copio el bloque en un hueco
    out = R.renderizar(plan, "verifika_prod")
    assert out.count(bloque) == 1


# ── 4. validar_plan: red contra un JSON mal formado del solver ───────────────

def test_validar_plan_filtra_piezas_invalidas():
    obj = {"saludo": "hola",
           "piezas": [{"tipo": "producto", "id": "TEC0001"},
                      {"tipo": "producto"},          # sin id -> fuera
                      {"tipo": "politica"},           # sin tema -> fuera
                      {"tipo": "inventado", "x": 1},  # tipo desconocido -> fuera
                      "no soy dict"]}
    plan = R.validar_plan(obj)
    assert plan is not None
    assert len(plan["piezas"]) == 1
    assert plan["piezas"][0]["id"] == "TEC0001"


def test_validar_plan_vacio_es_none():
    assert R.validar_plan({"piezas": [], "saludo": ""}) is None
    assert R.validar_plan("no soy dict") is None
    assert R.validar_plan({}) is None


def test_validar_plan_solo_hueco_es_valido():
    plan = R.validar_plan({"saludo": "buenas, en que te ayudo?"})
    assert plan is not None and plan["saludo"].startswith("buenas")

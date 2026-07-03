"""
AREA: FAQ numerica — los numeros CHICOS de politica (porcentaje, cuotas, plazos,
garantia) que el verificador de plata no mira (solo cubre montos de dinero).

Herramienta cubierta: verificador_faq (app/core/verificador_faq.py).

Invariante: todo numero con unidad de clase (X%, N cuotas, N dias, N meses) tiene
que salir de la FAQ o del catalogo. La correccion es anclada al TEMA consultado
este turno (query_faq): solo si el pool del tema tiene UN valor de esa clase se
reescribe; ante ambiguedad se loguea y no se toca (mismo criterio que la plata).
"""
from app.core import verificador_faq as VF


def _faq(tema, respuesta, valores=None):
    return {"tipo": "faq", "id": tema, "tema": tema,
            "respuesta": respuesta, "valores": valores or []}


EVIDENCIA = [
    _faq("descuento_transferencia",
         "Pagando por transferencia tenes 20% de descuento.",
         valores=[{"concepto": "transferencia", "unidad": "porcentaje",
                   "monto": 20, "modalidad": "fijo"}]),
    _faq("cuotas",
         "Podes pagar hasta en 6 cuotas sin interes, o 12 con interes.",
         valores=[{"concepto": "sin_interes", "unidad": "cuotas", "monto": 6,
                   "modalidad": "fijo"}]),
    _faq("plazo_envio",
         "El envio demora de 2 a 7 dias habiles segun la zona."),
    _faq("devoluciones",
         "Tenes 10 dias corridos para devolverlo por arrepentimiento."),
    {"tipo": "producto", "id": "MOU0001", "nombre": "Mouse G203",
     "precio_ars": 37500, "stock": 5, "garantia_meses": 24},
]


# ── Verificacion: numeros respaldados pasan, inventados se marcan ────────────

def test_porcentaje_real_pasa():
    v = VF.verificar_faq_numerica("Con transferencia tenes 20% de descuento.",
                                  EVIDENCIA)
    assert v["ok"]


def test_porcentaje_inventado_se_marca():
    """El % es EXACTO: un 25% que no esta en ninguna fuente es alucinacion."""
    v = VF.verificar_faq_numerica("Con transferencia tenes 25% de descuento.",
                                  EVIDENCIA)
    assert not v["ok"]
    assert {"clase": "porcentaje", "n": 25} in v["sin_respaldo"]


def test_cuotas_dentro_del_tope_pasan():
    """'hasta 6 cuotas' habilita cualquier N <= 6: ofrecer 3 cuotas es legitimo
    (semantica de rango, no de igualdad; evita el falso positivo)."""
    v = VF.verificar_faq_numerica("Lo podes pagar en 3 cuotas sin interes.",
                                  EVIDENCIA)
    assert v["ok"]


def test_cuotas_sobre_el_tope_se_marcan():
    v = VF.verificar_faq_numerica("Lo podes pagar en 24 cuotas.", EVIDENCIA)
    assert not v["ok"]


def test_dias_dentro_del_rango_pasan():
    v = VF.verificar_faq_numerica("Te llega en 5 dias habiles.", EVIDENCIA)
    assert v["ok"]


def test_dias_fuera_de_rango_se_marcan():
    v = VF.verificar_faq_numerica("Te llega en 45 dias habiles.", EVIDENCIA)
    assert not v["ok"]


def test_garantia_meses_del_catalogo_respalda():
    v = VF.verificar_faq_numerica("El Mouse G203 tiene 24 meses de garantia.",
                                  EVIDENCIA)
    assert v["ok"]


def test_garantia_meses_inventada_se_marca():
    v = VF.verificar_faq_numerica("El Mouse G203 tiene 36 meses de garantia.",
                                  EVIDENCIA)
    assert not v["ok"]


# ── Correccion anclada al tema consultado (safe-override) ────────────────────

def test_corrige_porcentaje_con_tema_consultado():
    """query_faq trajo descuento_transferencia este turno: su pool de porcentaje
    tiene UN valor (20) -> el 25% inventado se reescribe por 20, edicion minima."""
    r = "Con transferencia tenes 25% de descuento, te conviene."
    fix = VF.autocorregir_faq_numerica(
        r, EVIDENCIA, temas_consultados={"descuento_transferencia"})
    assert fix["cambiada"]
    assert "20% de descuento" in fix["respuesta"]
    assert "te conviene" in fix["respuesta"]
    assert fix["verificacion"]["ok"]


def test_sin_tema_consultado_no_corrige_solo_marca():
    """Sin ancla del turno no se arriesga un reemplazo: queda para el log."""
    r = "Con transferencia tenes 25% de descuento."
    fix = VF.autocorregir_faq_numerica(r, EVIDENCIA, temas_consultados=set())
    assert not fix["cambiada"]
    assert not fix["verificacion"]["ok"]


def test_pool_ambiguo_no_corrige():
    """Si el tema consultado tiene DOS porcentajes distintos, es ambiguo: no se
    elige uno, se deja para el log (conservador, como la plata)."""
    evid = [_faq("promos", "Hay 10% en efectivo y 20% por transferencia.")]
    r = "Tenes 25% de descuento."
    fix = VF.autocorregir_faq_numerica(r, evid, temas_consultados={"promos"})
    assert not fix["cambiada"]


def test_numero_respaldado_no_se_toca():
    r = "Con transferencia tenes 20% de descuento."
    fix = VF.autocorregir_faq_numerica(
        r, EVIDENCIA, temas_consultados={"descuento_transferencia"})
    assert not fix["cambiada"]
    assert fix["respuesta"] == r


def test_temas_de_meta_saca_principal_y_relacionadas():
    """El ancla del turno sale de los query_faq del meta: tema principal + las
    relacionadas que la tool devolvio."""
    meta = {"tools_called": [
        {"name": "query_faq",
         "result": {"encontrada": True, "tema": "descuento_transferencia",
                    "relacionadas": [{"tema": "formas_pago"}]}},
    ]}
    assert VF.temas_de_meta(meta) == {"descuento_transferencia", "formas_pago"}

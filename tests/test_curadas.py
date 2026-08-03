"""
AREA: ESTAMPADO de la FAQ curada (`app/core/curadas.py`).

Lock unico y load-bearing: TODA curada del repo con huecos estampa completa
contra los `valores` de su propio tema. Si un hueco no resuelve, la curada NO se
sirve: una politica a medias -"tenes {{dias}} dias para el cambio"- es peor que
no contestarla. Es lo que impide que una tarifa cambiada en el valor deje el
texto viejo, o que un hueco mal escrito salga literal al cliente.

Los otros trece tests de este archivo se BORRARON el 3-ago con el codigo que
probaban: el atajo `servir_curada` y la poda de muletillas eran del ACOPLE, que
murio el 2-ago junto con la tool `query_faq` y el interprete de veinte campos.
Probaban codigo que el bot no corre, que es lo mismo que no probar nada. Las
lecciones que encerraban -no repetir el enlatado, no pedir un dato que la charla
ya tiene- pasaron a `identidad.charla` en la fuente y ahora se las dice al modelo
en cada turno.
"""
from app.core import curadas as C


# ── 1. Lock de formato sobre los datos reales ────────────────────────────────

def test_toda_curada_del_repo_estampa_completa(firestore_doble):
    from app.storage.firestore_client import get_all_faq
    faq = get_all_faq(tienda_id="verifika_prod")
    con_curada = {t: d for t, d in faq.items() if d.get("respuesta_curada")}
    assert con_curada, "Debe haber al menos una respuesta curada cargada."
    for tema, data in con_curada.items():
        out = C.estampar_valores(data["respuesta_curada"], data)
        assert out, f"La curada de '{tema}' tiene un hueco que no resuelve."
        assert "{{" not in out and "}}" not in out


def test_hueco_sin_valor_no_se_sirve():
    data = {"tema": "x", "valores": [], "respuesta_curada": "Sale {{precio}}."}
    assert C.estampar_valores(data["respuesta_curada"], data) is None


def test_formatos_de_valor():
    tema = {"tema": "t", "valores": [
        {"concepto": "tarifa", "modalidad": "fijo", "monto": 3000, "unidad": "ars"},
        {"concepto": "desc", "modalidad": "fijo", "monto": 10, "unidad": "porcentaje"},
        {"concepto": "cuo", "modalidad": "fijo", "monto": 6, "unidad": "cuotas"},
        {"concepto": "rango", "modalidad": "rango", "monto_min": 5000, "monto_max": 12000},
        {"concepto": "gratis", "modalidad": "fijo", "monto": 0, "umbral_ars": 250000},
    ]}
    out = C.estampar_valores(
        "{{tarifa}} | {{desc}} | {{cuo}} | {{rango}} | {{gratis}}", tema)
    assert out == "$3.000 | 10% | 6 | entre $5.000 y $12.000 | $250.000"


# ── 2. Comportamiento del atajo ──────────────────────────────────────────────

def _interp(intencion="pregunta_especifica", **kw):
    return {"intencion": intencion, "confianza": 0.9, **kw}


























# ── PODA DE MULETILLAS CONTRA ESTADO (charla real 20-jul) ────────────────────






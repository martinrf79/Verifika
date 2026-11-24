"""El chequeo del modelo contra su planilla: el codigo del modelo no es un dato (24-nov-2026).

Al cargar el catalogo, `modelo_contra_planilla` daba cinco falsas alarmas: leia Archer AX23 como "23 AX" de wifi. Del
nombre solo cuenta lo que lleva unidad o el tipo de memoria. Se controla en los dos sentidos: los codigos no dan dato, y
una contradiccion real con unidad se sigue viendo.
"""
from app.core.coherencia_datos import modelo_contra_planilla, valores_del_nombre
from app.core.fuente_producto import _valores_de

CODIGOS = ["Archer AX23", "Archer AX55", "Archer AX73", "AC10", "AC8", "Gaming OC RTX 4070 Ti Super", "G305 Lightspeed",
           "Core i5-12400F", "EcoTank L5590", "27GP850 UltraGear", "Deco M4 Mesh"]
DATOS = [("Fury Beast DDR4 3200 16GB", {("gb", "16"), ("ddr", "4")}), ("Baseus GaN5 Pro 100W", {("w", "100")}),
         ("Samsung 990 PRO 2TB", {("tb", "2")})]


def test_los_codigos_del_modelo_no_son_dato():
    malos = [m for m in CODIGOS if valores_del_nombre(m)]
    assert not malos, malos
    print(f"{len(CODIGOS)} codigos de modelo, ninguno leido como dato")


def test_lo_que_lleva_unidad_si_es_dato():
    for modelo, esperado in DATOS:
        assert esperado <= valores_del_nombre(modelo), (modelo, valores_del_nombre(modelo))
    print(f"{len(DATOS)} nombres con dato, leidos")


def test_una_contradiccion_real_se_sigue_viendo():
    """El nombre dice 16GB y la planilla 8GB: la familia y el numero chocan."""
    del_nombre, de_planilla = valores_del_nombre("Fury Beast DDR4 3200 16GB"), _valores_de("8GB")
    assert any(f == g and n != m for f, n in del_nombre for g, m in de_planilla)


def test_la_fuente_real_sin_falsas_alarmas():
    problemas = modelo_contra_planilla("verifika_prod")
    assert problemas == [], problemas

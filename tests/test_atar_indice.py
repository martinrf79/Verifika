"""LA CONDICION ATADA POR EL INDICE — `catalogo.atar` con el origen partido y los campos de si o no (23-oct-2026).

Medido en `banco_pruebas/pedido_documento/atar_ficha.py` sobre la ficha nativa: de 63 condiciones, el codigo ataba 39.
Las clases que no ataba, y que este cambio cubre sin listas de palabras:
  el origen       "no fabricado en China": el pais sale de `origen`, que es prosa, por `filtros_catalogo._valor_crudo`;
  el si o no      "resistente al agua", "bluetooth", "lector de huella": la clave de `specs_preguntables` nombra el
                  campo y se cumple por su veredicto;
  el plural       "sin cables" ata en "con cable usb".
Despues: 52 de 63. Las 3.107 traducciones grabadas, igual: arregla 0, rompe 0.
"""
import pytest

from banco_pruebas import cableado58 as R


@pytest.fixture(scope="module")
def K():
    from app.core import llm_reintento
    puerta = llm_reintento._cliente
    R.instalar()
    llm_reintento._cliente = puerta
    from app.core.flujo import catalogo
    return catalogo


TID = "verifika_prod"

# (rubro, condicion, campo que ata, niega, si es por veredicto)
CASOS = [
    ("auriculares", "no fabricado en China", "pais_fabricacion", True, False),
    ("memoria ram", "fabricada en Taiwan", "pais_fabricacion", False, False),
    ("auriculares", "de marca de Estados Unidos", "pais_marca", False, False),
    ("parlante", "resistente al agua", "resistencia_agua", False, True),
    ("teclado", "bluetooth", "bluetooth", False, True),
    ("tablet", "lector de huella", "lector_huella", False, True),
    ("mouse", "sin cables", "conexion", True, False),
    # Lo que ya ataba sigue igual: "rgb" es un valor de retroiluminacion, no su veredicto.
    ("teclado", "rgb", "retroiluminacion", False, False),
    ("mouse", "inalambrico", "conexion", False, False),
    ("mouse", "no Redragon", "marca", True, False),
]


def test_cada_clase_ata_al_campo_que_la_dice(K):
    malos = []
    for rubro, cond, campo, niega, veredicto in CASOS:
        univ = [p for p in K.productos(TID) if p.get("categoria") == rubro]
        f = K.atar(cond, univ, TID)
        if (f.get("campo"), f.get("niega"), bool(f.get("si_no"))) != (campo, niega, veredicto):
            malos.append((cond, f))
    assert not malos, f"{len(malos)} de {len(CASOS)} condiciones no atan donde corresponde: {malos}"


def test_el_veredicto_filtra_lo_que_dice_si(K):
    """"Resistente al agua" deja solo los parlantes cuyo campo empieza con "si"; "sin bluetooth", los que dicen "no"."""
    from app.core.filtros_catalogo import _si_no, _valor_crudo
    for rubro, cond, campo, esperado in [("parlante", "resistente al agua", "resistencia_agua", "si"),
                                         ("teclado", "sin bluetooth", "bluetooth", "no")]:
        univ = [p for p in K.productos(TID) if p.get("categoria") == rubro]
        f = K.atar(cond, univ, TID)
        quedan = [p for p in univ if K.cumple(p, f)]
        assert quedan and all(_si_no(_valor_crudo(p, campo)) == esperado for p in quedan), (cond, len(quedan))


def test_el_origen_que_no_hay_no_se_inventa(K):
    """Todos los auriculares se fabrican en China: "no fabricado en China" ata y no deja ninguno. `buscar` lo dice."""
    r = K.buscar("auriculares", ["no fabricado en China"], "mas barato", 1, TID)
    assert r["vacio_por"] == ["no fabricado en China"] and r["filas"], r["vacio_por"]


def test_lo_que_prefiere_va_primero_y_no_saca_lo_demas(K):
    """27-oct, FICHA 82: "preferentemente Razer" filtraba y mostraba solo Razer. Lo preferido va primero, con el orden
    adentro, y lo demas sigue; lo exigido sigue filtrando. Dos busquedas."""
    r = K.buscar("mouse", ["inalambrico", "preferentemente Razer"], "mas barato", 8, TID)
    marcas = [p["marca"] for p in r["filas"]]
    assert marcas[0] == "Razer" and set(marcas) - {"Razer"} and not r["vacio_por"], marcas
    k = marcas.index(next(m for m in marcas if m != "Razer"))
    assert all(m == "Razer" for m in marcas[:k]) and all(m != "Razer" for m in marcas[k:]), marcas
    solo = K.buscar("mouse", ["Razer"], "mas barato", 8, TID)
    assert {p["marca"] for p in solo["filas"]} == {"Razer"}

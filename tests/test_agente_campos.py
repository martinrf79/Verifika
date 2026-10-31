"""EL BUSCADOR DA LOS CAMPOS QUE PIDE LA CONSULTA — el examen real del 31-oct, FICHA 83.

13 de las 16 fallas de dato del examen eran un campo que la ficha tiene y la fila del buscador no mostraba: el origen
—"algo que no sea fabricado en China", once charlas— y el peso —"el mouse mas liviano" elegia el tercero—. La fila
cortaba la ficha en seis campos fijos y los campos de arriba de todo, origen, uso, material, nunca entraban.

Se mide la clase: cada campo de la ficha nombrado en la consulta, en cada rubro, sale en las filas que lo tienen.
Sin embeddings: lo exacto basta.
"""
import pytest

from banco_pruebas import clon_produccion as C

CAMPOS = {"origen": "origen", "uso_recomendado": "uso recomendado", "material": "material",
          "peso_gramos": "peso", "dimensiones": "dimensiones", "contenido_caja": "contenido caja",
          "garantia_detalle": "garantia detalle"}
RUBROS = ("mouse", "notebook", "monitor", "teclado", "auriculares", "gabinete")


@pytest.fixture(scope="module")
def A():
    C.instalar()
    from app.core.flujo import agente
    original = agente._parecidos
    agente._parecidos = lambda *a, **k: []
    yield agente
    agente._parecidos = original


def _filas(texto: str) -> list:
    return [x for x in texto.split("\n") if x.startswith("  ") or x.startswith("PRODUCTO:")]


def test_cada_campo_nombrado_sale_en_cada_rubro(A):
    from app.core.flujo import catalogo as K
    casos, malos = 0, []
    for campo, dicho in CAMPOS.items():
        for rubro in RUBROS:
            filas = _filas(A.buscar(f"{dicho} {rubro}", C.TIENDA))
            assert filas, f"{dicho} {rubro}: sin filas"
            casos += 1
            for f in filas:
                p = next((p for p in K.productos(C.TIENDA) if f.strip().removeprefix("PRODUCTO: ").startswith(
                    p["nombre"] + " $")), None)
                if p and K._valor_crudo(p, campo) and f"{CAMPOS[campo]}:" not in f:
                    malos.append(f"{dicho} {rubro}: {f[:120]}")
    print(f"\nCAMPOS PEDIDOS: {casos} consultas, {len(CAMPOS)} campos por {len(RUBROS)} rubros, "
          f"{len(malos)} filas sin el campo")
    assert casos == len(CAMPOS) * len(RUBROS)
    assert not malos, "\n".join(malos[:10])


def test_el_mas_liviano_trae_el_peso_y_va_primero(A):
    """d29c5ac43a: "dame el mouse mas liviano" eligio el G502 X, el tercero, porque la fila no traia el peso."""
    filas = _filas(A.buscar("mouse liviano", C.TIENDA))
    pesos = [int(f.split("peso: ")[1].split()[0]) for f in filas]
    assert len(pesos) == len(filas) == 5 and pesos == sorted(pesos)


def test_lo_no_fabricado_en_china_trae_el_origen_y_ninguno_es_de_china(A):
    """Once charlas del examen: "tenes algun articulo que no sea fabricado en china", y el bot dijo que no tenia el
    dato o que estaba en la caja. La ficha lo tiene."""
    filas = _filas(A.buscar("productos no fabricados en china", C.TIENDA))
    assert len(filas) == 10
    assert all("origen: " in f and "fabricado en china" not in f.lower() for f in filas)


def test_el_origen_de_un_producto_nombrado(A):
    filas = _filas(A.buscar("origen del mouse logitech g203", C.TIENDA))
    assert filas[0].startswith("PRODUCTO:") and "origen: Marca Logitech de Suiza. Fabricado en China." in filas[0]

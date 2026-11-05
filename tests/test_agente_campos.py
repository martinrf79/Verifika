"""LA TABLA TRAE LOS CAMPOS DE LA FICHA — el examen real del 31-oct, FICHA 83; la tabla desde el 5-nov, FICHA 87.

13 de las 16 fallas de dato del examen eran un campo que la ficha tiene y el buscador no mostraba: el origen —"algo que
no sea fabricado en China", once charlas— y el peso —"el mouse mas liviano" elegia el tercero—. EL REQUISITO CAMBIO EL
5-nov: los productos se consultan con SQL sobre `tabla.py`, no con una frase. Lo que se cuida es lo mismo: cada campo de
la ficha es una columna que trae el valor de cada producto que lo tiene, y el criterio del cliente se cumple en la
consulta, el mas liviano, lo no fabricado en China, lo que no sea de una marca y lo que anda con un equipo.
"""
import pytest

from banco_pruebas import clon_produccion as C

CAMPOS = {"uso": "uso_recomendado", "material": "material", "peso_g": "peso_gramos", "dimensiones": "dimensiones",
          "contenido_caja": "contenido_caja", "garantia_detalle": "garantia_detalle"}
RUBROS = ("mouse", "notebook", "monitor", "teclado", "auriculares", "gabinete")


@pytest.fixture(scope="module")
def A():
    C.instalar()
    from app.core.flujo import agente
    return agente


def _filas(texto: str) -> list:
    return [dict(x.split(": ", 1) for x in f.strip().split("; ")) for f in texto.split("\n")[1:] if f.startswith("  ")]


def test_cada_campo_de_la_ficha_es_una_columna_en_cada_rubro(A):
    from app.core.flujo import catalogo as K
    casos, malos = 0, []
    for col, campo in CAMPOS.items():
        for rubro in RUBROS:
            for f in _filas(A.buscar(f"SELECT nombre, {col} FROM productos WHERE rubro = '{rubro}' LIMIT 25", C.TIENDA)):
                casos += 1
                p = next(p for p in K.productos(C.TIENDA) if p["nombre"] == f["nombre"])
                if K._valor_crudo(p, campo) and col not in f:
                    malos.append(f"{rubro} {col}: {f['nombre']}")
    print(f"\nCAMPOS EN LA TABLA: {casos} filas, {len(CAMPOS)} campos por {len(RUBROS)} rubros, {len(malos)} sin el valor")
    assert casos and not malos, malos[:10]


def test_el_mas_liviano_va_primero_con_su_peso(A):
    """d29c5ac43a: "dame el mouse mas liviano" eligio el G502 X, el tercero, porque la fila no traia el peso."""
    from app.core.flujo import catalogo as K
    filas = _filas(A.buscar("SELECT nombre, peso_g FROM productos WHERE rubro = 'mouse' AND stock > 0 ORDER BY peso_g "
                            "LIMIT 5", C.TIENDA))
    pesos = [int(f["peso_g"]) for f in filas]
    minimo = min(K.entero(p.get("peso_gramos")) for p in K.productos(C.TIENDA) if p.get("categoria") == "mouse"
                 and K.con_stock(p) and K.entero(p.get("peso_gramos")))
    assert len(pesos) == 5 and pesos == sorted(pesos) and pesos[0] == minimo


def test_lo_no_fabricado_en_china_trae_el_origen_y_ninguno_es_de_china(A):
    """Once charlas del examen: "tenes algun articulo que no sea fabricado en china", y el bot dijo que no tenia el
    dato o que estaba en la caja. La ficha lo tiene."""
    filas = _filas(A.buscar("SELECT nombre, fabricado_en FROM productos WHERE fabricado_en NOT LIKE '%China%' AND "
                            "stock > 0 LIMIT 10", C.TIENDA))
    assert len(filas) == 10 and all(f.get("fabricado_en") and "china" not in f["fabricado_en"].lower() for f in filas)


def test_el_origen_de_un_producto_nombrado(A):
    f = _filas(A.buscar("SELECT nombre, pais_marca, fabricado_en FROM productos WHERE nombre LIKE '%G203%'", C.TIENDA))[0]
    assert (f["pais_marca"], f["fabricado_en"]) == ("Suiza", "China")


def test_lo_negado_y_el_equipo_filtran_en_la_consulta(A):
    """58b5a1 y b8bb00, 3-nov: "auriculares PS5" listaba primero el Zeus X, que no anda con la PS5, y el modelo lo daba
    por compatible. En la tabla, con_ps5 = 'anda' no lo trae."""
    casos = [("SELECT nombre, marca FROM productos WHERE rubro = 'teclado' AND marca != 'Redragon'", "Redragon", "marca"),
             ("SELECT nombre, con_ps5 FROM productos WHERE rubro = 'auriculares' AND con_ps5 = 'anda'", "Zeus X", "nombre")]
    malos = [q for q, fuera, col in casos if not (fs := _filas(A.buscar(q, C.TIENDA))) or any(fuera in f[col] for f in fs)]
    print(f"\nFILTROS: {len(casos) - len(malos)} de {len(casos)}")
    assert not malos, malos


def test_la_consulta_es_de_solo_lectura_y_el_envio_va_en_castellano(A):
    contar = "SELECT COUNT(*) FROM productos"
    antes = A.buscar(contar, C.TIENDA)
    assert "COUNT" in antes and "SELECT" in A.buscar("DELETE FROM productos", C.TIENDA)
    assert "Solo una consulta SELECT" in A.buscar("SELECT 1; DELETE FROM productos", C.TIENDA)
    assert A.buscar(contar, C.TIENDA) == antes
    assert "envio a <lugar>" in A.buscar("SELECT nombre FROM productos WHERE nombre LIKE '%envio%'", C.TIENDA)
    assert "Envío a Posadas: $" in A.buscar("envio a Posadas", C.TIENDA)

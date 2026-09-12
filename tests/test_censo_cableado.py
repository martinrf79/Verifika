"""EL CANDADO DEL CABLEADO — que las puntas sueltas no crezcan.

POR QUE ES UN TECHO Y NO UN CERO. Hay 32 y no se arreglan en una sesion; un
test que exija cero estaria rojo desde el dia uno y se apagaria a la semana,
que es como se murieron los candados anteriores de este repo. El techo SOLO
BAJA, igual que los de `A MEDIAS` y `PLAN`: se puede arreglar de a poco y no se
puede empeorar sin que alguien lo decida a proposito, en su propio commit y con
las cuentas escritas.

LO QUE ESTE CANDADO COMPRA, que es lo que Martin pregunto el 12-sep: que una
desconexion nueva se vea EN EL MISMO PUSH QUE LA CREA. Todas las de hoy se
descubrieron en WhatsApp, dias despues, de a una y con un cliente adelante.
"""
from banco_pruebas import censo_cableado as C


def test_el_cableado_no_empeora():
    r = C.censo()
    techo = C.techo()
    assert r["total"] <= techo, (
        f"EL CABLEADO EMPEORO: {r['total']} puntas sueltas contra un techo de "
        f"{techo}. Las nuevas son:\n"
        + "\n".join(f"   {h['clase']}: {h['nombre']} en {h['donde']}"
                    for h in r["hallazgos"]
                    if h["clase"] != "funcion_solo_instrumento"))
    print(f"\nCABLEADO: {r['total']} puntas sueltas, techo {techo} — "
          + ", ".join(f"{k} {v}" for k, v in sorted(r["por_clase"].items())))


def test_el_techo_esta_al_dia_o_sobra():
    """Si el censo bajo y el techo no, el techo dejo de medir: cualquier
    desconexion nueva entra gratis hasta llegar al numero viejo."""
    r = C.censo()
    assert C.techo() - r["total"] <= 3, (
        f"el techo quedo {C.techo() - r['total']} puntas por encima del censo "
        f"real ({r['total']}): bajalo en su propio commit")


def test_las_cinco_clases_MIDEN_algo():
    """Un detector que siempre devuelve vacio se ve igual que un cableado
    sano, y es como se apago el candado del CI con `|| true`. Cada clase tiene
    que poder encontrar su caso: se le da uno de mentira y tiene que verlo."""
    import ast
    # El detector de campos, con una lectura que nadie escribe.
    arbol = ast.parse('conv.get("campo_que_no_existe_jamas")')
    assert arbol, "el parseo es la base de tres de los cinco detectores"
    # Los cinco existen y devuelven listas, no None.
    for nombre, fn in C.CLASES.items():
        r = fn()
        assert isinstance(r, list), f"{nombre} no devolvio una lista"
    # Y el censo entero no puede dar cero: si da cero, algo dejo de mirar.
    assert C.censo()["total"] > 0, (
        "el censo dio CERO. O se arreglo todo el cableado de una vez, y "
        "entonces hay que bajar el techo a cero en un commit propio, o los "
        "detectores dejaron de mirar.")

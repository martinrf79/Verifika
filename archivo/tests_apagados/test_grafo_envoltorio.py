"""El unico test que quedaba del envoltorio del grafo. Salio de
`tests/test_cierre_y_cobro.py` el 3-sep-2026, cuando `app/verifika/grafo.py`
se apago: mide como se declaraba cada nodo del turno, y ya no hay nodos.
"""
def test_el_grafo_declara_sus_nodos_con_el_envoltorio():
    """`grafo._n` es el envoltorio con el que se declara cada nodo del turno.
    Es la identidad a proposito -no envuelve nada todavia- y por eso conviene
    fijarlo: el dia que envuelva algo, esta prueba dice si sigue devolviendo la
    funcion que le dieron, que es de lo que depende el cableado entero."""
    from app.verifika.grafo import ETAPAS, _n, NODOS, nodos_de

    def cualquiera(texto, ctx):
        return texto

    assert _n(cualquiera) is cualquiera
    # QUE EL GRAFO NO SE QUEDE SIN NODOS, escrito sin un numero (FICHA 10,
    # 24-ago-2026). Decia `> 20` y era el conteo del dia: la FICHA 10 baja la
    # salida de 18 nodos a 4 y ese 20 se pone rojo sin que el grafo haya
    # perdido una sola etapa. Lo que hay que exigir es que las SEIS etapas del
    # turno sigan declaradas y ninguna quede vacia, que es lo que "se quedo sin
    # nodos" queria decir; contar nodos mide otra cosa, y esa otra cosa la
    # miden los tests del recorte, que la quieren cada vez mas chica.
    vacias = [e for e in ETAPAS if not nodos_de(e)]
    assert not vacias, f"etapas del turno sin un solo nodo: {vacias}"
    assert len(NODOS) == sum(len(nodos_de(e)) for e in ETAPAS), (
        "hay nodos declarados en una etapa que el turno no conoce")

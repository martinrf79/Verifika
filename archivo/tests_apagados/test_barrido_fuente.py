"""
EL BARRIDO DE LA FUENTE — el otro lado del de identidad.

POR QUE SON DOS ARCHIVOS Y NO UNO. `test_barrido_identidad` barre el CODIGO: le
pasa la fuente entera a un engranaje y mira cual no resuelve. Este barre la
FUENTE: chequea los datos entre si, sin pasar por ningun engranaje. La
distincion no es de orden, es de naturaleza — los dos hallazgos del barrido de
identidad fueron bugs de codigo con la fuente intacta, y las 57 fichas que le
mentian al cliente el 29-jul fueron lo contrario, fuente rota con el codigo
sano. Un sistema con la mejor logica del mundo arriba de datos que se
contradicen sigue mintiendo.

LO QUE ESTE ARCHIVO CIERRA. `coherencia_datos` existe desde el 29-jul, hace los
seis chequeos correctos, y el mapa de cobertura del 12-ago dice que **ninguna
prueba lo corria**: ni `revisar_todo`, ni `cobertura_compatibilidad`, ni los
seis chequeos de adentro. Estaba escrito y apagado, que es la peor de las dos
formas de no tenerlo, porque figura como hecho.

MEDIDO EL 12-AGO sobre la fuente real: los seis chequeos dan CERO problemas. O
sea que este archivo nace en verde, y ese es exactamente su valor — no viene a
arreglar nada, viene a que el dia que alguien cargue una fila que se contradice
con otra, se entere en el push y no seis semanas despues por una respuesta que
le llego a un cliente.

SE LOCKEAN PISOS, NO TOTALES. Cuantos productos, cuantos temas y cuantas
categorias hay vive en UN solo lugar con candado propio, `INVENTARIO_FUENTE.md`.
Repetir esos numeros aca seria crear la segunda copia que despues envejece, que
es el error que ya se pago una vez. Lo que se afirma aca son propiedades: cero
contradicciones, cero huecos donde no puede haberlos, y una cobertura que puede
subir pero no bajar en silencio.
"""
import csv

import pytest

RUTA_CSV = "data/clientes/verifika_prod/productos.csv"
TIENDA = "verifika_prod"


@pytest.fixture(scope="module")
def fuente(firestore_doble):
    from app.core.contexto_turno import set_current_tienda
    set_current_tienda(TIENDA)
    with open(RUTA_CSV, encoding="utf-8") as f:
        filas = [dict(r) for r in csv.DictReader(f)]
    for p in filas:
        p["precio_ars"] = int(p["precio_ars"] or 0)
    return filas


# ── 1. LOS DATOS NO SE CONTRADICEN ENTRE SI ─────────────────────────────────

def test_los_seis_chequeos_de_coherencia_dan_cero(fuente):
    """El chequeo que estaba escrito y no corria nadie.

    Cubre las seis formas en que la fuente puede mentirle al cliente sin que el
    codigo tenga un solo bug: el modelo que se llama RM850e con la potencia
    cargada en 550W, la prosa que sobrevive a la ingesta contradiciendo a la
    planilla curada, el typo de compatibilidad que no existe en el vocabulario
    cerrado, las dos planillas del mismo modelo que se contradicen, la fila
    huerfana de un producto que ya no esta, y la columna que nadie lee."""
    from app.core import coherencia_datos as CD

    problemas = CD.revisar_todo(TIENDA)
    rotos = {k: v for k, v in problemas.items() if v}
    assert not rotos, "la fuente se contradice a si misma: " + "; ".join(
        f"{k}: {len(v)} — p.ej. {str(v[0])[:120]}" for k, v in rotos.items())


def test_la_compatibilidad_cargada_no_puede_bajar(fuente):
    """PISO, no total. Un modelo sin fila de compatibilidad no es un error -la
    celda vacia sale honesta, el bot dice que no esta confirmado- pero un hueco
    GRANDE tiene que ser una decision y no un descuido. El piso se fija en lo
    que hay hoy: cargar mas esta bien, perder lo cargado se ve."""
    from app.core import coherencia_datos as CD

    cubiertos, total = CD.cobertura_compatibilidad(TIENDA)
    assert total > 400, "la tabla de compatibilidad se quedo sin modelos"
    assert cubiertos >= 469, (
        f"la compatibilidad cargada BAJO: {cubiertos} de {total}, era 469")


# ── 2. LA FUENTE CONTESTA TODO LO QUE DICE QUE CONTESTA ─────────────────────

def test_toda_spec_que_aplica_a_un_producto_tiene_valor(fuente):
    """EL BARRIDO DE LAS SPECS: cada par producto-spec que APLICA se recorre y
    tiene que traer valor. Medido el 12-ago: 100% de los pares aplicables se
    contestan, gracias a las cuatro capas -ficha del producto, tabla por modelo,
    default de categoria, regla condicional-.

    Un hueco aca no rompe el turno, el bot contesta el honesto 'la ficha no lo
    especifica'. Pero el honesto no vende, y hoy no hace falta decirlo ni una
    vez: si aparece un hueco es porque una capa dejo de cargar, y eso se tiene
    que ver en el push."""
    from app.core import fuente_producto as F

    cfg = F.specs_config(TIENDA)
    assert cfg, "specs_preguntables.json no cargo: la fuente quedo muda"
    huecos = []
    for p in F.enriquecer(fuente, TIENDA):
        specs = p.get("specs") or {}
        for s in cfg:
            if F.aplica(s, p.get("categoria", "")) and not specs.get(s["id"]):
                huecos.append((p.get("id"), s["id"]))
    assert not huecos, (f"{len(huecos)} pares producto-spec sin valor, "
                        f"p.ej. {huecos[:5]}")


def test_todo_tema_del_enum_tiene_material_que_devolver(fuente):
    """EL BARRIDO DE LOS TEMAS. El enum de `consultar_temas` junta la FAQ con la
    base de conocimiento, y es lo UNICO que el modelo puede nombrar. Un tema que
    entra al enum y no devuelve nada es el peor hueco posible: el modelo lo
    llama porque se lo ofrecimos, no recibe nada, y contesta de memoria — que es
    exactamente la alucinacion que todo el diseño viene a evitar.

    Es la falla que costo mas cara del proyecto, del otro lado: los 23 temas que
    la fuente sabia contestar y el interprete no podia nombrar estuvieron
    tapados meses porque nadie tenia el numero."""
    from app.core.herramientas import _criterio_de, _politica_de, temas_consultables

    temas = temas_consultables(TIENDA)
    assert temas, "el enum de temas quedo vacio"
    mudos = [t for t in temas
             if not _politica_de(t, TIENDA) and not _criterio_de(t)]
    assert not mudos, f"{len(mudos)} temas del enum no devuelven material: {mudos[:10]}"


# Las CURADAS no se barren aca a proposito: ya las barre entera
# `tests/test_curadas.py::test_toda_curada_del_repo_estampa_completa`, y lo hace
# sobre la FAQ leida por el mismo camino que la lee el bot. Duplicar el candado
# es crear la segunda copia que despues envejece distinto de la primera.

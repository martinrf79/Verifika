"""EL TABLERO — el indice de la fuente que el modelo lee antes de buscar.

Es el componente 7 de la FICHA 52 y su diseno esta en
`arquitectura/FICHA_53_el_tablero.md`. Aca vive su vara, y son dos cosas
distintas: LO QUE TIENE QUE DECIR y LO QUE NO PUEDE PESAR.

EL TECHO SOLO BAJA. Si una sesion lo sube, que sea en su propio commit y con
las cuentas escritas, que es la regla del bloque 1 de CLAUDE.md. Subirlo junto
con el trabajo que lo hace pasar es indistinguible de aflojar la vara.
"""
import json

import pytest

from app.core import motor as MT
from app.core.filtros_catalogo import (CARGA_FLACA, LARGO_ETIQUETA,
                                       campos_ordenables,
                                       condicion_sin_vocabulario, leyenda,
                                       vocabulario)

TIENDA = "verifika_prod"

# Medido el 13-sep-2026 sobre la tienda viva: el esquema entero, con la leyenda
# adentro, da 2.001. El techo deja margen para que una tienda con mas variedad
# entre, y NO para que este repo engorde.
TECHO_TABLERO = 2100


def _tokens(s: str) -> int:
    """Bytes sobre cuatro. No hay tokenizador en el repo, asi que lo que
    importa es que siempre se mida igual."""
    return len(s) // 4


def test_el_tablero_no_pasa_su_techo(firestore_doble):
    peso = _tokens(json.dumps(MT.esquema(TIENDA), ensure_ascii=False))
    assert peso <= TECHO_TABLERO, (
        f"el tablero pesa {peso} tokens y el techo es {TECHO_TABLERO}")


def test_el_tablero_no_lleva_un_solo_dato(firestore_doble):
    """Lleva VOCABULARIO, no catalogo. Que la fuente escriba `china` no dice
    que producto es chino. Si se colara un id o un precio, el tablero pasaria a
    crecer con el catalogo, que es lo unico que no puede pasar."""
    crudo = json.dumps(MT.esquema(TIENDA), ensure_ascii=False)
    from app.storage.firestore_client import get_all_products
    prods = get_all_products(tienda_id=TIENDA)
    colados = [p["id"] for p in prods[:200] if str(p.get("id")) in crudo]
    assert not colados, f"se colaron ids de producto: {colados[:5]}"
    precios = [p["precio_ars"] for p in prods[:200]
               if str(p.get("precio_ars")) in crudo]
    # El rango del inventario SI viaja -el minimo y el maximo-, asi que dos
    # precios pueden aparecer legitimamente. Mas que eso es catalogo.
    assert len(precios) <= 2, f"se colaron precios: {precios[:5]}"


def test_la_leyenda_dice_las_palabras_del_campo_que_se_erraba(firestore_doble):
    """`pais_fabricacion` es el defecto medido: `igual china` trae 633 y
    `contiene china` trae 789, 156 de diferencia, y el modelo elegia el
    operador sin ver los 5 valores que la fuente usa."""
    L = leyenda(TIENDA)
    assert "pais_fabricacion" in L
    for v in ("china", "taiwan o china segun linea",
              "china, taiwan o corea segun linea"):
        assert v in L, f"falta el valor '{v}' en la leyenda"


def test_la_leyenda_enumera_la_marca(firestore_doble):
    """Es de los campos que mas nombra un cliente -"tenes Logitech?"- y tiene
    75 valores: la regla de contar valores lo dejaba afuera, la de presupuesto
    por rendimiento lo mete."""
    L = leyenda(TIENDA)
    for m in ("logitech", "asus", "kingston", "samsung"):
        assert m in L, f"falta la marca '{m}'"


def test_la_leyenda_no_lleva_prosa(firestore_doble):
    """`contenido_caja` tiene 22 valores distintos -poca variedad- y cada uno
    es un parrafo. Enumerarlo pesaba 675 tokens que no le sirven a nadie."""
    voc = vocabulario(TIENDA)
    L = leyenda(TIENDA)
    largos = [v for d in voc.values() for v in (d["valores"] or [])
              if len(v) > LARGO_ETIQUETA and v in L]
    assert not largos, f"se colo prosa en la leyenda: {largos[:2]}"


def test_la_leyenda_avisa_los_campos_flacos(firestore_doble):
    """`memoria_video` esta en 18 de 880. Filtrar por ahi devuelve casi nada, y
    ese casi nada se lee como "no lo tenemos" en vez de "no esta cargado". Es
    la respuesta 2 dicha como la 3, el defecto mas caro del nicho."""
    from app.core.filtros_catalogo import recorrida
    L = leyenda(TIENDA)
    voc = vocabulario(TIENDA)
    total = recorrida(TIENDA)["productos"]
    flacos = [c for c, d in voc.items()
              if d["tipo"] != "numero" and d["llenos"] < CARGA_FLACA * total]
    assert flacos, "la tienda de prueba tiene que tener algun campo flaco"
    for c in flacos:
        assert c in L, f"el campo flaco '{c}' no se avisa"


def test_ordenar_por_ofrece_solo_los_numericos(firestore_doble):
    """Sobre una etiqueta el orden es alfabetico y no contesta ninguna pregunta
    que un cliente pueda hacer. Ofrecer los 41 era caro y ademas estaba mal."""
    ordenables = campos_ordenables(TIENDA)
    assert set(ordenables) == {"precio_ars", "peso_gramos", "garantia_meses"}
    esq = MT.esquema(TIENDA)
    en_esquema = (esq["function"]["parameters"]["properties"]["consultas"]
                  ["items"]["properties"]["ordenar_por"]["properties"]
                  ["campo"]["enum"])
    assert en_esquema == ordenables


def test_el_tablero_nombra_las_cinco_bocas(firestore_doble):
    """Una boca que el tablero no nombra no existe para el modelo, aunque tenga
    cable. Y la que NO tiene cable se dice, en vez de fingirla."""
    d = MT.esquema(TIENDA)["function"]["description"].lower()
    assert "catalogo" in d and "politicas" in d
    for sin_cable in ("compatible", "conviene", "envio"):
        assert sin_cable in d, f"no se avisa que falta el cable de {sin_cable}"


@pytest.mark.parametrize("campo,operador,valor,hay_hueco", [
    ("pais_fabricacion", "igual", "japon", True),
    ("pais_fabricacion", "igual", "china", False),
    ("pais_fabricacion", "contiene", "china", False),
    ("color", "igual", "fucsia", True),
    ("color", "igual", "negro", False),
    ("marca", "igual", "nintendo", True),
    ("marca", "igual", "logitech", False),
    # Un campo de 482 valores no se valida por vocabulario: ahi contesta el
    # rescate por cercania, que ya existe.
    ("modelo", "contiene", "g15", False),
    ("modelo", "contiene", "no_existe_este_modelo", False),
])
def test_el_hueco_de_valor_caso_por_caso(firestore_doble, campo, operador,
                                         valor, hay_hueco):
    r = condicion_sin_vocabulario(campo, operador, valor, TIENDA)
    assert (r is not None) == hay_hueco, f"{campo} {operador} {valor} -> {r}"


def test_un_valor_que_no_existe_no_devuelve_cero(firestore_doble):
    """LA DECISION D3. Cero se lee como "no lo tenemos". El hueco se lee como
    "esa palabra no es la nuestra, estas si"."""
    r = MT.buscar([{"categoria": "notebook", "busco": "varios",
                    "condiciones": [{"campo": "pais_fabricacion",
                                     "operador": "igual",
                                     "valor": "japon"}]}], TIENDA)
    q = r["resultados"][0]
    assert q["filas"], "no puede volver vacio: la condicion no se pudo aplicar"
    motivos = " ".join(x["motivo"] for x in q["no_aplicado"])
    assert "japon" in motivos and "china" in motivos


def test_la_G15_no_puede_traer_una_G16(firestore_doble):
    """El caso que no se puede errar. `g15` son 9 filas de Dell y `g16` son 9
    de Asus: un vecino cercano los mezcla, un `contiene` con borde de digito
    no puede."""
    for codigo, marca in (("g15", "Dell"), ("g16", "Asus")):
        r = MT.buscar([{"categoria": "notebook", "busco": "uno", "cuantos": 8,
                        "condiciones": [{"campo": "modelo",
                                         "operador": "contiene",
                                         "valor": codigo}]}], TIENDA)
        filas = r["resultados"][0]["filas"]
        assert filas, f"{codigo} no devolvio nada"
        for f in filas:
            assert codigo in f["nombre"].lower(), f"{codigo} trajo {f['nombre']}"
            assert marca.lower() in f["nombre"].lower()

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
                                       que_dice_la_fuente_de,
                                       campos_ordenables,
                                       condicion_sin_vocabulario, leyenda,
                                       vocabulario)

TIENDA = "verifika_prod"

# Medido el 13-sep-2026 sobre la tienda viva: el esquema entero, con la leyenda
# adentro, daba 2.001 y el techo era 2.100. El techo deja margen para que una
# tienda con mas variedad entre, y NO para que este repo engorde.
#
# SUBE UNA VEZ, 13-sep-2026, Y LAS CUENTAS SON ESTAS. La boca de
# COMPATIBILIDAD entra al tablero: el campo `compatibilidad` del esquema pesa
# 177 tokens -los dos ids, los doce equipos que el vocabulario conoce y los
# tres veredictos- y nombrarla en la descripcion de la puerta cuesta otros 36.
# El esquema vivo pasa de 2.001 a 2.214, asi que el techo pasa de 2.100 a
# 2.300 y el margen queda en 86, del mismo orden que el 99 que tenia.
#
# LO QUE COMPRA ESE GASTO: la compatibilidad se contestaba de memoria. La
# tabla de la casa estaba escrita, se estampa en cada ficha al leer el catalogo
# y el turno no la alcanzaba; sin este campo, el modelo no tiene como pedirla.
#
# Y SUBE OTRA VEZ, EL MISMO DIA, POR LA ULTIMA BOCA QUE FALTABA CABLEAR. El
# campo `envios` pesa 76 tokens y nombrar la boca en la descripcion de la
# puerta cuesta 11: el esquema pasa de 2.214 a 2.301. El techo pasa de 2.300 a
# 2.400 y el margen vuelve a 99, que es el que tuvo siempre.
#
# LO QUE COMPRA: el envio deja de viajar EMPUJADO en cada turno. El bloque que
# se saco del prompt pesaba entre 70 y 250 caracteres y salia contestara lo que
# contestara el cliente, asi que el tablero sube y el TURNO baja. La cuenta
# entera se mira en vivo, no aca.
#
# Y SUBE LA TERCERA Y ULTIMA VEZ, EL MISMO DIA, POR LA BOCA QUE QUEDABA: el
# CRITERIO. El campo `criterio` pesa 111 tokens y nombrar la boca en la
# descripcion de la puerta cuesta 41; a cambio se BORRA la linea que avisaba
# que esa boca no tenia cable, que devuelve 22. Son +130: el esquema pasa de
# 2.301 a 2.432, asi que el techo pasa de 2.400 a 2.530 y el margen queda en
# 98, el mismo 99 que tuvo siempre.
#
# LO QUE COMPRA ESE GASTO: hoy "para que sirve" y "cual conviene" no tienen a
# quien preguntarle. Las entradas de `base_conocimiento.json` estan escritas y
# del turno no las alcanza nadie -el archivo se lee para la VOZ-, asi que el
# criterio lo contesta el modelo de memoria o entra disfrazado de politica. Sin
# este campo no hay forma de pedirlo.
#
# Y ES EL ULTIMO QUE SE PAGA POR UNA BOCA: con esta, las cinco tienen cable, y
# el techo de aca en adelante solo baja.
#
# ── Y SUBE UNA VEZ MAS, EL 14-sep, Y NO ES POR UNA BOCA ─────────────────────
#
# ESTO CONTRADICE EL RENGLON DE ARRIBA, y se dice asi en vez de borrarlo. El
# 13-sep se escribio que el techo solo bajaba de ahi en adelante. Sube igual, y
# el motivo tiene que poder discutirse: por eso la frase vieja queda.
#
# QUE SE PAGA: el campo `cuenta` pesa 170 tokens y nombrarla en la descripcion
# de la puerta cuesta 25. Son +195; medido, el esquema pasa de 2.432 a 2.631,
# asi que el techo pasa de 2.530 a 2.730 y el margen queda en 99, el mismo que
# tuvo siempre. La primera version del campo pesaba 288 y se recorto a 195
# antes de tocar el techo: lo que se paga es lo que no se pudo sacar.
#
# LO QUE COMPRA, y por que no es una boca sexta: la CUENTA no tiene area de
# fuente. Es aritmetica sobre lo que las otras devolvieron, y vive en el
# RETORNO. Hasta hoy el TOTAL del pedido lo resolvia `numeros` SUMANDO las
# cifras que ya estaban escritas en el mensaje. Esa suma no puede conocer el
# descuento por transferencia ni el reparto entre medios de pago, asi que el
# setenta treinta no existia: `calculate_total` es la unica que llama a
# `pago_split` y desde el apagon del 11-sep el total del pedido no la llamaba
# nunca. Sin este campo no hay forma de pedirla.
#
# Y AHORA SI SOLO BAJA: con esta, las cinco bocas tienen cable y la cuenta que
# las cruza tambien. No queda nada que enchufar que justifique subirlo.
#
# ── Y BAJA EL MISMO DIA, QUE ES COMO TIENE QUE MOVERSE ──────────────────────
#
# El campo `specs` de la consulta se borro: dejo de significar algo cuando la
# prosa dejo de viajar en las listas. Devuelve 62 tokens, asi que el esquema
# pasa de 2.631 a 2.569 y el techo de 2.730 a 2.670, con el margen en 101.
#
# ── Y BAJA OTRA VEZ EL 15-sep, CON LOS CAMPOS DE VEREDICTO ──────────────────
#
# Los ocho campos de si o no dejaron de enumerar su prosa y pasaron a un
# renglon propio con las dos palabras que el motor compara. El esquema pasa de
# 2.653 a 2.457 y el techo de 2.670 a 2.560, con el margen en 103.
TECHO_TABLERO = 2560


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


def test_la_marca_no_se_enumera_y_el_hueco_la_cubre(firestore_doble):
    """DA VUELTA LA VARA DEL 13-sep, y el requisito cambio de verdad.

    Hasta hoy este test exigia lo contrario: que `marca` entrara en la leyenda
    porque es de los campos que mas nombra un cliente. Lo que se midio despues
    es que la leyenda no alcanza sola —el 19-sep, cuatro veces seguidas, el
    modelo tuvo los cinco valores de `pais_fabricacion` delante y escribio
    igual `no_contiene china`— y que `marca` es el renglon que PEOR rinde:
    724 caracteres, el 35% del gasto, para 75 valores.

    La cobertura no se pierde, cambia de mecanismo: el HUECO DE VALOR devuelve
    los valores reales del campo cuando el modelo escribe uno que la fuente no
    usa. Seguro pagado por adelantado contra pago al usar.
    """
    L = leyenda(TIENDA)
    assert "logitech" not in L, "marca volvio a la leyenda: son 724 caracteres"
    cubre = que_dice_la_fuente_de("marca", TIENDA)
    for m in ("logitech", "asus"):
        assert m in cubre, f"el hueco de valor no cubre la marca '{m}'"


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


def test_un_campo_de_veredicto_se_dice_en_veredicto(firestore_doble):
    """LA CONSIGNA DE LA FICHA 54: el tablero tiene que decir lo mismo que las
    bocas. `evaluar` compara los campos de si o no por `_si_no` -la primera
    palabra- y la leyenda enumeraba las 19 formas en que la fuente escribe que
    algo tiene bluetooth. Eran dos idiomas para el mismo campo, y el que el
    modelo veia era el que el motor no usa."""
    L = leyenda(TIENDA)
    voc = vocabulario(TIENDA)
    si_no = [c for c, d in voc.items() if d["tipo"] == "si_no"]
    assert si_no, "la tienda de prueba tiene que tener campos de si o no"
    # Se mira el renglon ENUMERADO, no la leyenda entera: "no, se conecta por
    # usb" es un valor legitimo de `wifi`, que es de texto y si se enumera.
    enumerados = {r.split(" (")[0] for r in L.splitlines() if "): " in r}
    for campo in si_no:
        assert campo in L, f"el campo de veredicto '{campo}' no se nombra"
        assert campo not in enumerados, (
            f"se enumero la prosa de un veredicto: {campo}")
    assert "igual si" in L and "igual no" in L, (
        "la leyenda no dice con que se filtra un campo de si o no")


def test_el_hueco_de_un_veredicto_contesta_si_o_no(firestore_doble):
    """La misma regla del otro lado. Devolverle "si, bluetooth 5.1 | no, este
    modelo es con cable" a un `igual true` le ensena a copiar la frase, que es
    justo lo que el motor no compara."""
    voc = vocabulario(TIENDA)
    campo = next(c for c, d in voc.items() if d["tipo"] == "si_no")
    assert condicion_sin_vocabulario(campo, "igual", "true", TIENDA) == [
        "si", "no"]
    assert condicion_sin_vocabulario(campo, "igual", "si", TIENDA) is None
    assert condicion_sin_vocabulario(campo, "igual", "no", TIENDA) is None


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
    cable. Y la que NO tiene cable se dice, en vez de fingirla.

    CAMBIO EL 13-sep: COMPATIBILIDAD pasa de la lista de las que no tienen
    cable a la de las que se pueden pedir, porque el cable se construyo. Las
    dos listas se siguen midiendo, que es lo que esta vara cuida: la boca sin
    cable no puede quedar muda ni fingida.

    Y CAMBIA POR ULTIMA VEZ EL MISMO DIA, CON EL CRITERIO: la lista de las que
    no tienen cable queda VACIA, asi que lo que se mide ahora es lo otro. Las
    cinco se nombran y las cinco se pueden pedir; y el aviso de "todavia no
    tiene cable" no puede sobrevivir a su boca, porque un tablero que dice que
    algo no se pide es un tablero que hace que no se pida.

    Y CAMBIA EL 20-sep, CON LA FUSION DE LAS DOS AREAS DE LA CASA: politicas y
    criterio se piden por el MISMO campo, asi que ya no hay un campo por boca y
    la lista no se puede escribir a mano. Lo que se mide es el invariante, no
    los nombres: TODA boca que el indice nombra tiene su campo en el esquema.
    Asi una boca nueva no puede nacer nombrada y sin puerta, ni al reves."""
    d = MT.esquema(TIENDA)["function"]["description"].lower()
    props = MT.esquema(TIENDA)["function"]["parameters"]["properties"]
    from app.core import bocas as BC
    for b in BC.BOCAS:
        assert b.campo in props, f"se nombra {b.nombre} y no se puede pedir"
    assert "catalogo" in d and "consultas" in props
    assert "politicas" in d and "temas" in props
    assert "conviene" in d, "el tablero no dice para que sirve la boca criterio"
    for boca in ("compatibilidad", "envios"):
        assert boca in d, f"la boca con cable no se nombra: {boca}"
    assert "no tiene cable" not in d and "no tienen cable" not in d, (
        "las cinco bocas tienen cable y el tablero sigue avisando que falta uno")


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


def test_la_consulta_repetida_se_ejecuta_una_sola_vez(firestore_doble):
    """Medido el 13-sep: 6 repetidas sobre 31, y la causa no era la que decia
    el comentario de `_anotar`. El modelo manda dos consultas IDENTICAS en la
    MISMA llamada, asi que no hay vuelta de por medio: es determinista y se
    arregla en el motor, sin gastar prompt.

    LA REPETIDA VUELVE EN SU LUGAR Y SIN FILAS. En su lugar porque el modelo
    mando N consultas y tiene que recibir N resultados; sin filas porque
    copiarlas seria mandarle las mismas fichas dos veces en el mismo retorno,
    que es el gasto que esto saca.
    """
    una = {"categoria": "monitor", "busco": "varios"}
    otra = {"busco": "varios", "categoria": "monitor"}  # mismas claves, otro orden
    r = MT.buscar([una, otra, {"categoria": "mouse", "busco": "varios"}],
                  TIENDA)
    res = r["resultados"]
    assert len(res) == 3, "el modelo mando tres y tiene que recibir tres"
    assert not res[0].get("repetida") and res[0]["filas"]
    assert res[1].get("repetida"), "la segunda es identica y no se marco"
    assert res[1]["filas"] == [], "la repetida no puede repetir las filas"
    assert not res[2].get("repetida") and res[2]["filas"]


def test_el_reparto_del_pago_es_un_campo_de_primer_nivel(firestore_doble):
    """UNA COSA QUE EL CLIENTE DICE ES UN CAMPO.

    Nacio el 14-sep adentro de `cuenta`, y ahi el modelo tenia que tomar DOS
    decisiones para escribir algo que el cliente dijo una vez: resolver que
    quiere una cuenta, y recien ahi anotar el reparto. Medido cuatro veces en
    WhatsApp el 19-sep, "divide el presupuesto en setenta treinta" se declaro
    0 de 4: las cuatro se quedo en la primera decision.

    Y HAY MEDICION DE QUE LA FORMA MANDA: en esas mismas corridas `envios`
    —primer nivel, lista de textos— salio 4 de 4 y `condiciones` —anidado dos
    niveles y opcional— salio 0 de 4.
    """
    props = MT.esquema(TIENDA)["function"]["parameters"]["properties"]
    assert "reparto_pago" in props, "el reparto volvio a esconderse"
    assert "reparto_pago" not in props["cuenta"]["properties"], (
        "quedaron dos lugares para lo mismo")


def test_el_reparto_de_arriba_llega_a_la_cuenta(firestore_doble):
    """El campo subio en el tablero; la cuenta lo sigue leyendo de donde
    siempre. Si esto se corta, el modelo declara el setenta treinta y el total
    sale sin el descuento, que es peor que no tener el campo."""
    r = MT.buscar([], TIENDA, "t",
                  cuenta={"items": [{"id": "MOU0001", "cantidad": 2}]},
                  reparto_pago=[{"medio": "transferencia", "porcentaje": 70},
                                {"medio": "mercado pago", "porcentaje": 30}])
    c = r.get("cuenta") or {}
    assert c.get("total") and c.get("total_final")
    assert c["total_final"] != c["total"], (
        "el reparto no movio el total: el descuento no se aplico")

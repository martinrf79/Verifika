"""
EL BARRIDO DEL CODIGO — la otra mitad, la que ninguna fuente cubre.

POR QUE EXISTE. Los tres barridos del 11-ago enumeraron la FUENTE: los 880
productos por el certificador, los 50 temas por la guia, los pueblos por el
resolvedor de codigo postal. Sirvieron porque la fuente se puede recorrer
entera: tiene filas, y se cuentan. La cuenta no tiene filas. El componedor, la
aduana, el reconciliador, la calculadora y el split de pago no son datos que se
listan, son funciones que se COMBINAN, y ahi vivio el error de plata del 10-ago:
entre dos modulos que estaban los dos en verde.

QUE HACE ESTO, y es lo unico que hace: **genera las entradas en vez de
escribirlas**. Productos reales del catalogo por cantidades por extras por
destinos por formas de pago, el producto cartesiano entero, y sobre cada
resultado corre las propiedades. Nadie escribio la respuesta esperada de las
mil y pico de combinaciones, y no hace falta: una propiedad no compara contra un
texto, afirma algo que tiene que valer siempre.

LO QUE ENCONTRO EN LA PRIMERA CORRIDA, el 12-ago. Con "Sena 20%: $42.200 (pago
parcial)" escrito en la cuenta, el cobro le pedia al cliente el TOTAL, $211.000,
cinco veces lo que la cuenta dice que se paga ahora. Los dos modulos estaban
bien: la calculadora escribia la seña correcta y el cobro leia el total
correcto. Ninguna charla grabada tenia una seña, asi que ningun test lo habia
visto nunca, y los invariantes tampoco lo veian porque la regla estaba escrita
para el reparto y no para la seña. Es la misma costura del 10-ago, un metro mas
adelante.

LAS DOS CLASES DE PROPIEDAD, y las dos hacen falta:

  1. LOS INVARIANTES (`banco_pruebas/invariantes.py`) sobre el mensaje que sale.
     Miran que el texto no se contradiga a si mismo. Son ciegos a un envio
     cobrado de mas: un mensaje puede ser perfectamente coherente y cobrar mal.
  2. LAS PROPIEDADES CRUZADAS, que es lo que agrega este archivo. No
     recalculan la cuenta -eso seria escribirla dos veces y que las dos
     mientan-. Afirman relaciones ENTRE corridas: que la seña no mueva el
     total, que el descuento no se cobre dos veces por dos caminos distintos,
     que tres destinos cobren la suma de sus tres tarifas, que una unidad mas
     sume exactamente su precio.

CORRE OFFLINE Y GRATIS. Doble local de Firestore con el catalogo y la FAQ
reales, cero llamadas al modelo, cero credenciales.
"""
import itertools

import pytest

from banco_pruebas import invariantes as INV

TIENDA = "verifika_prod"

# Los extras que el modelo puede pedir, que salen de la FAQ cuantitativa real.
ENVIO = {"faq_tema": "costo_envio", "concepto": "envio_caba_gba"}
DESC = {"faq_tema": "descuento_transferencia", "concepto": "descuento_transferencia"}
SENA = {"faq_tema": "reservas", "concepto": "sena_reserva"}
CUOTAS = {"faq_tema": "cuotas", "concepto": "cuotas_sin_interes"}

COMBOS_EXTRA = ([], [ENVIO], [DESC], [ENVIO, DESC], [SENA], [ENVIO, DESC, SENA],
                [CUOTAS, ENVIO])

# Un destino cotizado por cada envio declarado: la calculadora se niega a cobrar
# un envio sin cotizar, y hace bien.
LOCALIDADES = {
    1: ["Cordoba, provincia de Cordoba"],
    2: ["Cordoba, provincia de Cordoba", "Rosario, Santa Fe"],
    3: ["Cordoba, provincia de Cordoba", "Rosario, Santa Fe",
        "La Plata, Buenos Aires"],
}

REPARTOS = (
    None,
    [{"medio": "transferencia", "porcentaje": 50},
     {"medio": "mercado pago", "porcentaje": 50}],
    [{"medio": "transferencia", "porcentaje": 65},
     {"medio": "mercado pago", "porcentaje": 35}],
    [{"medio": "transferencia", "porcentaje": 33},
     {"medio": "mercado pago", "porcentaje": 67}],
    [{"medio": "transferencia", "porcentaje": 100}],
)

# Datos de transferencia de demo: el bloque de cobro que lee el cliente se arma
# igual que en produccion, con el CBU de la tienda. Aca alcanza con que exista.
_DATOS_CBU = {"cbu": "0000003100010000000001", "alias": "verifika.demo"}


@pytest.fixture(scope="module")
def entorno(firestore_doble):
    """Catalogo real, tienda seteada, y la muestra de productos del barrido.

    La muestra es DETERMINISTA y se abre a lo ancho del rango de precios: ocho
    productos del mas barato al mas caro. Con el catalogo entero el producto
    cartesiano no termina nunca; con ocho puntos bien repartidos las
    combinaciones de plata que importan -redondeos, umbral de envio gratis,
    porcentajes que no dan entero- aparecen igual.
    """
    from app.core.contexto_turno import set_current_tienda
    from app.storage.firestore_client import get_all_products

    set_current_tienda(TIENDA)
    prods = [p for p in get_all_products(tienda_id=TIENDA)
             if p.get("stock", 0) >= 3 and p.get("precio_ars")]
    prods.sort(key=lambda p: p["precio_ars"])
    muestra = [prods[int(i * (len(prods) - 1) / 7)] for i in range(8)]
    return {
        "muestra": muestra,
        "precio": {p["id"]: p["precio_ars"] for p in prods},
        "vocabulario": {p["nombre"] for p in prods},
    }


def _calcular(carro, extras, destinos=1, pago=None):
    """Una corrida de la cuenta por el camino VIVO, con los destinos cotizados
    como los cotiza un turno de verdad."""
    from app.core import estado_venta
    from app.core.calculadora import calculate_total

    estado_venta._envio_localidades.set([])
    for loc in LOCALIDADES[destinos]:
        estado_venta.set_envio_localidad(loc)
    return calculate_total(items=[dict(i) for i in carro],
                           items_extra=[dict(e) for e in extras],
                           destinos=destinos, pago=pago)


def _carros(muestra, cuantos=4):
    """Los pedidos generados: de uno a tres productos distintos, con
    cantidades distintas, que es la forma de un pedido real."""
    out = []
    for n in (1, 2, 3):
        for combo in itertools.islice(itertools.combinations(muestra, n), cuantos):
            out.append([{"product_id": p["id"], "cantidad": c}
                        for c, p in zip((1, 2, 3), combo)])
    return out


def _mensaje_al_cliente(resultado):
    """Lo que el cliente LEE de verdad: el presupuesto mas el bloque de cobro.

    La costura importa mas que las dos puntas. El error del 10-ago no estaba ni
    en la cuenta ni en los datos de transferencia: estaba en que el segundo no
    miraba lo que decia el primero."""
    from app.core import pago as PAGO

    presupuesto = resultado.get("presentacion") or ""
    cobro = PAGO.monto_a_cobrar(presupuesto, "cbu")
    if not cobro:
        return presupuesto, None
    return (presupuesto + "\n\n"
            + PAGO.mensaje_transferencia(_DATOS_CBU, cobro)), cobro


# ── 1. EL BARRIDO GRANDE: toda combinacion, contra los invariantes ──────────

@pytest.fixture(scope="module")
def barrido(entorno):
    """El producto cartesiano corrido UNA sola vez; los tests de abajo leen de
    aca. Devuelve las corridas y lo que fallo, con su detalle."""
    corridas = 0
    violaciones = []
    rechazos = []
    for carro in _carros(entorno["muestra"]):
        for extras in COMBOS_EXTRA:
            for destinos in (1, 2, 3):
                for pago in REPARTOS:
                    corridas += 1
                    r = _calcular(carro, extras, destinos, pago)
                    if not r.get("ok"):
                        rechazos.append((len(carro), len(extras), destinos,
                                         bool(pago),
                                         (r.get("mensaje_para_llm") or "")[:80]))
                        continue
                    texto, _cobro = _mensaje_al_cliente(r)
                    for f in INV.revisar(texto,
                                         vocabulario=entorno["vocabulario"]):
                        violaciones.append({**f, "entrada": (
                            len(carro), len(extras), destinos, bool(pago))})
    return {"corridas": corridas, "violaciones": violaciones,
            "rechazos": rechazos}


def test_el_barrido_recorre_el_espacio_entero(barrido):
    """Que el generador no se apague solo. Si un cambio deja las corridas en
    cero, los tests de abajo pasarian vacios y nadie se enteraria: es
    exactamente la trampa del tablero verde que este repo ya pago."""
    assert barrido["corridas"] > 1000, (
        f"el barrido corrio {barrido['corridas']} combinaciones: se apago")


def test_ninguna_combinacion_viola_un_invariante(barrido):
    """Ninguna de las mil y pico de cuentas generadas se contradice a si misma
    ni contradice a su cobro. Incluye la costura donde vivio el error de plata
    del 10-ago: el bloque de transferencia se arma con el monto que sale del
    presupuesto, no con uno recalculado aparte."""
    v = barrido["violaciones"]
    assert not v, (f"{len(v)} violaciones en {barrido['corridas']} corridas, "
                   f"p.ej. {v[0]}")


def test_la_cuenta_no_se_niega_a_calcular_una_entrada_valida(barrido):
    """Toda entrada del barrido es legitima -productos con stock, extras de la
    FAQ real, destinos cotizados-, asi que ninguna puede terminar en ok False.
    Un rechazo aca es el bot diciendole que no a una venta que podia hacer."""
    r = barrido["rechazos"]
    assert not r, f"{len(r)} entradas validas rechazadas, p.ej. {r[0]}"


# ── 2. LAS PROPIEDADES CRUZADAS: lo que los invariantes no pueden ver ───────

def test_la_sena_no_mueve_el_total(entorno):
    """Una seña es un pago PARCIAL: dice cuanto se paga ahora, no cambia lo que
    se debe. Si moviera el total, el cliente pagaria dos veces la diferencia."""
    for carro in _carros(entorno["muestra"]):
        base = _calcular(carro, [])
        con = _calcular(carro, [SENA])
        assert con["ok"] and base["ok"]
        assert con["total_ars"] == base["total_ars"], (
            f"la seña movio el total: {con['total_ars']} vs {base['total_ars']}")


def test_las_cuotas_no_mueven_el_total(entorno):
    """Seis cuotas es una cantidad, no pesos. El dia que se sumen al total, seis
    pesos de mas en la cuenta."""
    for carro in _carros(entorno["muestra"]):
        base = _calcular(carro, [])
        con = _calcular(carro, [CUOTAS])
        assert con["ok"] and base["ok"]
        assert con["total_ars"] == base["total_ars"], (
            f"las cuotas movieron el total: {con['total_ars']}")


def test_el_descuento_da_igual_por_los_dos_caminos_y_no_se_cobra_dos_veces(entorno):
    """EL DESCUENTO POR TRANSFERENCIA TIENE DOS PUERTAS y tienen que dar el
    mismo numero: pedirlo como extra de la FAQ, o repartir el pago 100% por
    transferencia. Y pedirlo por las DOS a la vez no puede descontar dos veces
    -la calculadora saca el extra cuando hay reparto, y esto lo comprueba-."""
    solo_transferencia = [{"medio": "transferencia", "porcentaje": 100}]
    for carro in _carros(entorno["muestra"]):
        por_extra = _calcular(carro, [DESC])
        por_reparto = _calcular(carro, [], pago=solo_transferencia)
        por_los_dos = _calcular(carro, [DESC], pago=solo_transferencia)
        assert por_extra["ok"] and por_reparto["ok"] and por_los_dos["ok"]
        assert por_reparto["total_final_ars"] == por_extra["total_ars"], (
            f"reparto {por_reparto['total_final_ars']} vs extra "
            f"{por_extra['total_ars']}")
        assert por_los_dos["total_final_ars"] == por_reparto["total_final_ars"], (
            "el descuento se aplico dos veces: "
            f"{por_los_dos['total_final_ars']} vs "
            f"{por_reparto['total_final_ars']}")


def test_cada_destino_cobra_su_tarifa_y_mas_destinos_nunca_cobra_menos(entorno):
    """El envio de tres destinos es la suma de las tres tarifas cotizadas, no
    tres veces la ultima ni una sola. Las dos formas de romperlo ya pasaron en
    real: E5 colapsaba los destinos en uno, E13 duplicaba la ultima tarifa."""
    from app.core.calculadora import cotizar_envio

    for carro in _carros(entorno["muestra"]):
        subtotal = sum(entorno["precio"][i["product_id"]] * i["cantidad"]
                       for i in carro)
        envios = {}
        for d in (1, 2, 3):
            r = _calcular(carro, [ENVIO], destinos=d)
            assert r["ok"], f"no calculo con {d} destinos: {r}"
            envios[d] = r["total_ars"] - r["subtotal_productos_ars"]
        assert envios[1] <= envios[2] <= envios[3], (
            f"mas destinos cobra menos envio: {envios}")
        tarifas = [cotizar_envio(localidad=loc, subtotal=subtotal // 3)
                   for loc in LOCALIDADES[3]]
        if all(t.get("ok") and t.get("modalidad") != "rango" for t in tarifas):
            suma = sum(int(t.get("monto", 0)) for t in tarifas)
            assert envios[3] == suma, (
                f"tres destinos cobraron {envios[3]} y las tarifas suman {suma}")


def test_una_unidad_mas_suma_exactamente_su_precio(entorno):
    """La aritmetica mas basica de todas, y la unica que se puede afirmar sin
    volver a escribir la cuenta."""
    for carro in _carros(entorno["muestra"]):
        antes = _calcular(carro, [])
        mas = [dict(i) for i in carro]
        mas[0]["cantidad"] += 1
        despues = _calcular(mas, [])
        assert antes["ok"] and despues["ok"]
        salto = despues["total_ars"] - antes["total_ars"]
        esperado = entorno["precio"][carro[0]["product_id"]]
        assert salto == esperado, f"una unidad mas sumo {salto}, no {esperado}"


def test_el_reparto_reparte_la_base_entera_y_solo_descuenta_lo_que_no_es_mp(entorno):
    """Las tres cosas que el split no puede violar nunca: las partes suman la
    base, las partes finales suman el total final, y Mercado Pago no lleva el
    descuento por transferencia (que el 11-jul se lo llevo, y era plata)."""
    for carro in _carros(entorno["muestra"], cuantos=2):
        for extras in ([], [ENVIO]):
            for pago in REPARTOS[1:]:
                r = _calcular(carro, extras, pago=pago)
                assert r["ok"], f"no calculo con reparto: {r}"
                split = r["split_pago"]
                assert split["ok"]
                partes = split["partes"]
                assert sum(p["monto_ars"] for p in partes) == r["total_ars"]
                assert (sum(p["monto_final_ars"] for p in partes)
                        == r["total_final_ars"])
                for p in partes:
                    es_mp = "mercado" in p["medio"].lower()
                    assert bool(p["descuento_ars"]) is not es_mp or not p["descuento_ars"], (
                        f"Mercado Pago con descuento: {p}")


# ── 3. LA COSTURA DEL COBRO: la cuenta manda sobre lo que se pide ───────────

def test_lo_que_se_cobra_es_lo_que_la_cuenta_asigna_a_esa_via(entorno):
    """EL ERROR DEL 10-AGO, barrido en vez de anticipado. Con pago dividido, lo
    que se pide por transferencia es la parte de transferencia; sin reparto y
    sin seña, el total. Se comprueba en TODA combinacion, no en el caso que
    alguien se acordo de escribir."""
    from app.core import pago as PAGO

    for carro in _carros(entorno["muestra"], cuantos=2):
        for extras in ([], [ENVIO], [ENVIO, DESC]):
            for pago in REPARTOS:
                r = _calcular(carro, extras, pago=pago)
                assert r["ok"]
                presupuesto = r["presentacion"]
                cobro = PAGO.monto_a_cobrar(presupuesto, "cbu")
                split = r.get("split_pago") or {}
                if split.get("ok"):
                    esperado = next(
                        (p["monto_final_ars"] for p in split["partes"]
                         if "mercado" not in p["medio"].lower()), None)
                    if esperado is not None:
                        assert cobro == esperado, (
                            f"cobra {cobro} y la parte de transferencia es "
                            f"{esperado}")
                else:
                    assert cobro == r["total_ars"], (
                        f"cobra {cobro} y el total es {r['total_ars']}")


def test_con_sena_se_cobra_la_sena_y_no_el_total(entorno):
    """EL DEFECTO QUE ENCONTRO ESTE BARRIDO, 12-ago, con el numero en la mano.

    La cuenta decia "Sena 20%: $42.200 (pago parcial)" y el bloque de
    transferencia, tres renglones abajo, "Monto: $211.000". Cinco veces lo que
    la fuente dice que se paga para reservar -"con una sena del 20 por ciento te
    lo reservo"-. La calculadora escribia bien la seña y el cobro leia bien el
    total: cada modulo en verde, la costura rota, y ninguna charla grabada tenia
    una seña para que se viera."""
    from app.core import pago as PAGO

    for carro in _carros(entorno["muestra"], cuantos=3):
        for extras in ([SENA], [ENVIO, SENA], [ENVIO, DESC, SENA]):
            r = _calcular(carro, extras)
            assert r["ok"]
            presupuesto = r["presentacion"]
            sena = INV.pago_parcial(presupuesto)
            assert sena, f"la cuenta perdio la seña: {presupuesto}"
            cobro = PAGO.monto_a_cobrar(presupuesto, "cbu")
            assert cobro == sena, (
                f"se cobra {cobro} y la seña es {sena} (total "
                f"{r['total_ars']})")
            # Y el mensaje entero, como lo lee el cliente, queda sin violaciones.
            texto, _ = _mensaje_al_cliente(r)
            assert not INV.revisar(texto, vocabulario=entorno["vocabulario"])


def test_el_invariante_ve_el_cobro_del_total_habiendo_sena(entorno):
    """La otra mitad del arreglo: que el dia que vuelva a pasar, se vea. El
    invariante es el termometro: esta clase de falla no se parchea en el
    mensaje. FICHA 35: se lee de INV.revisar, no de un modulo de parche."""
    defectuoso = ("Presupuesto:\n"
                  "- 2x Mouse Logitech G600 MMO Negro: $105.500 c/u = $211.000\n"
                  "Subtotal: $211.000\n"
                  "Sena 20%: $42.200 (pago parcial)\n"
                  "Total: $211.000\n\n"
                  "Para pagar por transferencia:\n"
                  "CBU: 0000003100010000000001\n"
                  "Monto: $211.000")
    fallas = INV.revisar(defectuoso)
    reglas = [f["regla"] for f in fallas]
    assert "cobra_el_total_habiendo_sena" in reglas, fallas


# ── 4. EL COMPONEDOR Y LA ADUANA sobre mensajes generados ───────────────────

def test_el_componedor_no_mueve_un_peso_ni_rompe_la_cuenta(entorno):
    """Las seis reglas del componedor son LOSSLESS por diseño; esto lo mide
    sobre mensajes que nadie escribio. El 10-ago una regla nueva le corto 500
    caracteres por turno a una charla real sin haberse disparado ni una vez en
    los 176 turnos de las charlas grabadas: los casos escritos a mano no
    alcanzan para probar una tijera."""
    from app.core.mensaje import componer
    from banco_pruebas.invariantes import _importes

    for carro in _carros(entorno["muestra"], cuantos=3):
        for extras in COMBOS_EXTRA:
            for pago in (None, REPARTOS[1]):
                r = _calcular(carro, extras, pago=pago)
                assert r["ok"]
                texto, _ = _mensaje_al_cliente(r)
                compuesto = componer(texto, anterior="")
                assert _importes(compuesto) == _importes(texto), (
                    "el componedor movio la plata: "
                    f"{_importes(texto)} -> {_importes(compuesto)}")
                assert not INV.revisar(compuesto,
                                       vocabulario=entorno["vocabulario"])


def test_el_renglon_de_la_sena_no_parte_la_cuenta_en_dos(entorno):
    """EL SEGUNDO DEFECTO DEL BARRIDO, 12-ago, y este borraba el Total.

    La cadena, que ninguna de las dos puntas podia ver sola: el patron que
    reconoce un renglon de cuenta no incluia la seña, asi que
    "Sena 20%: $1.700 (pago parcial)" contaba como PROSA y cortaba el bloque en
    dos. La regla 5 del componedor comparaba los dos pedazos y encontraba que la
    firma del de abajo, "total: $8.500", estaba contenida en la del de arriba,
    que termina en "subtotal: $8.500" — contencion de letras, no de palabras—.
    Resultado: el renglon del Total se iba, y al cliente le llegaba un
    presupuesto sin total.

    Se arreglaron las dos: la seña es cuenta, y la contencion se mide entre
    palabras. Con una sola de las dos el defecto seguia vivo por el otro lado."""
    from app.core.mensaje import componer, sin_cuenta_dos_veces

    con_sena = ("Presupuesto:\n"
                "- 1x Mouse Genius DX-110 Negro: $8.500 c/u = $8.500\n"
                "Subtotal: $8.500\n"
                "Sena 20%: $1.700 (pago parcial)\n"
                "Total: $8.500")
    assert sin_cuenta_dos_veces(con_sena) == con_sena
    assert componer(con_sena, anterior="") == con_sena
    assert "Total: $8.500" in componer(con_sena, anterior="")


def test_la_aduana_no_toca_un_mensaje_sano(entorno):
    """Una aduana que corrige lo que ya estaba bien es peor que el defecto que
    arregla. FICHA 35: corre contra el snapshot, no contra el camino vivo.
    Sobre mil mensajes correctos generados, tiene que devolver el texto
    identico, caracter por caracter."""
    from test_aduana import revisar_salida

    for carro in _carros(entorno["muestra"], cuantos=3):
        for extras in COMBOS_EXTRA:
            for pago in (None, REPARTOS[1]):
                r = _calcular(carro, extras, pago=pago)
                assert r["ok"]
                texto, _ = _mensaje_al_cliente(r)
                salida = revisar_salida(texto, tienda_id="",
                                        vocabulario=entorno["vocabulario"])
                assert salida == texto, (
                    f"la aduana toco un mensaje sano: {len(texto)} -> "
                    f"{len(salida)}")


# ── 5. EL RECONCILIADOR sobre planes generados ──────────────────────────────

def _busqueda(categoria):
    return {"herramienta": "buscar_productos",
            "pedido": {"categoria": categoria, "descripcion": categoria},
            "resultado": {"productos": [{"nombre": f"Un {categoria} X",
                                         "categoria": categoria}]}}


def test_el_reconciliador_reclama_lo_que_falta_y_solo_lo_que_falta(firestore_doble):
    """El reconciliador compara lo que el modelo DIJO que entendio contra lo que
    PIDIO. Se barre el espacio entero: pedidos de uno a tres rubros por TODOS
    los subconjuntos de rubros efectivamente buscados.

    Las dos formas de fallar cuestan una ronda de modelo cada una, y las dos
    pasaron en real: no reclamar un item que se perdio -el auricular del 7-ago-,
    o reclamar uno que ya estaba atendido, que es el reclamo imposible que
    quemaba rondas hasta que se agrego el tercer estado."""
    from app.core.contexto_turno import set_current_tienda
    from app.core import pedido as P

    set_current_tienda(TIENDA)
    rubros = ["mouse", "teclado", "auriculares", "monitor", "notebook"]
    corridas = 0
    for k in (1, 2, 3):
        for items in itertools.combinations(rubros, k):
            declarado = {"items": [{"que": c, "cantidad": 1} for c in items]}
            for j in range(k + 1):
                for buscadas in itertools.combinations(items, j):
                    corridas += 1
                    rec = P.reconciliar(declarado, [_busqueda(c) for c in buscadas],
                                        "barrido", tienda_id=TIENDA)
                    reclamados = [str(x).lower() for x in rec["sin_buscar"]]
                    for c in items:
                        if c in buscadas:
                            assert not any(c == r.strip() for r in reclamados), (
                                f"reclama {c} habiendolo buscado: {reclamados}")
                        else:
                            assert any(c in r for r in reclamados), (
                                f"no reclama {c}, que nadie busco: {reclamados}")
                    assert len(reclamados) == len(set(reclamados)), reclamados
                    assert len(rec["faltantes"]) == len(set(rec["faltantes"]))
    assert corridas > 100, f"el barrido del reconciliador corrio {corridas}"


def test_lo_resuelto_en_turnos_anteriores_cuenta_como_atendido(firestore_doble):
    """El tercer estado, del lado de la memoria: un item que se resolvio hace
    dos turnos no se vuelve a reclamar aunque este turno no se haya buscado
    nada. Sin esto, 25 de los 41 faltantes repetidos del 7-ago."""
    from app.core.contexto_turno import set_current_tienda
    from app.core import pedido as P

    set_current_tienda(TIENDA)
    rubros = ["mouse", "teclado", "auriculares", "monitor", "notebook"]
    for k in (1, 2, 3):
        for items in itertools.combinations(rubros, k):
            declarado = {"items": [{"que": c, "cantidad": 1} for c in items]}
            rec = P.reconciliar(declarado, [], "barrido",
                                ya_resuelto=" ".join(items), tienda_id=TIENDA)
            assert not rec["sin_buscar"], (
                f"reclama {rec['sin_buscar']} sobre lo ya resuelto {items}")


# ── LOS TRES CAMINOS QUE FALTABAN, y estaban anotados como "A MEDIAS" ────────
#
# Este archivo declaro desde el 12-ago que le faltaban tres caminos de la
# calculadora: `grupos_envio`, el destino unico sticky y el envio cotizado en
# RANGO. Quedo escrito en PENDIENTE.md como "A MEDIAS" y asi paso una sesion
# entera, que es exactamente lo que Martin marco: "esta hecho el barrido o no
# esta hecho". Se cierran aca.

_ENVIO_RANGO = {"faq_tema": "costo_envio", "concepto": "envio_interior"}


def test_el_umbral_de_envio_gratis_se_decide_por_paquete_y_no_por_el_promedio(
        entorno):
    """CAMINO 1: `grupos_envio`. Con el pedido repartido, el envio gratis se
    decide con el subtotal REAL de cada paquete. Con el promedio, el paquete
    caro le regala el envio al barato y la tienda pierde plata en cada venta
    repartida."""
    from app.core import estado_venta
    from app.core.calculadora import calculate_total
    caro = max(entorno["muestra"], key=lambda p: p["precio_ars"])
    barato = min(entorno["muestra"], key=lambda p: p["precio_ars"])
    items = [{"product_id": caro["id"], "cantidad": 1},
             {"product_id": barato["id"], "cantidad": 1}]
    grupos = [{"destino": "cordoba capital",
               "cats": [{"n": 1, "cat": caro["categoria"]}]},
              {"destino": "rosario",
               "cats": [{"n": 1, "cat": barato["categoria"]}]}]
    estado_venta._envio_localidades.set([])
    for loc in ("cordoba capital", "rosario"):
        estado_venta.set_envio_localidad(loc)
    con = calculate_total(items=items, items_extra=[ENVIO], destinos=2,
                          grupos=grupos)
    estado_venta._envio_localidades.set([])
    for loc in ("cordoba capital", "rosario"):
        estado_venta.set_envio_localidad(loc)
    sin = calculate_total(items=items, items_extra=[ENVIO], destinos=2)
    assert con.get("ok") and sin.get("ok")
    # Con grupos NUNCA se cobra menos envio que con el promedio: el paquete
    # chico paga el suyo en vez de que se lo regale el grande.
    assert (con.get("total_ars") or 0) >= (sin.get("total_ars") or 0), (
        f"con grupos salio {con.get('total_ars')} y sin grupos "
        f"{sin.get('total_ars')}: el reparto por paquete regalo envio")


def test_el_destino_unico_sticky_cobra_un_solo_envio(entorno):
    """CAMINO 2: el destino unico. "Mandalo todo a Salta" despues de haber
    cotizado dos destinos no puede cobrar dos envios: el destino viejo quedo
    obsoleto. Es el bug real del 8-jul, mudanza Mendoza a Salta cobrada doble."""
    from app.core import estado_venta
    from app.core.calculadora import calculate_total
    p = entorno["muestra"][0]
    items = [{"product_id": p["id"], "cantidad": 1}]

    estado_venta.set_current_estado({"destino_unico": True,
                                     "localidades_envio": ["salta"]})
    estado_venta._envio_localidades.set([])
    for loc in ("cordoba capital", "salta"):
        estado_venta.set_envio_localidad(loc)
    uno = calculate_total(items=items, items_extra=[ENVIO], destinos=2)

    estado_venta.set_current_estado({})
    estado_venta._envio_localidades.set([])
    for loc in ("cordoba capital", "salta"):
        estado_venta.set_envio_localidad(loc)
    dos = calculate_total(items=items, items_extra=[ENVIO], destinos=2)
    estado_venta.set_current_estado(None)

    assert uno.get("ok") and dos.get("ok")
    assert (uno.get("total_ars") or 0) < (dos.get("total_ars") or 0), (
        "con destino unico se cobro lo mismo que con dos destinos: "
        f"{uno.get('total_ars')} contra {dos.get('total_ars')}")


def test_el_envio_en_rango_hoy_no_lo_puede_disparar_la_fuente(entorno):
    """CAMINO 3: el envio cotizado en RANGO, y la respuesta honesta es que HOY
    NO SE PUEDE ALCANZAR.

    Estuvo anotado como "falta barrer el envio en rango" y asi paso una sesion.
    Medido: la calculadora tiene la rama de rango escrita en dos lugares, pero
    el envio tiene UNA sola fuente -`cotizar_envio`- y el propio codigo declara
    que el concepto que manda el modelo se IGNORA. Y la tabla de tarifas de la
    fuente tiene las 24 provincias en modalidad FIJA. Con esos datos, ninguna
    entrada puede producir un envio en rango: la rama existe y esta muerta.

    En vez de dejarlo como pendiente para siempre, este test lo DECLARA y monta
    la guardia: cuenta las tarifas en rango que la fuente puede servir por el
    camino del envio. Mientras sean cero, no hay nada que barrer y esto pasa. El
    dia que alguien cargue una tarifa en rango, se pone rojo y pide el barrido,
    en el mismo push que la agrego y no tres sesiones despues."""
    from app.core.calculadora import cotizar_envio
    from app.core import estado_venta
    zonas = ("caba", "gba", "cordoba", "santa fe", "entre rios", "mendoza",
             "salta", "jujuy", "tucuman", "chaco", "corrientes", "misiones",
             "neuquen", "rio negro", "chubut", "santa cruz",
             "tierra del fuego", "la pampa", "san luis", "san juan",
             "la rioja", "catamarca", "formosa", "santiago del estero")
    estado_venta._envio_localidades.set([])
    en_rango = [z for z in zonas
                if (cotizar_envio(localidad=z) or {}).get("modalidad") == "rango"]
    assert not en_rango, (
        "la fuente ya sirve tarifas de envio en RANGO para "
        f"{en_rango}: el barrido tiene que cubrir ese camino. Agregale al "
        "generador un caso con esa localidad y afirma que la cuenta sale con "
        "sus dos extremos, no con un numero solo.")

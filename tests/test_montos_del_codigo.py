"""NINGUN MONTO LO ESCRIBE EL MODELO — FICHA 69, 15-oct-2026.

Lo visto en WhatsApp, K21: "el teclado va a Posadas". El modelo entendio bien
y la calculadora conto bien, pero el redactor escribio Posadas con los 10.000
de envio del presupuesto anterior y armo con eso el total y el 70/30. La
guarda vio cinco montos sin origen y tiro la respuesta entera.

La regla nueva, en tres partes: la cuenta la pone el codigo por su marca; solo
vale lo de este turno; un monto sin fuente se saca con su oracion y lo demas
sale. Reemplaza a `test_suma_verificada.py`: la suma a mano ya no es un camino.
"""
import random

from app.core import numeros as N

K120 = {"id": "TEC0029", "nombre": "Teclado Logitech K120 Negro", "precio_ars": 14500}
G203 = {"id": "MOU0001", "nombre": "Mouse Logitech G203 Lightsync Negro", "precio_ars": 37500}

# Lo que devolvio la calculadora para Posadas DESPUES del cambio: envio gratis.
POSADAS = {"total_ars": 651500, "total": "$651.500",
           "detalle": "Presupuesto Posadas:\n- 1x Teclado: $651.500\nEnvio: gratis\nTotal: $651.500"}
CALC = {"C1": {"detalle": POSADAS["detalle"], "vuelve": POSADAS}}


def test_la_marca_pone_el_bloque_exacto():
    salida, inf = N.llenar("Listo, te paso Posadas:\n{{cuenta:C1}}\nTe sirve?", [], "t", calculos=CALC)
    assert POSADAS["detalle"] in salida and "{{" not in salida
    assert inf["bloques"] == ["C1"] and not inf["inventada"]


def test_el_envio_del_presupuesto_viejo_no_sale_y_va_el_bloque():
    """K21: el redactor arma Posadas con los 10.000 viejos. Esa oracion se va
    y el cliente lee el bloque que calculo el codigo en este turno."""
    texto = "Posadas te queda en $661.500 con envio de $10.000. Algo mas?"
    salida, inf = N.llenar(texto, [], "t", calculos=CALC,
                           fuente_texto="ultimo presupuesto: envio $10.000")
    assert "661.500" not in salida
    assert POSADAS["detalle"] in salida and "Algo mas?" in salida
    assert inf["inventada"] and inf["bloques"] == ["C1"]


def test_la_suma_a_mano_se_va_y_los_precios_quedan():
    salida, inf = N.llenar("El K120 sale $14.500 y el G203 $37.500. Los dos, $52.000.", [K120, G203], "t")
    assert "$14.500" in salida and "$37.500" in salida and "52.000" not in salida
    assert inf["inventada"] == ["$52.000."]


def test_un_monto_sin_fuente_no_tumba_la_respuesta():
    salida, inf = N.llenar("Hola! Sale $99.999. Lo tenes en negro.", [K120], "t")
    assert "99.999" not in salida and "Lo tenes en negro." in salida


def test_si_todo_era_invento_se_dice_que_no_se_tiene_el_dato():
    salida, _ = N.llenar("Sale $99.999.", [K120], "t")
    assert salida and "99.999" not in salida and N.SIN_DATO in salida.lower()


def test_la_marca_de_un_calculo_que_no_existe_no_inventa():
    """La marca mal puesta dice que no tiene el dato, y el calculo que si hubo
    llega igual, al final."""
    salida, inf = N.llenar("{{cuenta:C9}}", [], "t", calculos=CALC)
    assert N.SIN_DATO in salida and "{{" not in salida and inf["sin_dato"] == ["cuenta:C9"]
    assert POSADAS["detalle"] in salida


def test_el_tablero_cambia_el_detalle_por_la_marca():
    """El redactor no ve los renglones de la cuenta: ve la marca."""
    from app.core import tablero as T
    llamadas = [{"herramienta": "cuenta", "vuelve": {"cuenta": POSADAS}}]
    hechos = [{"parte": "Posadas", "tipo": "cuenta", "resultado": {"cuenta": dict(POSADAS)}}]
    calc = T._calculos(hechos, llamadas)
    assert list(calc) == ["C1"] and calc["C1"]["detalle"] == POSADAS["detalle"]
    assert hechos[0]["resultado"]["cuenta"]["marca"] == "{{cuenta:C1}}"
    assert "detalle" not in hechos[0]["resultado"]["cuenta"]


def test_el_total_escrito_bien_a_mano_no_duplica_el_bloque():
    salida, inf = N.llenar("Posadas: $651.500 con envio gratis.", [], "t", calculos=CALC)
    assert salida.count("651.500") == 1 and not inf["inventada"]


def test_un_modelo_que_inventa_montos_nunca_llega_al_cliente():
    """El modelo de mentira: doscientas respuestas con precios buenos y montos
    al azar mezclados. Ningun monto inventado sale, y cada calculo del turno
    llega entero."""
    rnd = random.Random(69)
    buenos = {14500, 37500, 651500}
    corridas = 0
    for _ in range(200):
        oraciones, malos = [], set()
        for _ in range(rnd.randint(1, 6)):
            if rnd.random() < 0.5:
                m = rnd.randint(1000, 2_000_000)
                if m in buenos:
                    continue
                malos.add(m)
                oraciones.append(f"Eso sale ${m:,}.".replace(",", "."))
            else:
                oraciones.append(rnd.choice(["El K120 sale $14.500.", "El G203 sale $37.500.", "Te sirve?",
                                             "{{cuenta:C1}}"]))
        salida, _ = N.llenar(" ".join(oraciones), [K120, G203], "t", calculos=CALC)
        digitos = N._digitos(salida)
        assert not {str(m) for m in malos} & digitos, (oraciones, salida)
        assert POSADAS["detalle"] in salida
        corridas += 1
    assert corridas == 200


def test_la_cuenta_de_una_reserva_lleva_la_cantidad_reservada(firestore_doble):
    """K11: "dale, sumame 3 de esos teclados" reservaba 3 y la cuenta salia con 1."""
    from app.core import tablero as T
    llamadas = [{"herramienta": "reservar", "args": {"producto": "TEC0020", "cantidad": 3},
                 "vuelve": {"veredicto": "listo_para_cerrar", "id": "TEC0020", "cantidad": 3}}]
    ctx = {"estado": {}, "mensaje": "dale, sumame 3 de esos teclados", "historial": []}
    T._cuenta_del_codigo([{"tipo": "comprar", "producto": "teclado", "cantidad": 3}], llamadas, "verifika_prod", ctx, 3)
    cuenta = next(x for x in llamadas if x["herramienta"] == "cuenta")
    assert cuenta["args"]["items"] == [{"producto": "TEC0020", "cantidad": 3}]


def test_varios_bloques_sin_marca_llegan_enteros():
    """K21: con tres destinos sin marca, el filtro de un bloque borraba los
    renglones de otro ya agregado."""
    a = {"total_ars": 73500, "detalle": "A:\n- 1x Zeus X: $57.500 c/u = $57.500\nTotal: $73.500"}
    b = {"total_ars": 136500, "detalle": "B:\n- 1x Zeus X: $57.500 c/u = $57.500\nTotal: $136.500"}
    calc = {"C1": {"detalle": a["detalle"], "vuelve": a}, "C2": {"detalle": b["detalle"], "vuelve": b}}
    salida, inf = N.llenar("Listo, va el pedido.", [], "t", calculos=calc)
    assert a["detalle"] in salida and b["detalle"] in salida and inf["bloques"] == ["C1", "C2"]


def test_un_renglon_sin_plata_no_se_borra_por_su_spec():
    """"2x Memoria DDR4 3200" no repite plata del bloque: el 3200 es la spec."""
    salida, _ = N.llenar("A Posadas:\n- 2x Memoria DDR4 3200 8GB", [], "t", calculos=CALC,
                         fuente_texto="DDR4 3200")
    assert "2x Memoria DDR4 3200 8GB" in salida and POSADAS["detalle"] in salida


def test_un_reparto_con_un_solo_medio_se_completa_con_el_resto():
    """K21: "70 por ciento transferencia" es un 70/30; el 30 va sin medio y sin descuento."""
    from app.core import tablero as T
    from app.core.agente import CLIENTE_DIJO
    CLIENTE_DIJO.set("70 por ciento transferencia")
    rep = T._reparto([{"medio": "transferencia", "porcentaje": 70}])
    assert rep == [{"medio": "transferencia", "porcentaje": 70}, {"medio": "el resto", "porcentaje": 30}]


def test_un_renglon_corto_que_repite_plata_del_bloque_marcado_se_va():
    """K21 con Gemini: despues de cada presupuesto quedaba un "$7.500" suelto."""
    salida, _ = N.llenar("A Posadas:\n{{cuenta:C1}}\n$651.500\nTe sirve?", [], "t", calculos=CALC)
    assert salida.count("651.500") == POSADAS["detalle"].count("651.500") and "Te sirve?" in salida

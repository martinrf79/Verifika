"""
Regresion del verificador determinista, la linea cero anti-alucinacion de plata.

Cubre tres errores confirmados. Estos tests estan escritos para el comportamiento
CORRECTO, asi que HOY fallan (rojo). Cada uno se apaga cuando se arregla su error.

  E1  El total de un pedido con varios envios distintos no se deriva como suma:
      _totales_derivables trata los envios como alternativas, nunca los suma. Un
      total que se come un envio no se distingue de uno valido.
  E2  Un numero de plata sin formato (sin puntos, sin signo, sin 'pesos') esquiva
      el verificador entero: no se cuenta como monto y pasa sin control.
  E7  Cualquier numero suelto en la prosa de una FAQ entra al pool de verdad y
      blanquea cualquier precio alucinado que coincida con el.
"""
from app.core import verificador


def test_e1_total_multienvio_se_deriva_como_suma():
    """E1: con dos envios distintos, el gran total que suma AMBOS tiene que ser
    derivable del PROOF. Hoy no lo es (solo deriva subtotal + cada envio suelto)."""
    proof = {
        "tipo": "calculo_total_fijo",
        "subtotal_productos": 100000,
        "operandos_productos": [{"id": "A", "monto": 100000}],
        "operandos_extras": [
            {"faq_tema": "costo_envio", "concepto": "env_cordoba",
             "modalidad": "fijo", "monto": 8000},
            {"faq_tema": "costo_envio", "concepto": "env_caba",
             "modalidad": "fijo", "monto": 5000},
        ],
        "resultado": 113000,
    }
    derivables = verificador._totales_derivables(proof)
    assert 113000 in derivables, (
        "El total con los dos envios (100000+8000+5000) debe ser derivable; "
        "hoy los envios se tratan como alternativas y no se suman.")


def test_e1_total_que_come_un_envio_se_bloquea():
    """E1: un total al que le falta un envio no debe validar como correcto."""
    proof = {
        "tipo": "calculo_total_fijo",
        "subtotal_productos": 100000,
        "operandos_productos": [{"id": "A", "monto": 100000}],
        "operandos_extras": [
            {"faq_tema": "costo_envio", "concepto": "env_cordoba",
             "modalidad": "fijo", "monto": 8000},
            {"faq_tema": "costo_envio", "concepto": "env_caba",
             "modalidad": "fijo", "monto": 5000},
        ],
        "resultado": 113000,
    }
    ev = [{"tipo": "proof", "proof": proof}]
    # 108000 = subtotal + solo el envio de cordoba, se olvida el de CABA.
    r = verificador.verificar_respuesta("El total final es $108.000", ev)
    assert not r["ok"], (
        "Un total que se come un envio no debe pasar como valido.")


def test_e2_monto_sin_formato_se_verifica():
    """E2: un precio alucinado escrito sin puntos ni signo igual tiene que
    verificarse y bloquearse, no esquivar el control."""
    ev = [{"tipo": "producto", "nombre": "Mouse Gamer", "precio_ars": 45000}]
    r = verificador.verificar_respuesta("El combo te sale 999999 en total", ev)
    assert not r["ok"], (
        "999999 es un precio sin respaldo; sin formato hoy se cuela sin control.")


def _ev_multienvio():
    """Evidencia de un pedido con 3 envios a zonas distintas: la calculadora dio
    el subtotal de productos y el solver cotizo cada destino por separado (un
    PROOF de envio por zona). El gran total correcto es 100000+7500+9000+5000."""
    return [
        {"tipo": "proof", "proof": {
            "tipo": "calculo_total_fijo", "subtotal_productos": 100000,
            "operandos_productos": [{"id": "A", "monto": 100000}],
            "operandos_extras": [], "resultado": 100000}},
        {"tipo": "proof", "proof": {"tipo": "envio", "resultado": 7500}},
        {"tipo": "proof", "proof": {"tipo": "envio", "resultado": 9000}},
        {"tipo": "proof", "proof": {"tipo": "envio", "resultado": 5000}},
    ]


def test_multienvio_total_suma_cotizaciones_valida():
    """El gran total de un multienvio es el subtotal mas la suma de TODAS las
    cotizaciones de envio. Debe validar; hoy ningun PROOF suelto lo derivaba."""
    r = verificador.verificar_respuesta(
        "El total con los tres envios es $121.500", _ev_multienvio())
    assert r["ok"], (
        "subtotal 100000 + envios 7500+9000+5000 = 121500 es el total correcto "
        "del multienvio y debe estar respaldado.")


def test_multienvio_total_que_come_un_envio_no_valida():
    """Un total que se olvida uno de los tres envios no debe pasar como valido."""
    r = verificador.verificar_respuesta(
        "El total con los tres envios es $116.500", _ev_multienvio())
    assert not r["ok"], (
        "116500 = subtotal + solo 2 de 3 envios; se come uno y no debe validar.")


def test_multienvio_autocorrige_hacia_el_total_real():
    """El corrector debe llevar un total que se comio un envio al total real del
    multienvio, no al subtotal pelado sin ningun envio."""
    fix = verificador.autocorregir_montos(
        "El total con los tres envios es $116.500", _ev_multienvio())
    assert fix["cambiada"] and fix["verificacion"]["ok"]
    assert "121.500" in fix["respuesta"], (
        "debe corregir hacia 121500 (subtotal + los 3 envios), no a 100000.")


def test_a_repite_presupuesto_de_memoria_sin_tools_no_bloquea():
    """A: cuando queda una cifra sin respaldo pero HAY evidencia en memoria
    (proofs o productos vistos en turnos anteriores), la melliza activa NO
    bloquea con el canned: el solver repitio un presupuesto ya calculado y sus
    cifras son legitimas. Hoy se bloquea por 'este turno no llamo tools', que
    mataba un presupuesto bueno."""
    accion = verificador.decidir_accion_no_respaldado(
        verificacion_ok=False, hay_tools=False, hay_memoria=True)
    assert accion != "bloquear", (
        "con evidencia en memoria no debe salir el canned, aunque este turno "
        "no se hayan llamado herramientas.")


def test_a_sin_tools_sin_memoria_bloquea():
    """A: si no hay NINGUNA evidencia, ni tools este turno ni memoria, una cifra
    sin respaldo es alucinacion pura y SI se bloquea. La correccion de A no debe
    aflojar esta linea cero."""
    accion = verificador.decidir_accion_no_respaldado(
        verificacion_ok=False, hay_tools=False, hay_memoria=False)
    assert accion == "bloquear", (
        "sin tools y sin memoria, un numero sin respaldo no tiene de donde "
        "salir: es alucinacion y no debe llegar al cliente.")


def test_a_verificacion_ok_siempre_responde():
    """A: si la verificacion cierra, se responde, haya o no memoria o tools."""
    assert verificador.decidir_accion_no_respaldado(
        verificacion_ok=True, hay_tools=False, hay_memoria=False) == "responder"


def test_e7_numero_de_prosa_faq_no_respalda_precio():
    """E7: un numero que solo aparece en el texto libre de una FAQ no debe servir
    para blanquear un precio de producto alucinado."""
    ev = [{"tipo": "faq",
           "respuesta": "Compras mayores a 150000 tienen envio gratis."}]
    r = verificador.verificar_respuesta("Ese monitor sale $150.000", ev)
    assert not r["ok"], (
        "150000 viene de la prosa de la FAQ, no es un precio de catalogo; "
        "no debe respaldar un precio de producto.")


def test_productos_nombrados_entran_a_la_evidencia(firestore_doble):
    """La evidencia se completa con los productos que la respuesta NOMBRA con
    su nombre completo, para que la melliza pueda juzgar una linea de producto
    tipeada a mano sin tool ni marcador (visto en el banco: NX-7000 con precio
    y stock de fantasia que nadie pudo corregir)."""
    from app.core.evidencia import productos_nombrados_en

    r = "Mira, el Mouse Genius NX-7000 Negro - $8.000 (11 en stock) va joya."
    nombrados = productos_nombrados_en(r)
    assert [p["id"] for p in nombrados] == ["MOU0049"]
    assert nombrados[0]["precio_ars"] == 14000
    assert nombrados[0]["stock"] == 18
    assert productos_nombrados_en("hola, buen dia") == []


def test_precio_ancla_nombre_completo_gana_a_hermanos_de_marca():
    """El precio tipeado a mano junto al nombre COMPLETO se corrige aunque
    hermanos de la marca en la evidencia empaten por tokens (banco: '$8.000'
    junto a 'Mouse Genius NX-7000 Negro', real $14.000, quedaba ambiguo entre
    NX-7000 y DX-110 y no se corregia)."""
    from app.core.verificador import _precio_de_producto_nombrado

    ev = [
        {"tipo": "producto", "id": "MOU0049",
         "nombre": "Mouse Genius NX-7000 Negro", "precio_ars": 14000},
        {"tipo": "producto", "id": "MOU0023",
         "nombre": "Mouse Genius DX-110 Negro", "precio_ars": 8500},
    ]
    texto = "El mas barato es este: Mouse Genius NX-7000 Negro - $8.000"
    pr = _precio_de_producto_nombrado(texto, texto.index("$8.000"), ev)
    assert pr == 14000

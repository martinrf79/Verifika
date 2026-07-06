"""
Regresion de la guardia de promesas prohibidas (deteccion determinista de texto).

  E3  Deja pasar una fecha de entrega dicha por numero y mes, 'el 25 de junio':
      el patron de dia solo ve formatos tipo 25/6, no el mes en palabra.
  E4  Dispara en falso sobre las negaciones honestas de la propia tienda:
      'no hacemos retiro por local' o 'no hacemos instalacion' se marcan como si
      fueran la promesa, cuando son justo lo contrario.
"""
from app.core import guardia_promesas


def test_e3_detecta_fecha_por_numero_y_mes():
    """E3: 'el 25 de junio' con contexto de llegada es una fecha prometida."""
    clases = guardia_promesas.detectar("te llega el 25 de junio a tu casa")
    assert "dia_entrega" in clases, (
        "Prometer 'el 25 de junio' es prometer una fecha exacta de entrega.")


def test_e4_no_dispara_en_negacion_de_retiro():
    """E4: negar el retiro por local es honesto, no debe marcarse."""
    clases = guardia_promesas.detectar(
        "No tenemos retiro por local, somos solo online")
    assert clases == [], (
        "Negar el retiro es la politica correcta, no una promesa prohibida.")


def test_promesa_dia_de_semana_con_tengas():
    """Charla real 6-jul: 'entre miercoles y viernes de la semana que viene ya
    tengas todo' es promesa de dia de entrega y se filtro (la guarda no cazaba
    'tengas' ni 'semana que viene')."""
    clases = guardia_promesas.detectar(
        "lo mas probable es que entre miercoles y viernes de la semana que viene "
        "ya tengas todo en cada destino")
    assert "dia_entrega" in clases


def test_promesa_semana_que_viene():
    clases = guardia_promesas.detectar("lo tenes la semana que viene sin falta")
    assert "dia_entrega" in clases


def test_tengas_sin_dia_no_dispara():
    """'cuando tengas los datos' no nombra un dia: no es promesa de entrega."""
    assert guardia_promesas.detectar(
        "cuando tengas los datos te confirmo el pedido") == []


def test_e4_no_dispara_en_negacion_de_servicio():
    """E4: negar un servicio que no se ofrece es honesto, no debe marcarse."""
    clases = guardia_promesas.detectar(
        "No hacemos instalacion a domicilio, disculpa")
    assert clases == [], (
        "Negar la instalacion es honesto, no una promesa prohibida.")


# ── Red determinista cuando el editor LLM falla (hueco real 4-jul) ───────────
# DeepSeek devolvio la reescritura VACIA dos veces y una direccion de local
# inventada salio al cliente. La cuarentena poda las LINEAS con promesa.

def test_cuarentena_poda_la_linea_entera_con_la_invencion():
    from app.core.guardia_promesas import cuarentena_prohibidas
    texto = ("Si, tenemos local para retirar sin costo. Estamos en Montevideo "
             "540, CABA. Podes pasar de lunes a viernes de 10 a 19 hs.\n"
             "El total queda en $17.000.\n"
             "Que preferis?")
    out = cuarentena_prohibidas(texto)
    assert "Montevideo" not in out and "local" not in out
    assert "$17.000" in out and "Que preferis?" in out


def test_cuarentena_todo_promesa_devuelve_vacio():
    from app.core.guardia_promesas import cuarentena_prohibidas
    assert cuarentena_prohibidas("Podes pasar a retirar por el local.") == ""


def test_negacion_con_sin_no_dispara():
    # La curada oficial de retiro ('tienda online, sin punto de retiro') es
    # honestidad, no promesa: la guardia no debe dispararle a nuestro bloque.
    from app.core.guardia_promesas import detectar
    assert detectar("Somos tienda online, sin punto de retiro: todo va por "
                    "envio a la direccion que nos digas.") == []
    # Un 'sin' inconexo no tapa una promesa real.
    assert detectar("Sin problema, podes pasar a retirar por el local.") != []


# ── Datos de pago fabricados (visto en real 4-jul: CBU y alias inventados) ───

def test_detecta_cbu_alias_y_titular_inventados():
    from app.core.guardia_promesas import detectar
    msg = ("Te paso los datos para la transferencia:\n"
           "- Banco: Santander Rio\n"
           "- Titular: Verifika S.A.\n"
           "- CBU: 0720075488000001234567\n"
           "- Alias: VERIFIKA.TRANSFERENCIA\n"
           "- Monto exacto: $237.000")
    assert "datos_pago" in detectar(msg)


def test_promesa_inocente_de_cbu_no_dispara():
    from app.core.guardia_promesas import detectar
    assert detectar("Apenas confirmes, te paso el CBU para transferir.") == []
    assert detectar("Te mando los datos de la cuenta al cerrar el pedido.") == []


def test_cuarentena_poda_el_bloque_bancario_entero():
    from app.core.guardia_promesas import cuarentena_prohibidas
    msg = ("Perfecto, vamos con eso!\n"
           "Banco: Santander Rio\n"
           "Titular: Verifika S.A.\n"
           "CBU: 0720075488000001234567\n"
           "Alias: VERIFIKA.PAGO\n"
           "Decime tu nombre completo para armar el pedido.")
    out = cuarentena_prohibidas(msg)
    assert "0720" not in out and "Santander" not in out and "VERIFIKA.PAGO" not in out
    assert "Perfecto" in out and "nombre completo" in out

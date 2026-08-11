"""
AREA: EL COMPONEDOR — el largo del mensaje, en un solo lugar (`app/core/mensaje.py`).

Cada test es un caso MEDIDO sobre las charlas grabadas reproducidas por el
camino vivo, no un caso inventado: el turno 1 del guion 76 salio en 2.434
caracteres con la misma frase tres veces, y el turno 2 repitio el bloque entero
del turno 1. Logica pura, sin red y sin clave.

La otra mitad de estos tests es la que importa: que el componedor NO se lleve
la cuenta, NO se lleve una pregunta y NO deje el mensaje mudo. Podar de mas es
el error que este repo ya pago dos veces.
"""
from app.core.mensaje import (componer, sin_encabezados_huerfanos,
                              sin_lo_ya_dicho, sin_producto_duplicado,
                              sin_repeticion_interna,
                              un_ejemplo_por_rubro_con_cuenta)


# ── REGLA 1: un renglon no se dice dos veces ────────────────────────────────
def test_la_frase_pegada_tres_veces_sale_una():
    cola = ("Donde sí se cumple del todo lo que pedís es en: almacenamiento "
            "externo, procesador.")
    texto = (f"Lo que más se acerca, entre los auriculares:\n"
             f"- Auriculares Zeus: $57.500\n{cola}\n"
             f"Lo que más se acerca, entre los mouse:\n"
             f"- Mouse Genius: $8.500\n{cola}\n"
             f"Lo que más se acerca, entre las memorias:\n"
             f"- Memoria Kingston: $34.500\n{cola}")
    out = sin_repeticion_interna(texto)
    assert out.count(cola) == 1
    # los tres productos siguen estando: no se perdio un dato
    for p in ("Auriculares Zeus", "Mouse Genius", "Memoria Kingston"):
        assert p in out


def test_los_renglones_de_la_cuenta_no_se_deduplican():
    """Dos renglones iguales en una cuenta son plata, no una coletilla: el
    mismo producto puede venir partido en dos destinos."""
    texto = ("Presupuesto:\n"
             "- 1x Mouse Genius DX-110 Negro: $8.500 c/u = $8.500\n"
             "- 1x Mouse Genius DX-110 Negro: $8.500 c/u = $8.500\n"
             "Total: $17.000")
    assert sin_repeticion_interna(texto) == texto


def test_la_linea_corta_repetida_no_se_toca():
    texto = "Listo.\nListo."
    assert sin_repeticion_interna(texto) == texto


# ── REGLA 2: lo que el cliente acaba de leer ────────────────────────────────
def test_el_bloque_entero_del_turno_anterior_no_vuelve():
    bloque = ("Hay 43 opciones igual de cerca y ninguna está mejor que otra, "
              "así que te muestro las tres más accesibles del grupo.")
    anterior = f"Te muestro lo que tengo.\n{bloque}"
    texto = f"{bloque}\nEl total con envío te queda en $225.000, ¿avanzamos?"
    out = sin_lo_ya_dicho(texto, anterior)
    assert bloque not in out
    assert "¿avanzamos?" in out


def test_la_cuenta_si_se_repite_cuando_el_cliente_reconfirma():
    """El renglon de cuenta es plata reestampada por el codigo. Repetirlo
    cuando el cliente vuelve sobre el pedido es lo correcto."""
    cuenta = "Total: $225.000"
    anterior = f"Presupuesto:\n- 2x Mouse: $8.500 c/u = $17.000\n{cuenta}"
    out = sin_lo_ya_dicho(f"Te confirmo.\n{cuenta}", anterior)
    assert cuenta in out


def test_la_valvula_no_deja_el_mensaje_mudo():
    """Si sacar lo repetido se lleva todo, no se saca nada: un turno mudo es
    peor que un turno repetido."""
    frase = ("El envío a Córdoba capital te sale igual para cualquiera de los "
             "tres modelos que estuvimos viendo recién.")
    assert sin_lo_ya_dicho(frase, frase) == frase


# ── REGLA 3: un producto no se muestra dos veces ────────────────────────────
def test_el_producto_que_ya_esta_en_la_cuenta_no_se_lista_arriba():
    texto = ("Lo que más se acerca:\n"
             "- Auriculares Zeus X Negro: $57.500 — país de fabricación: china\n"
             "- Auriculares Zeus X Blanco: $57.500 — país de fabricación: china\n"
             "Presupuesto:\n"
             "- 2x Auriculares Zeus X Negro: $57.500 c/u = $115.000\n"
             "Total: $115.000")
    out = sin_producto_duplicado(texto)
    assert out.count("Auriculares Zeus X Negro") == 1
    # el hecho que el cliente pidio sigue en el renglon que queda
    assert "país de fabricación: china" in out
    assert "Total: $115.000" in out


def test_no_se_lleva_el_renglon_si_se_lleva_el_unico_dato():
    """Si el hecho distintivo vive SOLO en ese renglon, el renglon se queda.
    Mejor un mensaje mas largo que un mensaje sin el dato por el que
    preguntaron."""
    texto = ("Lo que más se acerca:\n"
             "- Auriculares Zeus X Negro: $57.500 — origen: taiwan\n"
             "- Auriculares Pandora: $62.500 — origen: china\n"
             "Presupuesto:\n"
             "- 2x Auriculares Zeus X Negro: $57.500 c/u = $115.000\n"
             "Total: $115.000")
    assert sin_producto_duplicado(texto) == texto


def test_sin_cuenta_no_toca_nada():
    texto = ("Lo que más se acerca:\n"
             "- Auriculares Zeus X Negro: $57.500\n"
             "- Auriculares Pandora: $62.500")
    assert sin_producto_duplicado(texto) == texto


# ── REGLA 3-bis: con cuenta, el listado no es la respuesta ──────────────────
_LISTADO_CON_CUENTA = (
    "Lo que más se acerca, entre los auriculares (43 igual de cerca):\n"
    "- Auriculares Zeus X Blanco: $57.500 — país de fabricación: china\n"
    "- Auriculares Pandora Negro: $62.500 — país de fabricación: china\n"
    "Lo que más se acerca, entre los mouse (45 igual de cerca):\n"
    "- Mouse Logitech M170 Negro: $12.000 — país de fabricación: china\n"
    "- Mouse Logitech M170 Blanco: $12.000 — país de fabricación: china\n"
    "Presupuesto:\n"
    "- 2x Auriculares Zeus X Negro: $57.500 c/u = $115.000\n"
    "Total: $115.000")


def test_con_cuenta_queda_un_ejemplo_por_rubro():
    out = un_ejemplo_por_rubro_con_cuenta(_LISTADO_CON_CUENTA)
    assert out.count("- Auriculares") == 1
    assert out.count("- Mouse Logitech") == 1
    # el hecho del rubro y el conteo siguen estando
    assert out.count("país de fabricación: china") == 2
    assert "43 igual de cerca" in out and "45 igual de cerca" in out
    # la cuenta entera, intacta
    assert "- 2x Auriculares Zeus X Negro: $57.500 c/u = $115.000" in out
    assert "Total: $115.000" in out
    assert len(out) < len(_LISTADO_CON_CUENTA)


def test_sin_cuenta_el_listado_es_la_respuesta_y_no_se_toca():
    solo_listado = "\n".join(_LISTADO_CON_CUENTA.splitlines()[:6])
    assert un_ejemplo_por_rubro_con_cuenta(solo_listado) == solo_listado


def test_el_renglon_con_otro_dato_se_queda_aunque_haya_cuenta():
    """Dos productos que difieren en el hecho que el cliente pidio son dos
    respuestas distintas, no una repetida."""
    texto = ("Lo que más se acerca:\n"
             "- Auriculares Zeus: $57.500 — origen: china\n"
             "- Auriculares Pandora: $62.500 — origen: taiwan\n"
             "Presupuesto:\n"
             "- 1x Mouse Genius: $8.500 c/u = $8.500\n"
             "Total: $8.500")
    assert un_ejemplo_por_rubro_con_cuenta(texto) == texto


# ── el encabezado que se queda colgado ──────────────────────────────────────
def test_el_encabezado_sin_lista_abajo_se_va():
    texto = ("Lo que más se acerca a lo que pediste, entre los mouse:\n"
             "Presupuesto:\n"
             "- 2x Mouse Genius: $8.500 c/u = $17.000\n"
             "Total: $17.000")
    out = sin_encabezados_huerfanos(texto)
    assert "entre los mouse" not in out
    assert "Presupuesto:" in out and "Total: $17.000" in out


# ── EL TOPE QUE SE PROBO Y SE FUE ──────────────────────────────────────────
def test_el_componedor_no_borra_prosa_por_largo():
    """EL CANDADO DE LA LECCION DEL 8-AGO. Hubo un presupuesto de largo que
    borraba bloques de prosa "decorativa" -sin plata y sin pregunta- cuando el
    mensaje pasaba el tope. Medido en vivo tiro la nota de 55 a 23: la unica
    condicion que el cliente habia puesto la explica el modelo en PROSA, y esa
    prosa no lleva plata ni signo de pregunta.

    Este test existe para que nadie lo reproponga sin leer el numero: un mensaje
    largo SIN nada repetido adentro sale entero."""
    largo = "\n\n".join(
        f"Sobre los {r}, te cuento que todo lo que trabajo de ese rubro se "
        f"fabrica en China, que es justo lo que me pediste evitar, así que te "
        f"marco cuál se acerca más y por qué."
        for r in ("auriculares", "mouse", "memorias", "teclados",
                  "monitores", "notebooks", "impresoras", "parlantes"))
    assert len(largo) > 1200
    assert componer(largo, anterior="") == largo


# ── la puerta unica ─────────────────────────────────────────────────────────
def test_componer_es_idempotente():
    texto = ("Lo que más se acerca:\n"
             "- Mouse Genius: $8.500 — origen: china\n"
             "- Mouse Logitech: $12.000 — origen: china\n\n"
             "¿Con cuál avanzamos?")
    una = componer(texto, anterior="")
    assert componer(una, anterior="") == una


def test_componer_no_toca_un_mensaje_corto_y_limpio():
    texto = "El Mouse Genius DX-110 sale $8.500 y tengo 10 en stock. ¿Te lo armo?"
    assert componer(texto, anterior="") == texto


def test_componer_nunca_devuelve_vacio():
    for t in ("", "   ", "ok", "Hola."):
        assert componer(t, anterior=t) == t


# ── LA VIDRIERA QUE CONTRADICE LA FACTURA: DEFECTO ABIERTO (9-ago-2026) ─────
# Del WhatsApp real de Martin: tres rubros mostrados en BLANCO arriba y
# cotizados en NEGRO abajo, con precios distintos. Se probo borrar el grupo
# entero cuando el rubro ya esta en la cuenta y se REVIRTIO con el numero: la
# nota viva cayo de 89 a 77 y el peor caso de 62 a 12, porque con el renglon se
# iba "país de fabricación: china", el unico criterio que el cliente puso.
# El arreglo verdadero es que el ejemplo que sobrevive sea EL DE LA CUENTA, no
# borrar mas. Este test fija lo que HOY hace, para que el intento siguiente vea
# en una corrida si cambio algo.

def test_hoy_el_ejemplo_que_queda_puede_no_ser_el_cotizado():
    """DEFECTO CONOCIDO, fijado a proposito y no disfrazado de verde. El dia
    que se arregle bien, este test se da vuelta y se le cambia el nombre."""
    from app.core import mensaje as M
    texto = ("Auriculares (43 igual de cerca):\n"
             "- Auriculares Redragon Zeus X Blanco: $57.500 — país de fabricación: china\n"
             "\n"
             "Presupuesto:\n"
             "- 2x Auriculares Redragon Zeus X Negro: $57.500 c/u = $115.000\n"
             "Total: $115.000")
    salida = M.un_ejemplo_por_rubro_con_cuenta(texto)
    assert "Blanco" in salida, "hoy sobrevive el que NO se cotizo"
    # y lo que NO puede perderse nunca, que es por lo que se revirtio el intento
    assert "país de fabricación: china" in salida


def test_el_reparto_por_destino_llega_entero():
    """EL BLOQUE DE REPARTO NO ES UN LISTADO, y confundirlo costo el turno real
    del 9-ago -trace 57ad6a0d-. La cuenta traia los tres destinos y al cliente
    le llego SOLO Cordoba.

    LA CAUSA, exacta: un renglon de reparto no tiene raya de hecho distintivo,
    asi que `_dato` da vacio, y la regla 3-bis lee el vacio como "el mismo
    hecho que el renglon anterior" y borra los que siguen. Borro Concordia y
    Posadas creyendo que repetian a Cordoba, cuando cada uno decia adonde va
    OTRA cosa: informacion unica, no repeticion. Es justo lo contrario de lo
    unico que este modulo promete."""
    from app.core.mensaje import componer

    texto = ("Auriculares (43 igual de cerca):\n"
             "- Auriculares Redragon Zeus X Negro: $57.500 — origen: china\n"
             "- Auriculares Redragon Zeus X Blanco: $57.500 — origen: china\n"
             "\n"
             "Presupuesto:\n"
             "- 2x Auriculares Redragon Zeus X Negro: $57.500 c/u = $115.000\n"
             "Total: $225.000\n"
             "\n"
             "Reparto de los envios:\n"
             "- A Córdoba capital: 1x auriculares, 1x mouse\n"
             "- A Concordia: 1x memoria ram, 1x mouse\n"
             "- A Posadas: 1x auriculares, 1x memoria ram\n")
    salida = componer(texto)
    for destino in ("Córdoba capital", "Concordia", "Posadas"):
        assert destino in salida, f"se perdio {destino}:\n{salida}"

    # Y el listado de arriba se sigue podando igual que antes: proteger el
    # reparto no puede apagar la regla para lo que si es un listado.
    assert "Zeus X Negro: $57.500 — origen" not in salida


def test_un_listado_que_empieza_con_A_no_se_confunde_con_el_reparto():
    """La guarda del reparto mira "- A " con la A como palabra suelta. Con un
    startswith pelado, "- Auriculares..." tambien empieza con "- A" y el
    listado entero se colaria como intocable."""
    from app.core.mensaje import _es_renglon_de_reparto

    assert _es_renglon_de_reparto("- A Concordia: 1x mouse")
    assert not _es_renglon_de_reparto("- Auriculares Redragon Zeus X: $57.500")
    assert not _es_renglon_de_reparto("- A4Tech Mouse Negro: $9.000")


# ── REGLAS 5 y 6: LA CUENTA REPETIDA ────────────────────────────────────────
# LOS CASOS SON LA CHARLA REAL DE MARTIN DEL 10-AGO, leida de Firestore, no un
# invento. Los cinco turnos, con su largo y su bloque de codigo medido:
#
#   turno 1 .. 1.036 caracteres, cuenta de 549 .. cuenta NUEVA
#   turno 2 .. 1.361 caracteres, cuenta de 550 .. cuenta NUEVA (paso a 65/35)
#   turno 3 .. 1.203 caracteres, cuenta de 550 .. IDENTICA a la anterior
#   turno 4 .. 1.115 caracteres, cuenta de 550 .. IDENTICA a la anterior
#   turno 5 .. 1.876 caracteres, cuenta de 970 .. el bloque entero, DOS VECES
#
# En los turnos 3 y 4 el cliente dijo "Me parece bien asi" y "Okay te confirmo
# entonces", o sea que no cambio nada, y la cuenta calcada es el 45% y el 49%
# del mensaje.
#
# POR QUE ESTOS TESTS Y NO UN CASETE: se midio, y las 13 charlas grabadas NO
# ejercitan ni una sola vez estas dos reglas -el largo de los 176 turnos dio
# identico antes y despues del cambio-. O sea que el defecto que Martin ve en
# WhatsApp todos los dias es zona ciega del banco. Hasta que haya un guion
# grabado de una confirmacion en varios turnos, el candado son estos tests.

CUENTA_REAL = (
    "Presupuesto:\n"
    "- 2x Auriculares Redragon Zeus X Blanco: $57.500 c/u = $115.000\n"
    "- 2x Mouse Genius DX-110 Negro: $8.500 c/u = $17.000\n"
    "- 2x Memoria ram Kingston Fury Beast DDR4 3200 8GB Negro: "
    "$34.500 c/u = $69.000\n"
    "Subtotal: $201.000\n"
    "Envio (3 envios): $24.000\n"
    "Total: $225.000\n"
    "\n"
    "Pago dividido:\n"
    "- transferencia (65%): $146.250 - 10% descuento = $131.625\n"
    "- mercado pago (35%): $78.750\n"
    "Total final: $210.375\n"
    "\n"
    "Reparto de los envios:\n"
    "- A Córdoba capital: 1x auriculares, 1x mouse\n"
    "- A Concordia: 1x memoria ram, 1x mouse\n"
    "- A Posadas: 1x auriculares, 1x memoria ram"
)


def test_la_cuenta_no_sale_dos_veces_en_el_mismo_mensaje():
    """El turno del 10-ago donde el cliente contesta su nombre: 27 renglones de
    cuenta, 970 caracteres, el presupuesto entero dos veces. Uno lo pego el
    redactor y el otro el cierre."""
    from app.core.mensaje import sin_cuenta_dos_veces

    texto = (f"Hola Jorge Campos, registre tu pedido.\n\n{CUENTA_REAL}\n\n"
             f"Listo Jorge, tomamos tu pedido.\n{CUENTA_REAL}\n"
             f"Para pagar por transferencia:\nCBU: 0000000000000000000000")
    out = sin_cuenta_dos_veces(texto)
    assert out.count("Total final: $210.375") == 1
    assert out.count("Presupuesto:") == 1
    # y no se perdio nada de lo que estaba UNA sola vez
    assert "CBU: 0000000000000000000000" in out
    assert "Listo Jorge, tomamos tu pedido." in out
    assert "A Posadas" in out


def test_el_segundo_bloque_mutilado_igual_se_va():
    """CONTENCION, NO IGUALDAD, y este es el caso que lo obligo. En produccion
    la regla 1 ya le habia comido los tres renglones de reparto al segundo
    bloque -no son cuenta, asi que no estaban exentos-, con lo cual los dos
    presupuestos no eran identicos y el duplicado sobrevivia por dos renglones
    de diferencia. Ademas dejaba el titulo "Reparto de los envios:" colgado,
    prometiendo tres destinos y sin mostrar ninguno."""
    from app.core.mensaje import sin_cuenta_dos_veces

    mutilado = CUENTA_REAL.split("Reparto de los envios:")[0] + \
        "Reparto de los envios:"
    texto = f"Registre tu pedido.\n\n{CUENTA_REAL}\n\nListo.\n{mutilado}\nGracias."
    out = sin_cuenta_dos_veces(texto)
    assert out.count("Presupuesto:") == 1
    assert out.count("Reparto de los envios:") == 1
    # el titulo que queda tiene sus tres destinos abajo, no esta huerfano
    assert "A Córdoba capital" in out and "A Posadas" in out


def test_dos_cuentas_DISTINTAS_en_un_mensaje_se_quedan_las_dos():
    """La salvaguarda. Si el segundo bloque dice algo que el primero no dice,
    no es una repeticion y no se toca: podria ser el pedido partido en dos."""
    from app.core.mensaje import sin_cuenta_dos_veces

    otra = CUENTA_REAL.replace("$210.375", "$999.999")
    texto = f"Opcion A:\n{CUENTA_REAL}\n\nOpcion B:\n{otra}"
    out = sin_cuenta_dos_veces(texto)
    assert "$210.375" in out and "$999.999" in out


def test_la_cuenta_que_no_cambio_no_se_reestampa_pero_la_plata_queda():
    """Turnos 3 y 4 del 10-ago: el cliente dijo "Me parece bien asi" y la
    cuenta salio calcada, 550 caracteres. Se va el bloque; el total NO."""
    from app.core.mensaje import sin_cuenta_que_no_cambio

    anterior = f"Ahi va tu presupuesto.\n\n{CUENTA_REAL}"
    texto = f"¡Excelente!\n\n{CUENTA_REAL}\n\nQuedo a la espera."
    out = sin_cuenta_que_no_cambio(texto, anterior, pregunta="Me parece bien así")
    assert "Presupuesto:" not in out
    assert "- 2x Mouse Genius" not in out
    # LA PLATA NO DESAPARECE NUNCA: el numero que va a pagar sigue en pantalla
    assert "$210.375" in out
    assert "Quedo a la espera." in out
    assert len(out) < len(texto) / 2


def test_una_cuenta_que_CAMBIO_sale_entera():
    """La atadura que hace segura a la regla 6: si cambio un peso, un producto,
    un destino o un porcentaje, la firma cambia y el bloque va completo. La
    regla no puede esconder un cambio de plata ni queriendo."""
    from app.core.mensaje import sin_cuenta_que_no_cambio

    anterior = f"Ahi va.\n\n{CUENTA_REAL}"
    nueva = CUENTA_REAL.replace("(65%)", "(70%)").replace("$131.625", "$141.750")
    texto = f"Te lo doy vuelta.\n\n{nueva}"
    assert sin_cuenta_que_no_cambio(texto, anterior, pregunta="dale 70/30") == texto


def test_si_el_cliente_PIDE_la_cuenta_sale_entera():
    """Reestampar es contestar lo que preguntaron, no una coletilla."""
    from app.core.mensaje import sin_cuenta_que_no_cambio

    anterior = f"Ahi va.\n\n{CUENTA_REAL}"
    texto = f"Claro.\n\n{CUENTA_REAL}"
    for pedido in ("pasame el presupuesto de nuevo", "¿cómo quedó?",
                   "mandame el total", "repetime la cuenta"):
        out = sin_cuenta_que_no_cambio(texto, anterior, pregunta=pedido)
        assert "Presupuesto:" in out, f"se podo con: {pedido}"


def test_una_cuenta_chica_no_paga_el_riesgo():
    """Piso de 200 caracteres: abajo de eso podar no compra nada."""
    from app.core.mensaje import sin_cuenta_que_no_cambio

    chica = "Presupuesto:\n- 1x Mouse Genius: $8.500 c/u = $8.500\nTotal: $8.500"
    texto = f"Listo.\n{chica}"
    assert sin_cuenta_que_no_cambio(texto, texto, pregunta="dale") == texto


def test_la_frase_de_OTRO_rubro_no_se_borra_por_parecerse():
    """EL CANDADO DE LA REVERSION DEL 10-AGO, y la razon de que exista el
    bloque de comentario de arriba.

    Se escribio una regla que borraba la oracion cuando el 75% de su texto ya
    estaba LITERAL en el mensaje anterior, para cazar el origen repetido cuatro
    turnos. Y borraba esto: el mensaje anterior habla de los AURICULARES, el de
    ahora dice lo mismo pero de los MOUSE, y la oracion del mouse desaparecia
    entera. Al cliente le quedaba la pregunta sola, sin el dato del rubro por el
    que habia escrito.

    Es la misma falla que el tope por caracteres, que tiro la nota de 55 a 23:
    la unica condicion que el cliente puso la explica el modelo en PROSA, y esa
    prosa se repite en la FORMA para cada rubro. Parecerse no es repetirse.

    Si alguien vuelve a proponer la regla, tiene que pasar este test primero."""
    def parrafo(rubro):
        return (f"Sobre los {rubro}, te cuento que todo lo que trabajo de ese "
                f"rubro se fabrica en China, que es justo lo que me pediste "
                f"evitar, así que te marco cuál se acerca más y por qué.")

    salida = componer(
        parrafo("mouse") + " Decime si avanzamos con alguno y te armo el "
        "presupuesto completo con el envío incluido.",
        anterior=parrafo("auriculares"))
    assert "mouse" in salida, f"se perdio el rubro del turno:\n{salida}"
    assert "China" in salida, f"se perdio el criterio del cliente:\n{salida}"


# ── REGLA 7: la cabecera de la cuenta, dos veces ────────────────────────────
def test_la_cuenta_a_medias_de_arriba_se_va_si_la_aritmetica_lo_prueba():
    """LO ENCONTRARON LOS INVARIANTES sobre las charlas grabadas, las mismas
    que puntuan 95 y estan en verde en cada push desde hace una semana. Al
    cliente le llegaba el mismo renglon dos veces y la cuenta NO cerraba sola:
    los renglones sumaban $24.000 y el Subtotal decia $12.000."""
    from app.core.mensaje import sin_cuenta_mutilada_arriba

    texto = ("El teclado más barato es el Genius KB-110X.\n"
             "Presupuesto:\n"
             "- 1x Teclado Genius KB-110X Blanco: $12.000 c/u = $12.000\n"
             "Presupuesto:\n"
             "- 1x Teclado Genius KB-110X Blanco: $12.000 c/u = $12.000\n"
             "Subtotal: $12.000\n"
             "Total: $12.000")
    out = sin_cuenta_mutilada_arriba(texto)
    assert out.count("Presupuesto:") == 1
    assert out.count("KB-110X Blanco") == 1
    assert "Total: $12.000" in out
    assert "El teclado más barato" in out


def test_la_cabecera_pegada_dos_veces_sin_nada_en_el_medio():
    from app.core.mensaje import sin_cuenta_mutilada_arriba

    texto = ("Te armé esto:\nPresupuesto:\nPresupuesto:\n"
             "- 1x Mouse Genius DX-110 Negro: $8.500 c/u = $8.500\n"
             "Subtotal: $8.500\nTotal: $8.500")
    assert sin_cuenta_mutilada_arriba(texto).count("Presupuesto:") == 1


def test_si_la_aritmetica_NO_cierra_no_se_toca_la_plata():
    """LA SALVAGUARDA, y es la razon de que la regla mire la suma y no el
    parecido: un mismo producto repetido en dos destinos es LEGITIMO, suma
    bien, y no tiene que entrar nunca. Si el recorte no hace cerrar la cuenta,
    el codigo no puede probar cual sobra y no toca nada."""
    from app.core.mensaje import sin_cuenta_mutilada_arriba

    texto = ("Presupuesto:\n"
             "- 1x Mouse Genius DX-110 Negro: $8.500 c/u = $8.500\n"
             "Presupuesto:\n"
             "- 1x Mouse Genius DX-110 Negro: $8.500 c/u = $8.500\n"
             "Subtotal: $17.000\n"
             "Total: $17.000")
    assert sin_cuenta_mutilada_arriba(texto) == texto


# ── REGLA 8: EL PIE DE LA CUENTA (11-ago-2026) ──────────────────────────────
def test_el_pie_de_la_cuenta_no_sale_dos_veces():
    """LO ENCONTRO EL EXPLORADOR, en una charla que NADIE escribio: el cliente
    sumaba una notebook al pedido y le llegaron el Subtotal y el Total dos
    veces seguidos. Ni la regla 5 -que pide dos bloques- ni la 7 -que pide dos
    cabeceras- lo veian: el duplicado no era el bloque ni la cabecera, era la
    COLA. Este es el texto real, recortado."""
    from app.core.mensaje import componer

    real = ("Con gusto te ayudo a actualizar tu pedido.\n\n"
            "Presupuesto:\n"
            "- 1x Gabinete Corsair 5000D Airflow Negro: $320.500 c/u = $320.500\n"
            "Subtotal: $320.500\n"
            "Total: $320.500\n"
            "Subtotal: $320.500\n"
            "Total: $320.500\n"
            "Como verás, el precio figura ahí.")
    salida = componer(real)
    assert salida.count("Subtotal: $320.500") == 1
    assert salida.count("Total: $320.500") == 1
    assert "$320.500" in salida
    assert "Como verás, el precio figura ahí." in salida


def test_el_mismo_producto_a_dos_destinos_conserva_su_plata():
    """La contracara, y es la que evita el desastre: el mismo renglon repetido
    porque el pedido va partido a dos destinos NO es un duplicado. La regla 8
    solo mira lineas de PIE, nunca renglones de producto."""
    from app.core.mensaje import componer

    dos = ("Presupuesto:\n"
           "- 1x Mouse Genius DX-110 Negro: $8.500 c/u = $8.500\n"
           "- 1x Mouse Genius DX-110 Negro: $8.500 c/u = $8.500\n"
           "Subtotal: $17.000\n"
           "Total: $17.000")
    assert componer(dos) == dos


def test_si_el_recorte_deja_la_cuenta_sin_cerrar_no_se_toca():
    """La atadura aritmetica, igual que en la regla 7: se prueba el recorte y
    se aplica SOLO si despues los renglones siguen sumando el Subtotal. Aca el
    pie repetido trae OTRO subtotal, asi que sacar el de abajo dejaria una
    cuenta que no cierra: ante la duda, la plata se queda entera."""
    from app.core.mensaje import componer

    raro = ("Presupuesto:\n"
            "- 1x Teclado Logitech K120: $12.000 c/u = $12.000\n"
            "Subtotal: $9.000\n"
            "Subtotal: $9.000")
    assert componer(raro) == raro

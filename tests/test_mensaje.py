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

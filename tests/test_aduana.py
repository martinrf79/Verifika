"""
AREA: LA ADUANA (`app/core/aduana.py`) — los invariantes ANTES de mandar.

QUE SE PRUEBA. Que el ultimo control del turno hace exactamente dos cosas y
ninguna mas: repara lo que puede PROBAR, y deja intacto lo que no.

LA MITAD QUE MAS IMPORTA es la segunda. Una tijera al final ya fallo dos veces
en este repo -el tope por caracteres tiro la nota de 55 a 23, la regla 2-bis
borro la oracion de OTRO producto-, asi que aca los candados que valen son los
que prueban que NO toca: que no mueve un peso, que no borra una cuenta que no
cierra, que no se lleva un renglon legitimo repetido por dos destinos.
"""
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from app.core.aduana import revisar_salida  # noqa: E402


# ── LO QUE REPARA ───────────────────────────────────────────────────────────
def test_la_etiqueta_interna_no_le_llega_al_cliente():
    """La marca de la atadura es lo unico que el sistema le pide escribir al
    modelo y lo unico que NUNCA puede salir. Si se fuga, el cliente lee
    `<d MOU0023>` en el medio de una oracion."""
    texto = "El <d MOU0023>Mouse Genius DX-110</d> viene con un año de garantia."
    salida = revisar_salida(texto, trace_id="t")
    assert "<d" not in salida and "</d>" not in salida
    assert "Mouse Genius DX-110" in salida
    assert "garantia" in salida


def test_el_titulo_sin_lista_abajo_se_va():
    """Le paso a Martin: 'Reparto de los envios:' y abajo, nada. Un titulo que
    promete una lista y no muestra ninguna es peor que no haberlo escrito. El
    mismo `Resumen:` huerfano aparecio en TRES charlas reales distintas."""
    texto = "Te confirmo el pedido para manana.\n\nResumen:\n"
    salida = revisar_salida(texto, trace_id="t")
    assert "Resumen:" not in salida
    assert "Te confirmo el pedido para manana." in salida


def test_el_renglon_calcado_queda_una_sola_vez():
    """Prioridad 2 de Martin, escrita como propiedad: sin repetir informacion
    ni datos. La misma linea larga dos veces en el mismo mensaje es repeticion
    demostrable, no una opinion sobre el estilo."""
    linea = "El envio a Cordoba tarda entre 4 y 7 dias habiles desde el pago."
    salida = revisar_salida(f"Hola.\n{linea}\nAlgo mas.\n{linea}", trace_id="t")
    assert salida.count(linea) == 1
    assert "Algo mas." in salida


# ── LO QUE NO TOCA, QUE ES LA MITAD QUE IMPORTA ─────────────────────────────
def _cuenta_rota() -> str:
    return ("Presupuesto:\n"
            "- 2x Mouse Genius DX-110 Negro: $8.500 c/u = $17.000\n"
            "- 1x Teclado Logitech K120: $12.000 c/u = $12.000\n"
            "Subtotal: $12.000\n")


def test_la_cuenta_que_no_cierra_no_se_reescribe():
    """UNA ADUANA QUE CORRIGE UN PESO ES PEOR QUE EL DEFECTO QUE ARREGLA. Si
    la aritmetica no da, se grita en el log y se manda tal cual: inventar la
    cuenta que el codigo no supo armar es exactamente la alucinacion que el
    sistema entero existe para evitar."""
    texto = _cuenta_rota()
    assert revisar_salida(texto, trace_id="t") == texto


def test_la_linea_con_plata_calcada_se_deduplica_porque_queda_su_copia():
    """La atadura A tiene DOS formas de cumplirse y esta es la segunda: el
    importe aparece una vez menos y no se perdio nada, porque la linea borrada
    sigue escrita mas arriba, palabra por palabra.

    SE AGREGO CON EL NUMERO EN LA MANO: con solo la comparacion de importes, la
    aduana bajaba las violaciones de las 30 charlas REALES de 6 a 2, y las dos
    que sobrevivian eran esta misma linea calcada, '- envio a cordoba capital:
    $7.500', que se negaba a deduplicar por miedo a mover la plata que seguia
    escrita dos lineas arriba."""
    linea = "- envio a cordoba capital: $7.500 (4 a 7 dias habiles)"
    texto = f"Te paso el detalle:\n{linea}\nY el resumen del envio.\n{linea}"
    salida = revisar_salida(texto, trace_id="t")
    assert salida.count(linea) == 1
    assert "$7.500" in salida


def test_una_reparacion_que_se_lleva_plata_no_escrita_se_descarta(monkeypatch):
    """La atadura A, primera forma, y es la que importa: si lo que se borra NO
    esta escrito en ningun otro lado, la reparacion se descarta aunque haya
    hecho desaparecer la violacion. Una aduana que corrige un peso es peor que
    el defecto que arregla."""
    from app.core import aduana

    def _se_lleva_la_plata(texto):
        return "El Mouse Genius DX-110 esta disponible."

    monkeypatch.setattr(aduana, "_REPARACIONES",
                        (("etiqueta_interna_fugada", _se_lleva_la_plata),))
    texto = "El <d MOU0023>Mouse Genius DX-110</d> sale $8.500."
    assert aduana.revisar_salida(texto, trace_id="t") == texto


def test_el_mismo_producto_a_dos_destinos_no_es_repeticion():
    """El caso legitimo que ninguna regla de parecido sabe distinguir: el mismo
    renglon calcado porque el pedido va partido a dos destinos. Esa plata es
    correcta y la cuenta CIERRA, asi que no se toca nada."""
    texto = ("Presupuesto:\n"
             "- 1x Mouse Genius DX-110 Negro: $8.500 c/u = $8.500\n"
             "- 1x Mouse Genius DX-110 Negro: $8.500 c/u = $8.500\n"
             "Subtotal: $17.000\n")
    assert revisar_salida(texto, trace_id="t") == texto


def test_un_mensaje_limpio_sale_identico():
    """El camino feliz, que es el 95% de los turnos: si no hay violaciones, la
    aduana devuelve el mismo objeto y no reescribe ni un espacio."""
    texto = ("Tengo el Mouse Genius DX-110 Negro a $8.500.\n"
             "¿Te lo reservo?")
    assert revisar_salida(texto, trace_id="t") == texto


def test_nunca_deja_mudo_al_bot():
    """Una aduana rota no puede callar al bot. Ante cualquier problema propio,
    devuelve el texto tal como entro."""
    assert revisar_salida("", trace_id="t") == ""
    largo = "Hola, " * 500
    assert revisar_salida(largo, trace_id="t")


def test_la_reparacion_que_no_mejora_se_revierte(monkeypatch):
    """La atadura B: se acepta solo si quedan MENOS violaciones y ninguna
    NUEVA. Se dobla una reparacion que 'arregla' rompiendo otra cosa y se
    verifica que el mensaje vuelve al original."""
    from app.core import aduana

    def _rompe(texto):
        # Saca la etiqueta y de paso deja un titulo huerfano: mismo total de
        # violaciones, una de ellas NUEVA.
        return "Mouse Genius DX-110 esta disponible.\n\nDetalle:"

    monkeypatch.setattr(aduana, "_REPARACIONES",
                        (("etiqueta_interna_fugada", _rompe),))
    texto = "El <d MOU0023>Mouse Genius DX-110</d> esta disponible."
    assert aduana.revisar_salida(texto, trace_id="t") == texto

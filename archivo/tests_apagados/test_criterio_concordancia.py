"""
EL CRITERIO DE PRECIO — "lo mas barato", como DECISION que persiste.

El cliente lo dice una vez y vale para todo el pedido. En la charla real de
WhatsApp lo dijo tres veces y el bot le seguia preguntando modelo y color; eso
lo hizo renegar, y es el arreglo B.

POR QUE SE REESCRIBIO (12-ago). Antes esto probaba `concordancia_criterio`, que
cruzaba el regex del codigo con la lectura del INTERPRETE. El hub reemplazo al
interprete el 1-ago, asi que esa funcion no la llamaba nadie: quedaban tres
funciones vivas solo para este archivo. Hoy el criterio lo lee el codigo del
mensaje —determinista, sin modelo— y lo que faltaba no era cruzarlo con nadie,
era GUARDARLO: `criterio_cliente` se leia en cada turno y no lo escribia nadie,
asi que llegaba siempre vacio. Eso es lo que se prueba ahora, de punta a punta.
"""
from app.core.estado_venta import construir_estado, detectar_criterio


def test_lo_dice_el_codigo_y_es_determinista():
    assert detectar_criterio("los mas baratos que tengas") == "más barato"
    assert detectar_criterio("algo economico") == "más barato"
    assert detectar_criterio("dame precio de dos mouse") == ""


def test_el_rechazo_del_minimo_no_es_lo_mas_barato():
    """'economicos pero no lo mas barato que haya' armaba los MAS baratos, que
    es lo contrario de lo pedido (banco 11-jul)."""
    assert detectar_criterio(
        "economicos pero no lo mas barato que haya") == "intermedio"
    assert detectar_criterio("algo intermedio") == "intermedio"


def test_el_criterio_persiste_y_vuelve_por_el_estado():
    estado = construir_estado({"criterio_cliente": "más barato"}, None)
    assert estado["criterio"] == "más barato"


def test_el_criterio_llega_al_prompt():
    """La mitad que faltaba: guardarlo no sirve si el turno siguiente no lo ve.
    Sin esto el bot vuelve a preguntar lo que el cliente ya decidio."""
    from app.core.hub_venta import _memoria_texto
    texto = _memoria_texto({"criterio": "más barato"}, [])
    assert "más barato" in texto
    assert "no se lo vuelvas a preguntar" in texto.lower()


def test_el_criterio_se_puede_soltar():
    """El criterio es STICKY, y por eso tiene que poder soltarse: sin esto el
    sistema le arrastra al cliente una decision que acaba de aflojar. Es el
    mensaje real del 12-ago: pidio "el mas barato" en un turno y dos turnos
    despues abrio con "el precio no seria tan importante"."""
    from app.core.estado_venta import libera_criterio
    assert libera_criterio("El precio no sería tan importante")
    assert libera_criterio("no me importa el precio, quiero calidad")
    assert not libera_criterio("dame los mas baratos")
    assert not libera_criterio("el precio importa mucho")

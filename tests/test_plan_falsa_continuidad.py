"""
FICHA 44 — LA OFERTA FANTASMA: "ya conoces X" cuando el turno nunca lo trajo.

DE DONDE SALE, y es doble a proposito. Primero se encontro reproduciendo
`banco_pruebas/casetes/81_charla_real_12ago_cierre.json` con el codigo de HOY
(turno 3: "Como ya conoces los Auriculares Redragon Zeus X Blanco, ¿queres que
proceda a cargarlos..."). El cliente nunca nombro el blanco. Podia pensarse
un resto de la grabacion del 12-ago, asi que no alcanzaba.

No alcanzo, porque volvio a pasar EN VIVO, el 29-ago, con el WhatsApp real de
Martin y el MISMO primer mensaje ("Dame precio de dos auriculares, dos mouse y
dos memorias..."). La respuesta real fue: "Como ya conoces los Auriculares
Redragon Zeus X en color blanco, decime si queres que los cargue en este
presupuesto para que te quede el total actualizado." Dos corridas separadas
por diecisiete dias, un intercambio de casetes en el medio (FICHAS 34 a 43), y
el mismo defecto exacto. No es un resto viejo: es estructural.

POR QUE NINGUNA PUERTA LO CAZA HOY, verificado leyendo el codigo, no
adivinado. `procedencia()` corre ocho piezas sobre el texto. La atadura
(`atadura_prosa.verificar`) solo controla NUMEROS adentro de un tag `<d ID>`
que el propio redactor pone; la oracion fantasma no tiene un solo digito, asi
que aunque el redactor la marcara no habria nada que contrastar. Las otras
siete piezas cazan JSON, markdown, CBU, negacion de lo traido, universales
sobre el catalogo, descuento inventado y narracion interna que nombra la
maquina: ninguna mira si el turno YA HABLO del producto que la frase da por
sabido. Es un agujero de FORMA, la misma clase de hallazgo que la FICHA 20 le
encontro a las otras guardias: el sistema no tiene ninguna pieza que compare
"lo que la prosa dice que el cliente ya sabe" contra "lo que el turno
efectivamente trajo o el cliente efectivamente dijo".

QUE SI HAY, y es la puerta correcta para resolverlo sin agrandar el prompt: el
mismo indice `fuentes()` que ya arma `atadura_prosa` para los tags -que id
trajo este turno- alcanza para vetar un nombre de producto que esa oracion da
por conocido y que no esta en ese indice. No hace falta memoria de charla ni
una llamada nueva al modelo: el material ya esta.

OBJETIVO: una oracion que afirma continuidad -"ya conoces", "como ya sabes",
"como te comente", "como hablamos", "retomamos lo que veniamos charlando"-
sobre un producto puntual se PODA cuando ese producto no esta en lo que el
turno trajo. La misma frase sobre un producto que SI esta en `llamadas` se
queda intacta: no se persigue la forma, se persigue la afirmacion sin
respaldo, igual que hace la atadura con los numeros.

NO ES ESTA FICHA la nota de politica inventada que aparecio en el mismo
casete ("nuestra politica ante mensajes con errores de tipeo es...", turno 4):
es la MISMA familia -una afirmacion sobre "como operamos" sin ninguna fuente
detras- pero un patron de texto distinto, y mezclar los dos en un solo corte
es la forma exacta en que este repo ya se corrigio antes: cortar junto lo que
es una sola pieza, no acumular guardias parecidas de a una. Queda anotado para
la ficha que sigue, no para esta.
"""
import pytest

from app.core import salida as SAL

# Lo que el turno REALMENTE trajo: el negro de los tres rubros pedidos. El
# blanco (AUR0020) nunca se busco ni se certifico en este turno.
_LLAMADAS_TURNO = [{
    "herramienta": "consultar_productos",
    "resultado": {"productos": [
        {"id": "AUR0019", "nombre": "Auriculares Redragon Zeus X Negro",
         "categoria": "auriculares"},
        {"id": "MOU0023", "nombre": "Mouse Genius DX-110 Negro",
         "categoria": "mouse"},
        {"id": "RAM0001",
         "nombre": "Memoria ram Kingston Fury Beast DDR4 3200 8GB Negro",
         "categoria": "memoria ram"},
    ]},
}]

# Verbatim del WhatsApp real del 29-ago-2026, primer turno de la charla.
_TEXTO_REAL_29AGO = (
    "¡Hola! Soy el asistente automático de Verifika Tech.\n\n"
    "Te paso el presupuesto solicitado.\n\n"
    "Sobre las consultas técnicas, trabajamos con precios de lista sujetos a "
    "cambios sin previo aviso, aceptamos transferencia bancaria y Mercado "
    "Pago, y realizamos envíos a todo el país mediante nuestra logística. "
    "Para cerrar la venta, una vez confirmado el pago, procedemos con el "
    "despacho de los artículos.\n\n"
    "Como ya conocés los Auriculares Redragon Zeus X en color blanco, "
    "decime si querés que los cargue en este presupuesto para que te quede "
    "el total actualizado.\n\n"
    "Presupuesto:\n"
    "- 2x Auriculares Redragon Zeus X Negro: $57.500 c/u = $115.000\n"
    "- 2x Mouse Genius DX-110 Negro: $8.500 c/u = $17.000\n"
    "- 1x Teclado Genius KB-110X Blanco: $12.000 c/u = $12.000\n"
    "- 2x Memoria ram Kingston Fury Beast DDR4 3200 8GB Negro: "
    "$34.500 c/u = $69.000\n"
    "Subtotal: $213.000\n"
    "Envio (3 envios): $24.000\n"
    "Total: $237.000"
)


@pytest.mark.xfail(strict=True, reason=(
    "PLAN: FICHA 44. Una afirmacion de continuidad -\"ya conoces\", \"como ya "
    "sabes\", \"como te comente\"- sobre un producto puntual se poda cuando "
    "ese producto no esta entre lo que `llamadas` trajo este turno. HOY "
    "ninguna de las ocho piezas de `procedencia()` la mira: la atadura solo "
    "verifica NUMEROS adentro de un tag y esta oracion no tiene ninguno. "
    "Medido dos veces, separadas por 17 dias y ocho fichas de por medio "
    "(34 a 43): la misma frase sobre el mismo producto blanco que nadie "
    "pidio, primero reproduciendo el casete 81_charla_real_12ago_cierre con "
    "el codigo de hoy, despues en el WhatsApp real del 29-ago. OBJETIVO: la "
    "palabra 'blanco' y el nombre AUR0020 no sobreviven `procedencia()` "
    "cuando `llamadas` solo trajo el AUR0019 negro."))
def test_no_se_afirma_continuidad_sobre_un_producto_que_el_turno_no_trajo():
    salida = SAL.procedencia(_TEXTO_REAL_29AGO, _LLAMADAS_TURNO,
                              "t_ficha44", "verifika_prod")
    assert "blanco" not in salida.lower(), (
        "la oferta fantasma del color blanco -que ningun `llamadas` de este "
        f"turno certifico- llego intacta al cliente:\n{salida}")


# La misma propiedad, del lado que NO se puede romper: si el turno SI trajo
# el producto que la frase da por conocido, la oracion es legitima y tiene
# que sobrevivir. HOY pasa en verde, porque hoy nada poda ninguna de las dos
# formas -esa es justamente la falla de arriba-. Se deja en verde y SIN
# xfail a proposito: no mide un defecto de hoy, mide la baranda que quien
# cierre la FICHA 44 no puede romper. Si el dia de manana este test se pone
# rojo, es que el corte de arriba se paso de mano y se llevo puesto un
# callback real -la forma exacta de rojo falso que el propio repo ya
# penó tres veces (ARRANQUE.md, regla 12)-.
def test_continuidad_legitima_sobre_un_producto_ya_traido_no_se_toca():
    texto = ("Como ya conocés el Mouse Genius DX-110 Negro que te pasé, "
             "¿lo confirmamos junto con el resto del pedido?")
    salida = SAL.procedencia(texto, _LLAMADAS_TURNO, "t_ficha44b",
                              "verifika_prod")
    assert "mouse genius dx-110" in salida.lower(), (
        "una referencia legitima a un producto que ESTE turno si trajo se "
        f"perdio en el corte:\n{salida}")

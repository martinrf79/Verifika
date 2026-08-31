"""
FICHA 44 — CERRADO. LA OFERTA FANTASMA: "ya conoces X" cuando el turno nunca
lo trajo.

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

EL ARREGLO: `app/core/salida.py::_sin_continuidad_fantasma`, novena pieza de
`procedencia()`. Busca una clausula de continuidad -"ya conoces", "como ya
sabes", "como te comente", "como hablamos", "retomamos lo que veniamos
charlando"- y la contrasta, RENGLON POR RENGLON, contra `_entradas_confirmadas`.
Solo poda cuando la clausula trae una SEÑAL puntual -un color, un nombre
propio de dos o mas palabras, un codigo con digitos- que no aparece en ningun
renglon confirmado de este turno; sin señal, no hay nada que contrastar y se
deja intacta (regla 12: podar por las dudas se come la charla legitima).

DOS VUELTAS MAS, IMPLEMENTANDO, ANTES DE CERRAR ESTA FICHA -las dos medidas
contra el mismo `81_charla_real_12ago_cierre`, no contra el verbatim solo,
que no alcanzaba para verlas:

  1. Comparar contra una BOLSA DE PALABRAS entera dejaba pasar de largo el
     Teclado Blanco real del mismo presupuesto: "aparece 'blanco' en algun
     lado" respaldaba cualquier cosa blanca. Se corrigio comparando por
     RENGLON: la clausula tiene que encontrar un renglon que la nombre por
     sus tokens NO-color, y el color tiene que estar en ESE MISMO renglon.
  2. Comparar contra `AP.fuentes(llamadas)` a secas -el mismo indice de la
     atadura de numeros- dejaba pasar la frase igual, porque ese indice
     junta TODO lo que trajo `consultar_productos`, y una busqueda por
     categoria trae los dos colores como candidatos aunque el cliente eligio
     uno. `_entradas_confirmadas` mira solo lo CONFIRMADO: lo que
     `registrar_pedido` declaro, lo que `cotizar` factura, y el bloque de la
     cuenta que ya viaja en `texto` -nunca un candidato de comparacion.

NO ES ESTA FICHA la nota de politica inventada que aparecio en el mismo
casete ("nuestra politica ante mensajes con errores de tipeo es...", turno 4):
es la MISMA familia -una afirmacion sobre "como operamos" sin ninguna fuente
detras- pero un patron de texto distinto, y mezclar los dos en un solo corte
es la forma exacta en que este repo ya se corrigio antes: cortar junto lo que
es una sola pieza, no acumular guardias parecidas de a una. Queda anotado para
la ficha que sigue, no para esta.
"""
from app.core import salida as SAL

# Lo que el turno REALMENTE CONFIRMO: el negro de los tres rubros pedidos,
# como lo declara `registrar_pedido` (mismo shape que el casete real). El
# blanco (AUR0020) nunca fue parte de lo que el cliente pidio, aunque una
# busqueda por categoria SI lo pueda traer como candidato -por eso esta
# guardia no mira `consultar_productos`, ver `_entradas_confirmadas`.
_LLAMADAS_TURNO = [{
    "herramienta": "registrar_pedido",
    "resultado": {"estado": "registrado", "pedido": {"items": [
        {"que": "Auriculares Redragon Zeus X Negro", "categoria": "auriculares",
         "cantidad": 2},
        {"que": "Mouse Genius DX-110 Negro", "categoria": "mouse",
         "cantidad": 2},
        {"que": "Memoria ram Kingston Fury Beast DDR4 3200 8GB Negro",
         "categoria": "memoria ram", "cantidad": 2},
    ]}},
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


def test_no_se_afirma_continuidad_sobre_un_producto_que_el_turno_no_trajo():
    salida = SAL.procedencia(_TEXTO_REAL_29AGO, _LLAMADAS_TURNO,
                              "t_ficha44", "verifika_prod")
    # LA ASERCION ORIGINAL DE ESTA FICHA PEDIA "blanco" NO EN NINGUN LADO, Y
    # ERA DEMASIADO ANCHA (corregido al implementar, 31-ago). El mismo
    # verbatim del 29-ago trae un TECLADO BLANCO real en el bloque de la
    # cuenta -un item legitimo del pedido, escrito por el codigo, que jamas
    # fue el defecto-. Perseguir la palabra entera se comia esa linea igual
    # que la frase fantasma. Lo que hay que probar es la CLAUSULA fantasma en
    # si: la afirmacion de continuidad sobre el color de los AURICULARES, que
    # es el producto puntual que este turno certifico en negro.
    assert "en color blanco" not in salida.lower(), (
        "la oferta fantasma del color blanco -que ningun `llamadas` de este "
        f"turno certifico- llego intacta al cliente:\n{salida}")
    assert "ya conocés" not in salida.lower(), (
        "la clausula de continuidad fantasma sigue en pie:\n" + salida)
    assert "auriculares redragon zeus x negro" in salida.lower(), (
        "el arreglo se llevo puesto el renglon real de la cuenta, que si "
        f"esta respaldado:\n{salida}")


# La misma propiedad, del lado que NO se puede romper: si el turno SI trajo
# el producto que la frase da por conocido, la oracion es legitima y tiene
# que sobrevivir. HOY pasa en verde, porque hoy nada poda ninguna de las dos
# formas -esa es justamente la falla de arriba-. Se deja en verde y SIN
# xfail a proposito: no mide un defecto de hoy, mide la baranda que quien
# cierre la FICHA 44 no puede romper. Si el dia de manana este test se pone
# rojo, es que el corte de arriba se paso de mano y se llevo puesto un
# callback real -la forma exacta de rojo falso que el propio repo ya
# peno tres veces (ARRANQUE.md, regla 12)-.
def test_continuidad_legitima_sobre_un_producto_ya_traido_no_se_toca():
    texto = ("Como ya conocés el Mouse Genius DX-110 Negro que te pasé, "
             "¿lo confirmamos junto con el resto del pedido?")
    salida = SAL.procedencia(texto, _LLAMADAS_TURNO, "t_ficha44b",
                              "verifika_prod")
    assert "mouse genius dx-110" in salida.lower(), (
        "una referencia legitima a un producto que ESTE turno si trajo se "
        f"perdio en el corte:\n{salida}")

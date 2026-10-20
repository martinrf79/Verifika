"""
EL BARRIDO DE LA MEMORIA — la superficie donde vivieron los peores errores.

POR QUE EXISTE. El barrido de entradas prueba UNA herramienta con UN argumento
torcido. Los defectos mas caros del 12-ago no eran de una herramienta suelta:
eran de lo que el sistema RECUERDA de un turno al siguiente.

  - La cuenta del turno 1, con un producto que el cliente anulo en el turno 2,
    reestampada en el turno 4 y con el reparto de pago al reves. Le cobro un
    teclado cancelado y le dio vuelta el pago.
  - El reparto de envios que existia en un turno y desaparecia dos turnos
    despues, con el mismo carrito, y el bot volvia a preguntar lo que el cliente
    ya habia contestado.
  - Cuatro campos que el estado LEIA en cada turno y no escribia nadie: el
    criterio de precio, la provincia, las preferencias y el ancla. No estaban
    mal calculados: no existian, y nadie se enteraba.

Ninguno de los tres lo puede ver un test de una funcion, porque cada funcion
sola esta bien. Viven en la TRANSICION: estado previo mas lo que pasa en el
turno, igual a estado nuevo.

QUE HACE ESTE MODULO. Genera transiciones: por cada estado previo plausible
-carrito vacio, carrito de uno, carrito repartido entre destinos, con cuenta
guardada, con ancla, con criterio- por cada movida del cliente -agregar, sacar,
cambiar el pago, confirmar sin cambiar nada, empezar otro pedido- y afirma las
propiedades que ninguna memoria correcta viola nunca.

LA COBERTURA SE MIDE CONTRA `construir_estado`, que es la funcion que decide
que recuerda el sistema. Si alguien agrega un campo ahi, aparece solo en la
cuenta y queda sin barrer hasta que se le escriba una transicion. El numero
sale del codigo, no de una lista.

CORRE OFFLINE Y GRATIS: son funciones deterministas, cero modelo.
"""
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

TIENDA = "verifika_prod"

_AUR = {"id": "AUR0019", "nombre": "Auriculares Redragon Zeus X Negro",
        "cantidad": 1}
_MOU = {"id": "MOU0023", "nombre": "Mouse Genius DX-110 Negro", "cantidad": 2}
_RAM = {"id": "RAM0001",
        "nombre": "Memoria ram Kingston Fury Beast DDR4 3200 8GB Negro",
        "cantidad": 2}
_TEC = {"id": "TEC0020", "nombre": "Teclado Genius KB-110X Blanco",
        "cantidad": 1}

_CUENTA_TRES = (
    "Presupuesto:\n"
    "- 1x Auriculares Redragon Zeus X Negro: $57.500 c/u = $57.500\n"
    "- 2x Mouse Genius DX-110 Negro: $8.500 c/u = $17.000\n"
    "- 2x Memoria ram Kingston Fury Beast DDR4 3200 8GB Negro: "
    "$34.500 c/u = $69.000\n"
    "Subtotal: $143.500\nTotal: $143.500")
_CUENTA_CON_TECLADO = (
    _CUENTA_TRES.replace(
        "Subtotal:",
        "- 1x Teclado Genius KB-110X Blanco: $12.000 c/u = $12.000\nSubtotal:"))


def estados_previos() -> list:
    """Los estados con los que puede arrancar un turno. Cada uno nombra que
    campos de la memoria toca, para poder medir la cobertura."""
    return [
        {"nombre": "vacio", "toca": [], "conv": {}},
        {"nombre": "carrito_de_uno", "toca": ["carrito"],
         "conv": {"carrito_vigente": [dict(_MOU)]}},
        {"nombre": "carrito_de_tres_con_cuenta",
         "toca": ["carrito", "presupuesto"],
         "conv": {"carrito_vigente": [dict(_AUR), dict(_MOU), dict(_RAM)],
                  "ultimo_presupuesto": _CUENTA_TRES}},
        {"nombre": "cuenta_con_producto_que_ya_no_esta",
         "toca": ["carrito", "presupuesto"],
         "conv": {"carrito_vigente": [dict(_AUR), dict(_MOU), dict(_RAM)],
                  "ultimo_presupuesto": _CUENTA_CON_TECLADO}},
        {"nombre": "repartido_entre_destinos",
         "toca": ["carrito", "grupos_envio", "localidades_envio"],
         "conv": {"carrito_vigente": [dict(_AUR), dict(_MOU), dict(_RAM)],
                  "ultimas_localidades": ["Cordoba capital", "Rosario"],
                  "grupos_envio": [
                      {"destino": "Cordoba capital",
                       "cats": [{"n": 1, "cat": "auriculares"},
                                {"n": 2, "cat": "mouse"}]},
                      {"destino": "Rosario",
                       "cats": [{"n": 2, "cat": "memoria ram"}]}]}},
        {"nombre": "con_ancla_y_criterio",
         "toca": ["producto_anotado", "criterio", "provincia_envio",
                  "preferencias"],
         "conv": {"producto_anotado": {"id": "MOU0023",
                                       "nombre": "Mouse Genius DX-110 Negro",
                                       "precio": 8500},
                  "criterio_cliente": "más barato",
                  "provincia_envio": "cordoba",
                  "preferencias_cliente": {"condiciones": ["sin china"]}}},
        {"nombre": "con_descartados_y_vistos",
         "toca": ["descartados", "productos_vistos", "localidad_envio"],
         "conv": {"descartados": ["teclado"],
                  "ultima_localidad": "Rosario",
                  "productos_vistos": [{"id": "MOU0023",
                                        "nombre": "Mouse Genius DX-110 Negro",
                                        "categoria": "mouse", "turno": 1,
                                        "posicion": 1, "precio": 8500}]}},
        {"nombre": "con_datos_del_cliente_y_resumen",
         "toca": ["datos_cliente", "resumen_charla"],
         "conv": {"datos_cliente_parciales": {"nombre": "Juan Perez"},
                  "summary": "El cliente venia mirando mouse y auriculares."}},
    ]


def movidas() -> list:
    """Lo que el cliente hace, con lo que el modelo declara en ese turno. El
    mensaje importa: varias decisiones del codigo se leen de ahi."""
    return [
        {"nombre": "confirma_sin_cambiar",
         "mensaje": "dale, confirmalo",
         "declarado": {"items": [{"que": "mouse", "cantidad": 2}]}},
        {"nombre": "saca_un_producto",
         "mensaje": "sacá los auriculares, dejame el resto",
         "declarado": {"items": [{"que": "mouse", "cantidad": 2},
                                 {"que": "memoria ram", "cantidad": 2}]}},
        {"nombre": "agrega_un_producto",
         "mensaje": "agregá un teclado con envío a Cordoba capital",
         "declarado": {"items": [{"que": "teclado", "cantidad": 1,
                                  "destino": "Cordoba capital"}]}},
        {"nombre": "cambia_el_pago",
         "mensaje": "que vaya 70 mercado pago",
         "declarado": {"items": [{"que": "mouse", "cantidad": 2}],
                       "reparto_pago": [{"medio": "mercado pago",
                                         "porcentaje": 70},
                                        {"medio": "transferencia",
                                         "porcentaje": 30}]}},
        {"nombre": "pide_otro_pedido_distinto",
         "mensaje": "dame precio de dos notebooks",
         "declarado": {"items": [{"que": "notebook", "cantidad": 2}],
                       "pide_precio": True}},
        {"nombre": "pregunta_sin_pedir_nada",
         "mensaje": "y cuanto tarda el envio?",
         "declarado": {}},
        {"nombre": "elige_y_pide_anotar",
         "mensaje": "me quedo con ese, anotalo",
         "declarado": {"items": [{"que": "mouse", "cantidad": 1}]}},
        {"nombre": "suelta_el_criterio",
         "mensaje": "el precio no sería tan importante",
         "declarado": {"items": [{"que": "mouse", "cantidad": 2}]}},
        {"nombre": "pone_una_condicion",
         "mensaje": "que tengan garantia de 2 años al menos",
         "declarado": {"items": [{"que": "mouse", "cantidad": 2}],
                       "restricciones": ["garantia de 2 años al menos"]}},
    ]


def transiciones() -> list:
    """El producto cartesiano: cada estado previo por cada movida."""
    return [{"estado": e, "movida": m}
            for e in estados_previos() for m in movidas()]


def campos_del_estado() -> list:
    """Los campos que `construir_estado` arma, leidos de la funcion viva. Es el
    denominador de la cobertura."""
    from app.core.estado_venta import construir_estado
    return sorted(construir_estado({}, None))


def cobertura() -> dict:
    """Que campos de la memoria toca al menos un estado previo del barrido."""
    tocados = {c for e in estados_previos() for c in e["toca"]}
    todos = campos_del_estado()
    faltan = sorted(set(todos) - tocados)
    return {"campos": len(todos), "cubiertos": len(todos) - len(faltan),
            "pendientes": faltan,
            "porcentaje": round(100 * (len(todos) - len(faltan)) / len(todos), 1)
            if todos else 0.0}

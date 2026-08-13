"""
EL BARRIDO DE LA MEMORIA — la transicion de un turno al siguiente.

POR QUE EXISTE. Los tres defectos mas caros del 12-ago no eran de una funcion:
cada funcion sola estaba bien. Vivian en la TRANSICION, que es lo que ningun
test miraba: estado previo mas lo que pasa en el turno, igual a estado nuevo.

  - La cuenta del turno 1 reestampada en el turno 4, con un producto que el
    cliente habia anulado y el pago al reves.
  - El reparto de envios que desaparecia dos turnos despues con el mismo
    carrito.
  - Cuatro campos que el estado leia y no escribia nadie.

Aca se generan 72 transiciones -ocho estados previos por nueve movidas del
cliente- y se afirman las propiedades que ninguna memoria correcta viola. La
cobertura se mide contra `construir_estado`, que es la funcion que decide que
recuerda el sistema: si aparece un campo nuevo, el candado lo nombra.

CORRE OFFLINE Y GRATIS: son funciones deterministas, cero modelo.
"""
import sys
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from banco_pruebas import barrido_memoria as M  # noqa: E402
from app.verifika import invariantes as INV  # noqa: E402


@pytest.fixture(scope="module")
def transiciones(firestore_doble):
    """Cada transicion corrida por las MISMAS funciones que usa el hub al
    cerrar el turno. Llamar a otra cosa probaria otro camino, que es la trampa
    que este repo ya pago dos veces."""
    from app.core import hub_venta as HV
    from app.core.estado_venta import (ancla_al_dia, construir_estado,
                                       detectar_criterio, libera_criterio,
                                       pide_agregar_al_pedido)
    from app.core.contexto_turno import set_current_tienda
    set_current_tienda(M.TIENDA)
    fuera = []
    for t in M.transiciones():
        conv = dict(t["estado"]["conv"])
        msg = t["movida"]["mensaje"]
        declarado = t["movida"]["declarado"]
        previo = construir_estado(conv, None)

        agrega = pide_agregar_al_pedido(msg)
        carrito, bajas = ((conv.get("carrito_vigente") or [], [])
                          if agrega else
                          HV._carrito_podado(conv.get("carrito_vigente") or [],
                                             declarado))
        descartados = HV._descartados_nuevos(
            conv.get("descartados") or [], bajas, carrito,
            declarado_antes=(None if agrega else conv.get("ultimo_declarado")),
            declarado_ahora=HV._declarados(declarado))
        criterio = ("" if libera_criterio(msg)
                    else detectar_criterio(msg) or (conv.get("criterio_cliente") or ""))
        ancla = ancla_al_dia(conv.get("producto_anotado") or {}, msg,
                             [{"id": c["id"], "nombre": c["nombre"]}
                              for c in carrito] if len(carrito) == 1 else [])
        prefs = HV._preferencias_al_dia(conv.get("preferencias_cliente") or {},
                                        declarado, [])
        cuenta_vieja = HV._cuenta_de_otro_pedido(
            conv.get("ultimo_presupuesto") or "", declarado, carrito)
        fuera.append({
            "caso": f"{t['estado']['nombre']} + {t['movida']['nombre']}",
            "previo": previo, "conv": conv, "mensaje": msg,
            "declarado": declarado, "agrega": agrega,
            "carrito": carrito, "descartados": descartados,
            "criterio": criterio, "ancla": ancla, "preferencias": prefs,
            "cuenta_es_vieja": cuenta_vieja,
            "reparto_guardado": HV._reparto_que_se_guarda(
                None, conv.get("grupos_envio") or [], carrito),
        })
    return fuera


# ── EL CANDADO DE COBERTURA ────────────────────────────────────────────────
def test_la_memoria_esta_cubierta_entera():
    """Los campos salen de `construir_estado`. Si mañana se agrega uno y nadie
    escribe una transicion que lo toque, esto se pone rojo con su nombre."""
    cob = M.cobertura()
    assert not cob["pendientes"], (
        f"la memoria esta cubierta al {cob['porcentaje']}%: ningun estado "
        f"previo del barrido toca {cob['pendientes']}")
    assert cob["porcentaje"] == 100.0


def test_el_barrido_de_memoria_no_se_apaga(transiciones):
    assert len(transiciones) >= 60, (
        f"corrio {len(transiciones)} transiciones: el generador se apago")


# ── LAS PROPIEDADES DE LA MEMORIA ──────────────────────────────────────────
def test_la_cuenta_guardada_o_es_del_pedido_vigente_o_se_descarta(transiciones):
    """LA PROPIEDAD DEL ERROR DEL 12-AGO. Una cuenta guardada que cotiza algo
    que ya no esta en el carrito no puede volver a estamparse. O corresponde al
    pedido vigente, o se marca como de otro pedido."""
    malas = []
    for t in transiciones:
        previo = t["conv"].get("ultimo_presupuesto") or ""
        if not previo or not t["carrito"]:
            continue
        en_el_pedido = " | ".join(str(c.get("nombre") or "").lower()
                                  for c in t["carrito"])
        sobra = [m.group("nombre").strip() for m in INV._RE_ITEM.finditer(previo)
                 if m.group("nombre").strip().lower() not in en_el_pedido]
        if sobra and not t["cuenta_es_vieja"]:
            malas.append(f"{t['caso']}: la cuenta guardada cotiza {sobra} y no "
                         f"esta en el carrito, y se dio por vigente")
    assert not malas, "\n  ".join(malas[:8])


def test_un_agregado_nunca_borra_lo_que_ya_habia(transiciones):
    """"Agregá un teclado" no puede dejar el carrito en un teclado. Fue el error
    de la charla real: la cuenta salio con un renglon de $12.000 y tres envios
    de $24.000 encima."""
    malas = []
    for t in transiciones:
        if not t["agrega"]:
            continue
        antes = {str(c.get("id")).upper() for c in (t["conv"].get("carrito_vigente") or [])}
        ahora = {str(c.get("id")).upper() for c in t["carrito"]}
        if antes - ahora:
            malas.append(f"{t['caso']}: agregar se llevo puesto {sorted(antes - ahora)}")
    assert not malas, "\n  ".join(malas[:8])


def test_nada_entra_al_carrito_sin_que_el_cliente_lo_pida(transiciones):
    """El carrito solo puede perder items o quedarse igual cuando el turno no
    cotiza. Un item que APARECE sin que nadie lo compre es plata que el cliente
    no pidio."""
    malas = []
    for t in transiciones:
        antes = {str(c.get("id")).upper()
                 for c in (t["conv"].get("carrito_vigente") or [])}
        ahora = {str(c.get("id")).upper() for c in t["carrito"]}
        if ahora - antes:
            malas.append(f"{t['caso']}: aparecio {sorted(ahora - antes)} sin cotizar")
    assert not malas, "\n  ".join(malas[:8])


def test_lo_descartado_no_vuelve_solo(transiciones):
    """La memoria negativa es lo primero que se pierde cuando la charla se
    comprime, y volver a meter algo que el cliente saco es de los errores que
    mas enojan."""
    malas = []
    for t in transiciones:
        previos = {str(d).lower() for d in (t["conv"].get("descartados") or [])}
        if not previos:
            continue
        en_carrito = " ".join(str(c.get("nombre") or "").lower()
                              for c in t["carrito"])
        vueltos = [d for d in previos if d in en_carrito]
        ahora = {str(d).lower() for d in t["descartados"]}
        perdidos = [d for d in previos if d not in ahora and d not in vueltos]
        if perdidos:
            malas.append(f"{t['caso']}: se perdio el descarte de {perdidos} sin "
                         f"que el cliente lo volviera a pedir")
    assert not malas, "\n  ".join(malas[:8])


def test_las_decisiones_del_cliente_no_se_borran_sin_motivo(transiciones):
    """El criterio, la provincia y las condiciones son STICKY: valen hasta que
    el cliente los cambie. Un turno que habla de otra cosa no puede limpiarlos.
    Es la falla que tuvieron los cuatro campos muertos, del otro lado."""
    malas = []
    for t in transiciones:
        antes = t["conv"].get("criterio_cliente") or ""
        libera = "precio no" in t["mensaje"].lower()
        if antes and not t["criterio"] and not libera:
            malas.append(f"{t['caso']}: se perdio el criterio '{antes}'")
        cond_antes = (t["conv"].get("preferencias_cliente") or {}).get("condiciones") or []
        cond_ahora = (t["preferencias"] or {}).get("condiciones") or []
        faltan = [c for c in cond_antes if c not in cond_ahora]
        if faltan:
            malas.append(f"{t['caso']}: se perdieron las condiciones {faltan}")
    assert not malas, "\n  ".join(malas[:8])


def test_el_ancla_solo_se_mueve_cuando_el_cliente_elige(transiciones):
    """Un ancla que se mueve sola sobre el producto equivocado es peor que no
    tener ancla: el cliente pide 'el que te dije' y le llega otro."""
    malas = []
    for t in transiciones:
        antes = t["conv"].get("producto_anotado") or {}
        ahora = t["ancla"] or {}
        elige = any(p in t["mensaje"].lower()
                    for p in ("anotalo", "me quedo con", "me gusta", "sacá",
                              "saca", "quiero ese"))
        if antes and ahora and antes.get("id") != ahora.get("id") and not elige:
            malas.append(f"{t['caso']}: el ancla salto de {antes.get('id')} a "
                         f"{ahora.get('id')} sin que el cliente eligiera")
        if antes and not ahora and not elige:
            malas.append(f"{t['caso']}: se borro el ancla {antes.get('id')}")
    assert not malas, "\n  ".join(malas[:8])


def test_el_reparto_que_se_guarda_cuadra_con_el_carrito_que_se_guarda(
        transiciones):
    """Un reparto que reparte mas o menos unidades de las que hay en el pedido
    manda a cotizar paquetes que no existen. Encontrado por este mismo barrido:
    con el reparto de un pedido de cinco unidades y un carrito podado a dos, el
    dato viejo sobrevivia intacto."""
    malas = []
    for t in transiciones:
        if not t["carrito"]:
            continue
        grupos = t["reparto_guardado"]
        if not grupos:
            continue
        reparte = sum(int(c.get("n") or 0) for g in grupos
                      for c in (g.get("cats") or []))
        tiene = sum(int(c.get("cantidad") or 1) for c in t["carrito"])
        if reparte != tiene:
            malas.append(f"{t['caso']}: se guarda un reparto de {reparte} "
                         f"unidades con un carrito de {tiene}")
    assert not malas, "\n  ".join(malas[:8])

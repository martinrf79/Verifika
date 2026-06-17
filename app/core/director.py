"""
DIRECTOR — el LLM gobierna la caneria determinista; el codigo la ejecuta.

Reparto (idea de Martin, 15-jun): asi como el LLM interpreta mejor que el codigo
el mensaje de entrada, tambien decide MEJOR que entra y sale del estado en cada
turno, incluso en los cambios de decision del cliente. Entonces el interprete, en
la MISMA llamada que ya hace, emite ACCIONES sobre el carrito; este modulo las
EJECUTA por codigo contra el catalogo real. El LLM decide el QUE; el codigo sigue
siendo dueno del HECHO (id, precio, stock) y nunca inventa un numero.

Esto reemplaza la decision-por-codigo de cuando acoplar/desacoplar el carrito
(carrito_delta + pedido_multi + el arrastre del orchestrator), que es la fuente de
los conflictos: ahora la decision viene del LLM (que entiende), no de heuristicas.

Funcion PURA (sin LLM, sin red salvo el search del catalogo, monkeypatcheable):
se testea entera offline. Detras del flag DIRECTOR_LLM; en off nadie la llama.

Cada accion (las emite el interprete en su JSON):
  {"tipo": "agregar",          "producto": "<texto>", "cantidad": N}
  {"tipo": "sacar",            "producto": "<texto>"}
  {"tipo": "cambiar_cantidad", "producto": "<texto>", "cantidad": N}
  {"tipo": "vaciar"}
Lista vacia = el turno NO toca el carrito (una pregunta, un saludo). Esa es la
clave que mata el arrastre: sin accion, el carrito queda igual y no se re-estampa.
"""
import re
from typing import Optional

from app.core.pedido_multi import _singular, _norm
from app.core.certificador import certificar
from app.logger import get_logger

log = get_logger(__name__)

_TIPOS = {"agregar", "sacar", "cambiar_cantidad", "vaciar"}


def _resolver(term: str, tienda_id: str,
              trace_id: Optional[str] = None) -> dict:
    """Resuelve un texto de producto a UN item del catalogo. NO tiene logica de
    identidad propia: delega en el CERTIFICADOR, la unica autoridad. Solo traduce
    el veredicto (exists/ambiguous/not_found) al shape que usa aplicar_acciones
    (ok/ambiguo/no_encontrado)."""
    v = certificar(term, tienda_id, trace_id=trace_id)
    status = v.get("status")
    if status == "exists":
        return {"estado": "ok", "item": v["item"]}
    if status == "ambiguous":
        return {"estado": "ambiguo",
                "candidatos": [{"id": c.get("product_id"),
                                "nombre": c.get("nombre"),
                                "precio_ars": c.get("precio_ars")}
                               for c in v.get("candidates", [])]}
    return {"estado": "no_encontrado"}


def _match_en_carrito(term: str, carrito: list[dict]) -> Optional[int]:
    """Indice del item del carrito que el texto nombra (para sacar / cambiar).
    Elige al item con MAS tokens en comun con el termino, no a cualquiera que
    comparta uno. Sin esto 'Teclado Logitech K380 Negro' pegaba tambien con el
    'Mouse Logitech G203 Negro' (comparten 'logitech' y 'negro') y, al ver dos
    candidatos, no aplicaba el cambio. Devuelve el ganador solo si es UNICO: si
    dos items empatan en solapamiento, es ambiguo de verdad y no adivina."""
    toks = {_singular(t) for t in _norm(term).split() if len(t) >= 3}
    if not toks:
        return None
    mejor_idx: Optional[int] = None
    mejor_n = 0
    segundo_n = 0
    for i, it in enumerate(carrito):
        nombre_toks = {_singular(t) for t in _norm(it.get("nombre", "")).split()}
        n = len(toks & nombre_toks)
        if n > mejor_n:
            segundo_n = mejor_n
            mejor_n, mejor_idx = n, i
        elif n > segundo_n:
            segundo_n = n
    # Necesita al menos un token en comun y un ganador claro (mas que el segundo).
    if mejor_n > 0 and mejor_n > segundo_n:
        return mejor_idx
    return None


def aplicar_acciones(acciones: list, carrito: list[dict], tienda_id: str,
                     trace_id: Optional[str] = None) -> dict:
    """Aplica las acciones del interprete sobre el carrito, por codigo.

    Args:
        acciones: lista de dicts {tipo, producto?, cantidad?} del interprete.
        carrito: items vigentes [{product_id, nombre, cantidad, precio_ars}].
        tienda_id: tienda activa.

    Returns:
        {"carrito": [...], "cambios": [...], "ambiguos": [...],
         "no_encontrados": [...]}. carrito SIEMPRE presente (igual al de entrada
        si no hubo accion valida). Nunca inventa precio: sale del catalogo.
    """
    # Copia de trabajo. La clave canonica del carrito es "id" (igual que
    # carrito_delta y lo que el provider lee para cotizar): NO usar product_id.
    nuevo = [dict(it) for it in (carrito or []) if it.get("id")]
    cambios, ambiguos, no_encontrados = [], [], []

    for acc in (acciones or []):
        if not isinstance(acc, dict):
            continue
        tipo = str(acc.get("tipo", "")).strip().lower()
        if tipo not in _TIPOS:
            continue
        term = str(acc.get("producto", "")).strip()
        # 0 es valido para cambiar_cantidad (= sacar); para agregar se trata como 1.
        cant_raw = acc.get("cantidad")
        cant = int(cant_raw) if isinstance(cant_raw, (int, float)) \
            and 0 <= cant_raw <= 50 else 1

        if tipo == "vaciar":
            if nuevo:
                cambios.append({"tipo": "vaciar"})
            nuevo = []
            continue

        if tipo == "sacar":
            idx = _match_en_carrito(term, nuevo)
            if idx is not None:
                cambios.append({"tipo": "sacar", "nombre": nuevo[idx].get("nombre")})
                nuevo.pop(idx)
            continue

        if tipo == "cambiar_cantidad":
            idx = _match_en_carrito(term, nuevo)
            if idx is not None:
                if cant <= 0:
                    cambios.append({"tipo": "sacar",
                                    "nombre": nuevo[idx].get("nombre")})
                    nuevo.pop(idx)
                else:
                    nuevo[idx]["cantidad"] = cant
                    cambios.append({"tipo": "cambiar_cantidad",
                                    "nombre": nuevo[idx].get("nombre"),
                                    "cantidad": cant})
            continue

        # agregar (cantidad minima 1; el 0 no aplica al agregar)
        if not term:
            continue
        cant = max(cant, 1)
        res = _resolver(term, tienda_id, trace_id=trace_id)
        if res["estado"] == "ambiguo":
            ambiguos.append({"termino": term, "cantidad": cant,
                             "candidatos": res["candidatos"]})
            continue
        if res["estado"] == "no_encontrado":
            no_encontrados.append(term)
            continue
        it = res["item"]
        # Ya en el carrito: suma cantidad. Nuevo: lo agrega. Clave canonica "id".
        existente = next((x for x in nuevo if x.get("id") == it["id"]), None)
        if existente:
            existente["cantidad"] = existente.get("cantidad", 1) + cant
            cambios.append({"tipo": "sumar", "nombre": it.get("nombre"),
                            "cantidad": existente["cantidad"]})
        else:
            nuevo.append({"id": it["id"], "nombre": it.get("nombre"),
                          "cantidad": cant, "precio_ars": it.get("precio_ars")})
            cambios.append({"tipo": "agregar", "nombre": it.get("nombre"),
                            "cantidad": cant})

    if cambios or ambiguos or no_encontrados:
        log.info("director_acciones_aplicadas", trace_id=trace_id,
                 cambios=len(cambios), ambiguos=len(ambiguos),
                 no_encontrados=len(no_encontrados), items=len(nuevo))
    return {"carrito": nuevo, "cambios": cambios, "ambiguos": ambiguos,
            "no_encontrados": no_encontrados}

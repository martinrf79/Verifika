"""EL TURNO DEL FLUJO NUEVO: LA LLAMADA 0, LOS NEXOS CON JEV, EL CODIGO, LA SEGUNDA LLAMADA Y LA MEMORIA (17-nov-2026).

Orden de Martin del 17-nov, FICHA 101: el flujo de dos llamadas reemplaza al agente en el bot. `responder` tiene la misma
entrada y salida que tenia `agente.responder`, y lo llama `turno.procesar_turno`:

  1. la llamada 0      el mensaje solo, `llamada0.pedir`: una linea por cosa, con fragmento, busqueda y destino.
  2. los embeddings    las busquedas y los fragmentos contra el indice de la tienda, `vectores.puntajes`.
  3. Jev               lo dudoso del tema y del producto, en una llamada por mensaje.
  4. la condicion      las partes de cada busqueda que el codigo no ato: sus embeddings y Jev, sobre el rubro elegido.
  5. los nexos         `contrato.flujo`: producto, nombrado, condicion, tema y destino, y el texto del codigo.
  6. la segunda        `segunda.llamar`: el texto retocado y los comandos del pedido, que aplica el codigo del agente.
  7. el control        el verificador sobre el texto retocado; si marca, sale el texto del codigo.
  8. la memoria        `memoria_agente`: la libreta, el pago, el tope, el lead, lo dicho y lo visto.

Si un paso falla, el turno sigue con lo que tiene: sin Jev queda lo que eligio el codigo; sin embeddings, sin nexos; sin
segunda llamada, el texto del codigo. Cada paso se anota con su `trace_id`. Las piezas con red estan en `Vivo`; el banco
le pasa las suyas, grabadas, a `responder`, y mide este mismo codigo.
"""
import asyncio
import re
import time

from app.logger import get_logger

from . import condicion as NC
from . import contrato as C
from . import jev as J
from . import llamada0 as L0
from . import segunda as S
from . import vectores as V

log = get_logger(__name__)


class Vivo:
    """Las piezas con red, para el bot."""

    def __init__(self, tid, trace_id=""):
        self.tid, self.trace_id = tid, trace_id

    def lineas(self, mensaje):
        lineas, e, s = L0.pedir(mensaje)
        log.info("flujo_llamada0", trace_id=self.trace_id, lineas=lineas, entrada=e, salida=s)
        return lineas

    def _jev(self, state, qs):
        """{pregunta: elegido}, o {} si Jev no contesta: lo dudoso queda como lo eligio el codigo."""
        if not qs:
            return {}
        try:
            r, tok = J.llamar(state, qs)
            log.info("flujo_jev", trace_id=self.trace_id, preguntas=list(qs), elige=r, tokens=tok)
            return r
        except Exception as e:  # noqa: BLE001
            log.warning("flujo_jev_error", trace_id=self.trace_id, error=f"{type(e).__name__}: {str(e)[:160]}")
            return {}

    def nexos(self, mensaje, crudas):
        """(lineas con sus nexos, texto del codigo, ids mostrados)."""
        tid = self.tid
        base = [C.Linea(str(l.get("fragmento") or ""), str(l.get("busqueda") or "").strip(),
                        str(l.get("destino") or "").strip()) for l in crudas]
        if not base:
            return [], "", []
        prod, tema = V.puntajes(tid, [l.busqueda for l in base], [l.fragmento for l in base])
        idx = C.Indice(tid, prod, tema, {}, {})
        por_id = {f["id"]: f for f in idx.filas}
        r = self._jev(f"MENSAJE DEL CLIENTE: {mensaje}", J.preguntas_mensaje(idx, base))
        frags, busqs = [l.fragmento for l in base], [l.busqueda for l in base]

        def jev_tema(fragmento):
            i = frags.index(fragmento)
            return r.get(f"t{i}") if f"t{i}" in r else idx.temas.tema(fragmento)["elegido"]

        def jev_producto(busqueda):
            i = busqs.index(busqueda)
            if f"p{i}" in r:
                return r[f"p{i}"]
            p = idx.producto({"busqueda": busqueda, "fragmento": frags[i]})
            return p["elegido"]["id"] if p["elegido"] else None

        def copia():
            return [C.Linea(l.fragmento, l.busqueda, l.destino) for l in base]
        # La condicion corre sobre el rubro que eligieron producto y nombrado: primero se ven los rubros, despues se
        # piden los embeddings de las partes que el codigo no ato y Jev elige entre los campos candidatos.
        primera, _, _ = C.flujo(copia(), idx, por_id, jev_tema, jev_producto)
        pedidas = []
        for l in primera:
            rubro = NC.rubro_de(l, por_id)[0] if l.busqueda else None
            if rubro:
                pedidas += [(rubro, l.busqueda, p) for p in NC.seguro(l.busqueda, rubro, idx.condicion.fx)[1]]
        if pedidas:
            consulta = NC.VARIANTES[idx.condicion.variante]["consulta"]
            idx.condicion.pt.p = V.puntajes_condicion(tid, [(rb, consulta(p, rb, b)) for rb, b, p in pedidas])
            for rb, b in dict.fromkeys((rb, b) for rb, b, _ in pedidas):
                partes = [p for x, y, p in pedidas if (x, y) == (rb, b)]
                e = self._jev(f"BUSQUEDA DEL CLIENTE: {b}\nPRODUCTO: {rb}", J.preguntas_condicion(idx.condicion, b, rb, partes))
                idx.condicion.jev.update({(rb, b, p): e.get(f"p{i}") for i, p in enumerate(partes) if f"p{i}" in e})
        lineas, codigo, ids = C.flujo(copia(), idx, por_id, jev_tema, jev_producto)
        log.info("flujo_nexos", trace_id=self.trace_id, nexos=[[(x.nexo, x.veredicto, x.elegido) for x in l.nexos]
                                                              for l in lineas], codigo=codigo[:1500])
        return lineas, codigo, ids

    async def segunda(self, usuario):
        a, e, s = await S.llamar(usuario)
        log.info("flujo_segunda", trace_id=self.trace_id, responde=a, entrada=e, salida=s)
        return a


async def responder(mensaje, historial, memoria, user_id, canal, tienda_id, trace_id="", piezas=None):
    """Un turno: {"respuesta", "pasos", "hallazgos", "presupuesto", "codigo", "responde"}. Sin nada que decir, la
    respuesta va vacia y `procesar_turno` pregunta en que puede ayudar."""
    from app.config import get_settings
    from app.core.flujo import agente as A
    from app.core.flujo import catalogo as K
    from app.core.flujo import redaccion
    from app.core.flujo import verificador as V_
    piezas = piezas or Vivo(tienda_id, trace_id)
    t0 = time.time()
    try:
        crudas = await asyncio.to_thread(piezas.lineas, mensaje)
    except Exception as e:  # noqa: BLE001 — sin la llamada 0, la segunda contesta con la charla
        log.warning("flujo_llamada0_error", trace_id=trace_id, error=f"{type(e).__name__}: {str(e)[:160]}")
        crudas = []
    try:
        _, codigo, ids = await asyncio.to_thread(piezas.nexos, mensaje, crudas)
    except Exception as e:  # noqa: BLE001 — sin nexos no hay datos: la segunda pregunta lo que falta
        log.warning("flujo_nexos_error", trace_id=trace_id, error=f"{type(e).__name__}: {str(e)[:160]}")
        codigo, ids = "", []
    del_cliente = list(memoria.get("dicho") or []) or [str(m.get("content") or "") for m in historial
                                                       if m.get("role") == "user"]
    usuario = S.entrada(mensaje, historial, memoria, codigo, tienda_id)
    try:
        a = await piezas.segunda(usuario)
    except Exception as e:  # noqa: BLE001 — sin segunda llamada, el texto del codigo
        log.warning("flujo_segunda_error", trace_id=trace_id, error=f"{type(e).__name__}: {str(e)[:160]}")
        a = {}
    # EL CONTROL: el texto retocado contra lo que le dio el sistema, la memoria y lo que dijo el cliente.
    fuente = " ".join([codigo, usuario] + del_cliente + [mensaje])
    texto = str(a.get("texto") or "").strip()
    malos = V_.verificar(texto, fuente, tienda_id) if texto else []
    if not texto or malos:
        texto = codigo or texto
    # LOS COMANDOS, con el codigo de produccion del agente.
    ultimo_bot = next((str(m.get("content") or "") for m in reversed(historial) if m.get("role") == "assistant"), "")
    dijo = K.n(" ".join([mensaje] + del_cliente + A.de_la_oferta(mensaje, ultimo_bot)))
    visto = K.n(" ".join([usuario] + del_cliente + [mensaje]))
    memoria.pop("_ultimo", None), memoria.pop("_cmds", None)
    pasos, pegado = [], []
    for nombre in ("pedido", "cotizar", "cobrar"):
        cmd = a.get(nombre)
        if not isinstance(cmd, dict) or not any(cmd.values()):
            continue
        try:
            res = A.pedido(cmd, memoria, tienda_id, visto, dijo) if nombre == "pedido" \
                else A.presupuesto({**cmd, "anotar": False}, memoria, tienda_id, visto, dijo) if nombre == "cotizar" \
                else await A.cobrar(cmd, memoria, user_id, canal, tienda_id, trace_id, dijo)
        except Exception as e:  # noqa: BLE001
            log.error("flujo_comando_error", trace_id=trace_id, comando=nombre, error=f"{type(e).__name__}: {str(e)[:160]}")
            res = ("", f"fallo: {type(e).__name__}")
        pasos.append({"herramienta": nombre, "pide": cmd, "devuelve": "\n".join(x for x in res if x), "al_cliente": res[0]})
        if res[0]:
            pegado.append(res[0])
    memoria.pop("_cmds", None)
    memoria.update(memoria.pop("_ultimo", None) or {})
    final = "\n\n".join(x for x in [texto] + pegado if x)
    # EL NOMBRE PARA RESERVAR, como en `agente.responder`: una vez por pedido, si el pedido no pregunta otra cosa.
    compra = sorted(f"{K.entero(x.get('cantidad')) or 1} {A._id_de(x.get('producto'), tienda_id)}" for x in memoria["pedido"])
    pidio = re.search(r"\bnombre\b|reserv", K.n(final))
    if any(p["herramienta"] == "pedido" and p["al_cliente"] and "?" not in p["al_cliente"] for p in pasos) \
            and not memoria.get("lead") and not pidio and compra != memoria.get("nombre_para"):
        final, pidio = final + "\n\n" + redaccion.pedir_nombre(), True
    memoria["nombre_para"] = compra if pidio and compra else memoria.get("nombre_para") or []
    memoria["dicho"] = (del_cliente + [mensaje])[-get_settings().MEMORIA_TURNOS:]
    # Lo visto, un objeto por turno: Firestore no guarda listas dentro de listas.
    memoria["vistos"] = ((memoria.get("vistos") or []) + ([{"ids": list(dict.fromkeys(ids))[:S.VISTOS_MAX]}] if ids else []))[-S.VISTOS_TURNOS:]
    log.info("flujo_turno", trace_id=trace_id, comandos=[p["herramienta"] for p in pasos], hallazgos=malos,
             seg=round(time.time() - t0, 1))
    return {"respuesta": final, "pasos": pasos, "hallazgos": malos, "presupuesto": "\n".join(pegado),
            "codigo": codigo, "responde": a}

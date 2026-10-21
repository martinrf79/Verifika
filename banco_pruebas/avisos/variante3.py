"""V3, lo que pidio Gemini en la entrevista por tipo, sobre los comandos de V2:
  1. el esquema de cada rubro de antemano, en la consigna: que datos tiene y se pueden filtrar;
  2. los avisos del codigo: los comandos se preparan sin responder y el codigo dice lo que no podria cumplir;
  3. una tercera vuelta, solo si hay un aviso o una condicion: el modelo ve los avisos y los datos crudos de los
     productos, corrige, y decide la condicion si los datos alcanzan."""
import collections
import re

import comandos as Cm
import contexto
import pistas as P
from app.core.flujo import agenda as A
from app.core.flujo import borrador as B
from app.core.flujo import catalogo as K
from app.core.flujo import interprete as I

TIENDA = P.TIENDA


def esquema() -> str:
    ps = K.productos(TIENDA)
    por, n = collections.defaultdict(collections.Counter), collections.Counter()
    texto_libre = set()
    for p in ps:
        r = p.get("categoria")
        n[r] += 1
        for k, v in (p.get("specs") or {}).items():
            if v and k != "garantia":
                por[r][k] += 1
        if p.get("origen"):
            texto_libre.add("origen")
    lineas = [f"- {r}: " + ", ".join(k.replace("_", " ") for k, c in por[r].most_common() if c >= max(1, n[r] // 3))
              for r in sorted(n)]
    return ("LOS DATOS DE CADA RUBRO, que el codigo da y puede filtrar. Todos tienen marca, color, precio, stock, "
            "garantia y peso; ademas:\n" + "\n".join(lineas)
            + ("\nEl origen y el pais de fabricacion estan escritos en texto: el codigo no filtra por eso." if texto_libre else ""))


def consigna(tienda_id: str) -> str:
    base = Cm.consigna(tienda_id)
    return base.replace("RUBROS: ", esquema() + "\n\nRUBROS: ", 1)


TERCERA = """LO QUE EL CODIGO VIO AL PREPARAR TUS COMANDOS, sin contestarle todavia al cliente:
{avisos}
{datos}
Revisa tus renglones con esto:
- Si un aviso dice que algo no se puede cumplir, corregi ese renglon.
- Si un renglon depende de una condicion, si="n:si" o si="n:no", y los DATOS alcanzan para decidirla, decidila: deja el
  renglon sin "si" si se cumple, o cambialo por OTRO que="dato" si no se cumple. Si los datos no alcanzan, dejalo como esta.
- Si algo puede ser varios y el cliente no dijo cual, usa la lista para que el codigo pregunte.
- No escribas precios ni datos que el cliente no dijo: los pone el codigo.
Devolve todos los renglones de nuevo, con la misma forma."""


def _producto_de(x, nums: dict):
    """El producto que nombra un renglon: un M-n de la libreta o lo que dijo el cliente. None si es un rubro o no es."""
    x = str(x or "").strip()
    if not x:
        return None, ""
    if x.startswith("M-"):
        pid = nums.get(x)
        p = next((q for q in K.productos(TIENDA) if str(q["id"]) == str(pid)), None)
        return (p, "") if p else (None, f'senala {x}, que no esta en la libreta')
    if x.startswith(("L-", "R-")) or K.solo_rubro(x, TIENDA) or K.n(x) in ("los otros", "el resto", "lo demas"):
        return None, ""
    idt = K.identificar(x, "", TIENDA)
    if idt["veredicto"] == "exists":
        return idt["producto"], ""
    if idt["veredicto"] == "ambiguous":
        ops = [o.get("nombre") for o in (idt.get("opciones") or [])]
        return None, f'"{x}" puede ser {len(ops)} productos, como {" o ".join(ops[:4])}: si no dice cual, el codigo pregunta'
    return None, f'"{x}" no esta en el catalogo'


def _lugares(t: str) -> int:
    r = P._lugar(t)
    if r.startswith("no es"):
        return 0
    m = re.match(r"son (\d+) localidades", r)
    return int(m.group(1)) if m else 1


def avisos(agenda: dict, estado: dict, mensaje: str):
    """(problemas, datos, hay_condicion). Los problemas disparan la tercera vuelta; los datos van con ella."""
    from app.core import agente
    nums = I.numeros(estado)
    problemas = list(A.faltas(mensaje, agenda, set(nums)))
    datos, vistos = [], set()
    hay_si = False
    vacio = not B.leer(estado.get("borrador"))["renglones"]
    mostrados = [v for k, v in nums.items() if k.startswith("M-")]
    temas = set(agente.indice(TIENDA)["temas"])
    todos = K.productos(TIENDA)

    def dato(p):
        if p and p["id"] not in vistos:
            vistos.add(p["id"])
            datos.append("  " + I.datos(p, todos))

    for q in A.preguntas(agenda):
        n, acc = q.get("n"), q.get("accion")
        hay_si = hay_si or bool(q.get("si"))
        if acc == "producto":
            for x in (q.get("producto") if isinstance(q.get("producto"), list) else [q.get("producto")]):
                p, aviso = _producto_de(x, nums)
                dato(p)
                if aviso:
                    problemas.append(f"renglon {n}: {aviso}.")
        elif acc == "comprar":
            for a in q.get("agrega") or []:
                p, aviso = _producto_de(a.get("producto"), nums)
                dato(p)
                if aviso:
                    problemas.append(f"renglon {n}: {aviso}.")
            if vacio and any(q.get(k) for k in ("saca", "cambia", "confirma", "acepta")):
                problemas.append(f"renglon {n}: el pedido esta vacio, no hay renglones para cambiar, sacar ni confirmar.")
        elif acc == "envio":
            k = _lugares(q.get("destino"))
            if k == 0:
                problemas.append(f'renglon {n}: "{q.get("destino")}" no es una localidad a la que se envie.')
            elif k > 1:
                problemas.append(f'renglon {n}: "{q.get("destino")}" son {k} lugares: un ENVIO por cada uno.')
        elif acc == "buscar":
            rub = str(q.get("rubro") or "")
            if rub not in ("el pedido",) and not K.rubro(rub, TIENDA):
                problemas.append(f'renglon {n}: "{rub}" no es un rubro de la tienda.')
                continue
            rub = K.rubro(rub, TIENDA) if rub != "el pedido" else ""
            conds = q.get("condiciones") or []
            entre = mostrados if q.get("entre_lo_mostrado") else None
            r = K.buscar(rub, conds, q.get("orden") or "nada", int(q.get("cantidad") or 1) if str(q.get("cantidad") or 1).isdigit() else 1,
                         TIENDA, entre=entre)
            if r["sin_campo"]:
                datos.append(f"  renglon {n}: el codigo no tiene un dato para: {', '.join(r['sin_campo'])}.")
            if r["vacio_por"] or not r["filas"]:
                donde = "entre lo mostrado" if entre is not None else "en la tienda"
                total = len(K.buscar(rub, conds, "nada", 50, TIENDA)["filas"]) if entre is not None else 0
                problemas.append(f"renglon {n}: {donde} no hay ninguno que cumpla"
                                 + (f" {', '.join(r['vacio_por'])}" if r["vacio_por"] else "")
                                 + (f"; en toda la tienda hay {total}" if entre is not None else "") + ".")
        elif acc == "politica":
            if q.get("tema") not in temas:
                problemas.append(f'renglon {n}: "{q.get("tema")}" no es un tema de la lista TEMAS.')
    return problemas, datos, hay_si


# El banco curado, paso 3: si esta puesto, devuelve los ejemplos elegidos para este mensaje, que van antes de la libreta.
EXTRA = None


def instalar():
    async def interpretar(mensaje, historial, estado, tienda_id, trace_id=""):
        hay = bool([m for m in historial if m.get("role") == "user"])
        pistas = P.paso1(mensaje, hay)
        respuestas = P.contestar(pistas, estado)
        libreta = I.libreta(estado, historial, tienda_id)
        extra = EXTRA(mensaje, libreta, pistas) if EXTRA else ""
        msgs = [{"role": "system", "content": consigna(tienda_id)},
                {"role": "user", "content": extra + libreta + "\n" + respuestas + f"\nULTIMO MENSAJE: {mensaje}"}]
        try:
            crudo, uso = contexto.llamar(msgs)
            P.USO.append({"paso": 2, **uso})
            salida = Cm.a_agenda(crudo)
            problemas, datos, hay_si = avisos(salida, estado, mensaje)
            if problemas or hay_si:
                texto = TERCERA.format(avisos="\n".join("- " + x for x in problemas) or "- nada que corregir.",
                                       datos=("DATOS DE LOS PRODUCTOS:\n" + "\n".join(datos)) if datos else "")
                crudo2, uso = contexto.llamar(msgs + [{"role": "assistant", "content": crudo},
                                                      {"role": "user", "content": texto}])
                P.USO.append({"paso": 3, **uso})
                otra = Cm.a_agenda(crudo2)
                if otra["preguntas"]:
                    salida = otra
                crudo = crudo + "\n---AVISOS---\n" + texto + "\n---TERCERA---\n" + crudo2
        except Exception as e:  # noqa: BLE001
            print("V3 error", type(e).__name__, str(e)[:200], flush=True)
            return None
        salida["_crudo"] = crudo
        return salida
    I.interpretar = interpretar

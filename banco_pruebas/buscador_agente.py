"""EL BUSCADOR DE LA TIENDA — el modelo vende con un buscador en su idioma, como hace con la web (29-oct-2026, FICHA 83).

Orden de Martin del 29-oct: el modelo ya fue entrenado de sobra; hay que adaptar las herramientas a ese entrenamiento y
acercarle la informacion correcta. Hasta hoy las herramientas hablaban nuestro idioma —acciones, campos, hace y sobre— y
el modelo fallaba justo en esos significados. Lo que sabe hacer desde su entrenamiento es buscar con sus palabras, leer
resultados y contestar con lo que leyo.

  buscar(consulta)     castellano libre. El codigo contesta como un buscador, con filas reales de la tienda: el modelo
                       nombrado con su ficha, el estante entero de cada rubro que aparece, ordenado por precio, la
                       respuesta de cada tema de la tienda y el envio a cada lugar. Trae de mas: el catalogo es chico, y
                       asi no hace falta entender perfecto para traer lo correcto.
  calcular(cuenta)     una calculadora, para los totales.
  el candado           cada monto de la respuesta tiene que estar en lo que devolvio el buscador o la calculadora. Lo que
                       no esta se cuenta como inventado.

La vara es la de siempre: las casillas del turno en `vara_58.json` sobre lo que lee el cliente, en los primeros 65, los
24 fuera de muestra y los 40 turnos con charla. Los turnos de antes corren con la agenda a mano, como en
`agente_ventas.py`.

    MARTIN_AUTORIZO_LA_PAGA=<fecha> python3 banco_pruebas/buscador_agente.py --llamar [--hasta 10] [C27 K20 ...]
    python3 banco_pruebas/buscador_agente.py [--ver]                       sin modelo, lo grabado
"""
import collections
import copy
import json
import os
import re
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
# La paga se toma antes de importar el banco, que la saca del entorno.
_PAGA = os.environ.get("GEMINI_API_KEY_PROD") if os.environ.get("MARTIN_AUTORIZO_LA_PAGA") else None
import carrito_modelo as CM  # noqa: E402
import herramientas_modelo as HM  # noqa: E402
from app.core.flujo import catalogo as K  # noqa: E402
from app.core.flujo import ficha as F  # noqa: E402
from app.core.flujo import interprete  # noqa: E402

RL = HM.RL
if _PAGA:
    RL.PAGA, RL.BM.PAGA = True, _PAGA
TID = HM.TID
ARGS = HM.ARGS
GRABADO = os.path.join(AQUI, "buscador_agente.jsonl")
VUELTAS = 4

CONSIGNA = """Sos vendedor de una tienda online de tecnologia de Argentina que vende por WhatsApp. Contestas el ultimo
mensaje del cliente como un buen vendedor: corto, claro, en español rioplatense con voseo, contestando todo lo que
pregunto o pidio y llevando a la venta.

Tenes dos herramientas:
- buscar: el buscador de la tienda. Buscas con tus palabras lo que necesites saber, una cosa por busqueda o varias
  juntas: un producto, una clase de productos, una regla de la tienda, el envio a un lugar. Devuelve lo que la tienda
  tiene de verdad: productos con precio, stock, colores y ficha; reglas; envios.
- calcular: una calculadora, para cualquier cuenta: subtotales, totales, envios sumados, porcentajes.

Todo producto, precio, stock, dato de ficha, envio o regla que digas tiene que salir del buscador. Si no lo encontraste,
no lo digas: decile al cliente que no lo tenes o preguntale lo que falte. Las cuentas, con la calculadora. Si el cliente
pide algo que no eligio todavia y hace falta elegir para seguir, elegi vos con el criterio que dio, o el mas barato con
stock, y decile cual elegiste."""

HERRAMIENTAS = [
    {"type": "function", "function": {"name": "buscar", "description": "El buscador de la tienda, en castellano libre.",
                                      "parameters": {"type": "object", "properties": {"consulta": {"type": "string"}},
                                                     "required": ["consulta"]}}},
    {"type": "function", "function": {"name": "calcular",
                                      "description": "Una calculadora: una cuenta con numeros, + - * / y parentesis.",
                                      "parameters": {"type": "object", "properties": {"cuenta": {"type": "string"}},
                                                     "required": ["cuenta"]}}}]


# ══ EL BUSCADOR: castellano libre, filas reales de la tienda ══

_IND = None


def _indice():
    global _IND
    if _IND is None:
        _IND = RL.Indice()
    return _IND


def _fila(p: dict, todos: list) -> str:
    return interprete.datos(p, todos)


def buscar(consulta: str, estado: dict) -> str:
    """Lo que la tienda tiene para la consulta, en texto. Trae de mas a proposito."""
    from app.core.flujo import estado as E  # noqa: F401
    from app.core.flujo import lectura as L
    from app.core.flujo import marcador as MK
    from app.core.flujo import redaccion
    from app.core.flujo.ejecutor import ejecutar
    todos = K.productos(TID)
    q = K.n(consulta)
    ws = [w for w in re.findall(r"[a-z0-9]+", q) if w not in K._RELLENO]
    out, vistos = [], set()
    # Los modelos que nombra, con la ficha de cada color.
    for tramo, _ in MK._productos(ws, TID):
        idt = K.identificar(tramo, "", TID)
        ps = [idt["producto"]] if idt["veredicto"] == "exists" else idt.get("opciones") or []
        for p in ps:
            fam = F._familia(p)
            if fam in vistos:
                continue
            vistos.add(fam)
            out.append("PRODUCTO: " + _fila(p, todos))
    # Los rubros: por su nombre o alias, y los dos mas parecidos por significado.
    ind = _indice()
    ind.preparar([consulta])
    cands, _ = ind.candidatos(consulta, "", tipos=("rubro",))
    # UMBRALES DEL BANCO, 29-oct, a revisar con Martin: el rubro correcto da cerca de 0,78 y el ruido de 0,65 a 0,74.
    # Con un modelo nombrado no se suma un estante por significado: el modelo puede buscarlo si lo necesita.
    por_sentido = [k[1] for k, s in cands[:1] if s >= 0.75] if not vistos else []
    rubros = list(dict.fromkeys([r for _, r in MK._rubros(q.split(), TID)] + por_sentido))
    for r in rubros[:3]:
        est = sorted([p for p in todos if p.get("categoria") == r], key=lambda p: K.entero(p.get("precio_ars")) or 0)
        familias = {}
        for p in est:
            familias.setdefault(F._familia(p), p)
        filas = ["; ".join(_fila(p, todos).split("; ")[:5]) for p in familias.values()][:25]
        out.append(f"ESTANTE {r.upper()}, de menor a mayor precio:\n  " + "\n  ".join(filas))
    # Las reglas: por las frases de la FAQ y por significado.
    tcands, _ = ind.candidatos(consulta, "", tipos=("tema",))
    temas = list(dict.fromkeys([RL._tema_por_clave(q, "")] + [k[1] for k, s in tcands[:1] if s >= 0.70]))
    for tm in [t for t in temas if t][:2]:
        t = ejecutar({"preguntas": [{"n": 1, "accion": "politica", "tema": tm}], "cliente": {}, "responde": "",
                      "respuesta": "", "dudas": []}, copy.deepcopy(estado), TID)
        out.append(f"REGLA {tm.replace('_', ' ')}: " + " ".join(h.get("texto") or "" for h in t.hechos))
    # El envio a cada lugar que nombra.
    for d in L._lugares(consulta):
        t = ejecutar({"preguntas": [{"n": 1, "accion": "envio", "destino": d}], "cliente": {}, "responde": "",
                      "respuesta": "", "dudas": []}, copy.deepcopy(estado), TID)
        out.append("ENVIO: " + redaccion.texto(t.hechos, t.preguntas, False).replace("\n", " "))
    if not out:
        return "Sin resultados en la tienda para eso. La tienda vende: " + ", ".join(F._rubros(TID)) + "."
    return "\n".join(out)


def calcular(cuenta: str) -> str:
    c = re.sub(r"(?<=\d)\.(?=\d{3}\b)", "", str(cuenta)).replace("$", "").replace(",", ".").replace("x", "*")
    if not re.fullmatch(r"[\d\s+\-*/().%]+", c):
        return "Solo numeros y + - * / ( )."
    try:
        v = eval(c.replace("%", "/100"), {"__builtins__": {}}, {})  # noqa: S307 — solo aritmetica, validada arriba
    except Exception:  # noqa: BLE001
        return "Cuenta mal escrita."
    return f"{cuenta} = {round(v, 2):,.0f}".replace(",", ".") if float(v).is_integer() or abs(v) > 100 \
        else f"{cuenta} = {round(v, 2)}"


# ══ EL CANDADO: cada monto de la respuesta, en lo que devolvieron las herramientas ══

def _montos(texto: str) -> set:
    return {int(re.sub(r"\D", "", m)) for m in re.findall(r"\$\s?\d[\d.]*", texto) if re.sub(r"\D", "", m)}


def inventados(respuesta: str, salidas: list) -> list:
    fuente = " ".join(salidas)
    validos = _montos(fuente) | {int(re.sub(r"\D", "", m)) for m in re.findall(r"= ([\d.]+)", fuente)}
    return sorted(m for m in _montos(respuesta) if m not in validos)


# ══ EL AGENTE ══

def _cliente():
    from openai import OpenAI
    from app.config import get_settings
    clave = (_PAGA or os.environ["GEMINI_API_KEY"]).split()[0]
    return OpenAI(api_key=clave, base_url=get_settings().GEMINI_BASE_URL), bool(_PAGA), get_settings().GEMINI_MODEL


def charla(h: list) -> str:
    if not h:
        return "Charla nueva."
    return "LA CHARLA HASTA ACA:\n" + "\n".join(f"{'Cliente' if r == 'user' else 'Vos'}: {t}" for r, t in h)


def agente(cli, modelo: str, paga: bool, msg: str, estado: dict, h: list) -> dict:
    from banco_pruebas import libro_paga
    msgs = [{"role": "system", "content": CONSIGNA},
            {"role": "user", "content": f"{charla(h)}\n\nESTADO DEL PEDIDO:\n{CM.carrito(estado)}\n\n"
                                        f"ULTIMO MENSAJE DEL CLIENTE: {msg}"}]
    pasos, salidas, entrada, salida = [], [], 0, 0
    t0 = time.time()
    for vuelta in range(VUELTAS + 1):
        kw = {"tools": HERRAMIENTAS} if vuelta < VUELTAS else {}
        for intento in range(5):
            try:
                if paga:
                    libro_paga.puede()
                r = cli.chat.completions.create(model=modelo, temperature=0, messages=msgs, **kw)
                break
            except libro_paga.TopeDiario:
                raise
            except Exception as e:  # noqa: BLE001
                if intento == 4:
                    return {"error": f"{type(e).__name__}: {str(e)[:160]}", "pasos": pasos}
                time.sleep(10 * (intento + 1))
        u = r.usage
        entrada, salida = entrada + u.prompt_tokens, salida + u.completion_tokens
        if paga:
            libro_paga.anotar(modelo, u.prompt_tokens, u.completion_tokens)
        m = r.choices[0].message
        if not m.tool_calls:
            texto = m.content or ""
            return {"respuesta": texto, "pasos": pasos, "inventados": inventados(texto, salidas), "entrada": entrada,
                    "salida": salida, "seg": round(time.time() - t0, 1), "vueltas": vuelta}
        msgs.append({"role": "assistant", "content": m.content or "", "tool_calls": [
            {"id": c.id, "type": "function", "function": {"name": c.function.name, "arguments": c.function.arguments}}
            for c in m.tool_calls]})
        for c in m.tool_calls:
            a = json.loads(c.function.arguments or "{}")
            res = buscar(a.get("consulta", ""), estado) if c.function.name == "buscar" else calcular(a.get("cuenta", ""))
            pasos.append({"herramienta": c.function.name, "pide": a, "devuelve": res})
            salidas.append(res)
            msgs.append({"role": "tool", "tool_call_id": c.id, "content": res})
    return {"error": "sin respuesta", "pasos": pasos}


def main() -> None:
    from banco_pruebas.agendas58 import AGENDAS, EXPLICAR
    from banco_pruebas.sonda_charlas import nota_casilla
    from app.core.flujo import estado as E
    from app.storage import firestore_client as fc
    llamar = "--llamar" in ARGS
    interp = HM.C58.instalar()
    grab = {(r["conjunto"], r["id"], r["turno"]): r for r in map(json.loads, open(GRABADO, encoding="utf-8"))
            if "respuesta" in r} if os.path.exists(GRABADO) else {}
    vara = {c["id"]: c for c in json.load(open(os.path.join(AQUI, "vara_58.json"), encoding="utf-8"))["charlas"]}
    if llamar:
        cli, paga, modelo = _cliente()
        print(f"{'PAGA' if paga else 'gratis'} · {modelo}", flush=True)
    nota, tot, inv, filas, pedidos = collections.Counter(), collections.Counter(), collections.Counter(), [], 0
    for conj, ch, t, msg, _, _, _, _ in HM.casos():
        previas = list(AGENDAS.get(ch) or [])[:t]
        if len(previas) < t or ch not in vara:
            continue
        g = grab.get((conj, ch, t))
        if not g and not (llamar and (not HM.HASTA or pedidos < HM.HASTA)):
            continue
        turnos = vara[ch]["turnos"]
        previos = HM.C58.correr({"id": ch, "turnos": turnos[:t]}, previas, interp, EXPLICAR) if t else []
        estado = E.leer(fc.get_conversation(f"cableado_{ch}", tienda_id=TID) or {}) if t else E.leer({})
        if not g:
            pedidos += 1
            h = [x for p in previos for x in (("user", p["texto"]), ("assistant", p["respuesta"]))]
            g = {"conjunto": conj, "id": ch, "turno": t, "mensaje": msg,
                 **agente(cli, modelo, paga, msg, estado, h)}
            with open(GRABADO, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(g, ensure_ascii=False) + "\n")
            print(f"  {conj} {ch} t{t}: {len(g.get('pasos') or [])} pasos {g.get('seg')}s "
                  f"{g.get('entrada')}+{g.get('salida')} {g.get('error') or ''}", flush=True)
            if "respuesta" not in g:
                continue
        final = g["respuesta"]
        respuestas = [x["respuesta"] for x in previos] + [final]
        malas = [k["n"] for k in turnos[t]["casillas"] if nota_casilla(k, [], final, respuestas) is not True]
        tot[conj] += 1
        nota[conj] += not malas
        inv[conj] += bool(g.get("inventados"))
        filas.append({**g, "malas": malas})
    print("\nEL BUSCADOR DE LA TIENDA · casillas del turno · respuestas con algun monto que no salio de las herramientas")
    for conj in tot:
        print(f"  {conj:16} {nota[conj]} de {tot[conj]} · con montos inventados {inv[conj]}")
    if filas:
        n = len(filas)
        print(f"  por turno: entrada {sum(f.get('entrada') or 0 for f in filas) / n:.0f} tokens, salida "
              f"{sum(f.get('salida') or 0 for f in filas) / n:.0f}, busquedas "
              f"{sum(len(f.get('pasos') or []) for f in filas) / n:.1f}, demora mediana "
              f"{sorted(f.get('seg') or 0 for f in filas)[n // 2]}s")
    for f in filas:
        if (f["malas"] or f.get("inventados")) and (HM.VER or HM.SOLO):
            print(f"\n{f['id']} t{f['turno']} {f['conjunto']}: {f['mensaje'][:160]}\n  MAL: {'; '.join(f['malas'])}"
                  f" · inventados {f.get('inventados')}")
            for p in f.get("pasos") or []:
                print(f"  > {p['herramienta']} {json.dumps(p['pide'], ensure_ascii=False)}")
            print("  " + f["respuesta"][:900].replace("\n", "\n  "))


if __name__ == "__main__":
    main()

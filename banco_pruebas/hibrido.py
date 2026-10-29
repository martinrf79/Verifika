"""EL HIBRIDO — el modelo solo dice que hace cada linea, de una lista corta, y el codigo pone los datos (28-oct-2026, FICHA 83).

Pedido de Martin del 28-oct, despues de `herramientas_modelo.py` y `carrito_modelo.py`: cada uno hace lo que mostro
hacer bien. El codigo con las lineas, `responder_lineas.py`, fallo en entender la forma del pedido —toda la tienda, el
catalogo, lo que no vende, el total dicho dos veces—; el modelo, en los argumentos —elegia productos, perdia datos,
escribia frases que el codigo no ata—. Aca el modelo clasifica, que es lo que mas practico por entrenamiento: por cada
linea, que hace el cliente, de `responder_lineas.CLASES`, y a que senala por su numero. No ve productos candidatos. Los
datos los pone el codigo con `responder_lineas.a_salida`, y de ahi la lectura viva, el ejecutor y la redaccion.

  B   una segunda llamada chica: el carrito en palabras, el mensaje y las lineas ya grabadas -> la clase de cada linea.
  A   sin llamada extra: la primera llamada separa y clasifica en el mismo paso, con la consigna de cosa y tema.

Los casos y la vara son los de `herramientas_modelo.py`.

    python3 banco_pruebas/hibrido.py --llamar [--a] [--hasta 10]      con la gratis
    MARTIN_AUTORIZO_LA_PAGA=<fecha> python3 banco_pruebas/hibrido.py --llamar [--a]
    python3 banco_pruebas/hibrido.py [--a] [--ver]                     sin modelo
"""
import json
import os
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
# LA ORDEN DE LA PAGA SE LEE ANTES DEL CLON, que la saca del entorno.
_PAGA = os.environ.get("GEMINI_API_KEY_PROD") if os.environ.get("MARTIN_AUTORIZO_LA_PAGA") else None
import carrito_modelo as CM  # noqa: E402  — el carrito en palabras y los numeros
import herramientas_modelo as HM  # noqa: E402
import momento0 as M0  # noqa: E402
import responder_lineas as RL  # noqa: E402
from app.core.flujo import ficha as F  # noqa: E402
from app.core.flujo import interprete  # noqa: E402
from app.core.flujo import lectura as L  # noqa: E402

TID = HM.TID
VA = "--a" in HM.ARGS
HM.GRABADO = os.path.join(AQUI, "hibrido_a.jsonl" if VA else "hibrido_b.jsonl")
if _PAGA:
    RL.PAGA, RL.BM.PAGA = True, _PAGA

_LISTA = "\n".join(f"- {k}: {v}" for k, v in RL.CLASES.items())

CONSIGNA_B = f"""Lees el mensaje de un cliente de una tienda online de tecnologia de Argentina, ya separado en lineas. Por
cada linea decis dos cosas, nada mas:
- "hace": que hace el cliente en esa linea, de esta lista:
{_LISTA}
- "senala": si se refiere a algo del carrito, de lo que le mostraron o de lo que pregunto el vendedor, su numero tal como
  aparece: "item 2", "mostrado 1", "pregunta 1". Si no, vacio.

EJEMPLOS:
Carrito: item 1: 2 mouse a Rosario. Mostrado 1: Logitech G305. Mensaje: "el de Rosario mejor que sea uno, y el G305 es
inalambrico?" -> 1 cambia, item 1; 2 dato, mostrado 1.
Charla nueva. Mensaje: "venden drones? y lo mas barato que tengan" -> 1 no_vende; 2 ver.
Pregunta 1 del vendedor: "¿te lo confirmo?". Mensaje: "dale, y cuanto queda todo?" -> 1 contesta, pregunta 1; 2 total."""

FORMATO_B = {"type": "json_schema", "json_schema": {"name": "clases", "schema": {"type": "object", "properties": {
    "lineas": {"type": "array", "items": {"type": "object", "properties": {
        "n": {"type": "integer"}, "hace": {"type": "string", "enum": list(RL.CLASES)}, "senala": {"type": "string"}},
        "required": ["n", "hace", "senala"]}}}, "required": ["lineas"]}}}

AGREGA_A = f"""

ADEMAS, en cada linea:
- "hace": que hace el cliente en esa linea, de esta lista:
{_LISTA}
- "senala": si se refiere a algo de la libreta, su numero: "L-1", "M-2", "R-1". Si no, vacio."""


def formato_a() -> dict:
    f = json.loads(json.dumps(M0.formato_tema()))
    linea = f["json_schema"]["schema"]["properties"]["lineas"]["items"]
    linea["properties"].update(hace={"type": "string", "enum": list(RL.CLASES)}, senala={"type": "string"})
    linea["required"] += ["hace", "senala"]
    return f


def _cliente():
    from openai import OpenAI
    from app.config import get_settings
    clave = (_PAGA or os.environ["GEMINI_API_KEY"]).split()[0]
    return OpenAI(api_key=clave, base_url=get_settings().GEMINI_BASE_URL), bool(_PAGA), get_settings().GEMINI_MODEL


def llamar() -> None:
    from banco_pruebas import libro_paga
    cli, paga, modelo = _cliente()
    hechos = {(r["conjunto"], r["id"], r["turno"]) for r in map(json.loads, open(HM.GRABADO, encoding="utf-8"))
              if "error" not in r} if os.path.exists(HM.GRABADO) else set()
    pend = [c for c in HM.casos() if c[:3] not in hechos]
    pend = pend[:HM.HASTA] if HM.HASTA else pend
    temas = ", ".join(F._temas_de(TID))
    print(f"a pedir {len(pend)} · {'PAGA' if paga else 'gratis'} · {'A, separar y clasificar' if VA else 'B, llamada chica'}",
          flush=True)
    for conj, ch, t, msg, est, h, lineas, todo in pend:
        if VA:
            nueva = "vacia" in interprete.libreta(est, h, TID)
            sistema = M0.consigna_tema(temas) + ("" if nueva else M0.MEMORIA) + AGREGA_A
            user = f"MENSAJE DEL CLIENTE: {msg}" if nueva else f"{interprete.libreta(est, h, TID)}\nULTIMO MENSAJE: {msg}"
            formato = formato_a()
        else:
            sistema, formato = CONSIGNA_B, FORMATO_B
            user = (f"{CM.carrito(est)}\n\nMENSAJE: {msg}\n\nLINEAS:\n"
                    + "\n".join(f"{i}. {x.get('texto')}" for i, x in enumerate(lineas, 1)))
        fila = {"conjunto": conj, "id": ch, "turno": t, "mensaje": msg}
        for intento in range(6):
            try:
                if paga:
                    libro_paga.puede()
                t0 = time.time()
                r = cli.chat.completions.create(model=modelo, temperature=0, response_format=formato,
                                                messages=[{"role": "system", "content": sistema},
                                                          {"role": "user", "content": user}])
                u = r.usage
                if paga:
                    libro_paga.anotar(modelo, u.prompt_tokens, u.completion_tokens)
                s = interprete._json(r.choices[0].message.content or "{}")
                if VA:
                    ls, td = s.get("lineas") or [], str(s.get("todo") or "")
                    clases = [(x.get("hace") or "", x.get("senala") or "") for x in ls]
                else:
                    ls, td = lineas, todo
                    por_n = {int(x.get("n") or 0): x for x in s.get("lineas") or []}
                    clases = [((por_n.get(i) or {}).get("hace") or "", CM._ref((por_n.get(i) or {}).get("senala")))
                              for i in range(1, len(ls) + 1)]
                fila.update(seg=round(time.time() - t0, 2), entrada=u.prompt_tokens, salida=u.completion_tokens,
                            llamadas=[{"nombre": k, "args": {"linea": x, "senala": ref, "todo": td, "mensaje": msg}}
                                      for x, (k, ref) in zip(ls, clases)])
                fila.pop("error", None)
                break
            except libro_paga.TopeDiario:
                raise
            except Exception as e:  # noqa: BLE001 — la gratis se traba: se espera y se reintenta
                fila["error"] = f"{type(e).__name__}: {str(e)[:160]}"
                if "429" in str(e) and intento >= 1:
                    break  # la cuota del dia se acabo: no se espera de balde
                time.sleep(20 * (intento + 1))
        with open(HM.GRABADO, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(fila, ensure_ascii=False) + "\n")
        print(f"  {conj} {ch} t{t}: {[x['nombre'] for x in fila.get('llamadas') or []]} {fila.get('seg')}s "
              f"{fila.get('entrada')}+{fila.get('salida')} {fila.get('error') or ''}", flush=True)
        if "429" in str(fila.get("error")):
            print("SIN CUOTA: se corta", flush=True)
            return


_IND = []


def a_agenda(llamadas: list, est: dict = None) -> dict:
    """Las clases del modelo y las lineas, a la lectura viva por el codigo, y de ahi a la agenda."""
    if not llamadas:
        return {"preguntas": [], "cliente": {}, "responde": "", "respuesta": "", "dudas": []}
    if not _IND:
        _IND.append(RL.Indice())
    ind = _IND[0]
    lineas = [c["args"]["linea"] for c in llamadas]
    a = llamadas[0]["args"]
    ind.preparar([str(x.get(k) or "") for x in lineas for k in ("texto", "cosa")])
    salida, _ = RL.a_salida(lineas, a["todo"], ind, [(c["nombre"], c["args"]["senala"]) for c in llamadas])
    return L.a_agenda(salida, est or {}, TID, a["mensaje"])


HM.a_agenda = a_agenda

if __name__ == "__main__":
    llamar() if "--llamar" in HM.ARGS else HM.main()

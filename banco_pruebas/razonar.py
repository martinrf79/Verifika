"""CUANTO CUESTA Y CUANTO TARDA RAZONAR AL SEPARAR — los niveles de razonamiento del modelo (27-oct-2026, FICHA 82).

Pedido de Martin del 27-oct. El modelo de produccion tiene cuatro niveles de razonamiento, minimal, low, medium y high,
que la puerta compatible recibe como `reasoning_effort`. El proyecto nunca lo fijo. Con la consigna de las lineas,
atada, sobre una muestra de primeros mensajes: por nivel, la latencia, los tokens de entrada, de salida y de
razonamiento, el costo y si la separacion sale completa.

Va con la paga, por la puerta directa: el recuerdo de `libro_paga` no distingue el nivel y devolveria lo guardado. Cada
llamada se anota igual en el libro, con su tope.

    MARTIN_AUTORIZO_LA_PAGA=<fecha> python3 banco_pruebas/razonar.py [--n 30] [--niveles sin,minimal,low,medium,high]
"""
import json
import os
import statistics
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
ARGS = sys.argv[1:]
sys.argv = [sys.argv[0]]
# La paga se lee antes del clon, que la saca del entorno para que el banco no la use sin querer.
PAGA = os.environ.get("GEMINI_API_KEY_PROD") if os.environ.get("MARTIN_AUTORIZO_LA_PAGA") else None
DEEPSEEK = os.environ.get("DEEPSEEK_API_KEY") if os.environ.get("MARTIN_AUTORIZO_LA_PAGA") else None
sys.path.insert(0, AQUI)
import momento0 as M  # noqa: E402  — la consigna de las lineas, las varas y el entorno
from banco_pruebas import costo, libro_paga  # noqa: E402

P, V = M.P, M.V


def _opt(nombre, defecto):
    return ARGS[ARGS.index(nombre) + 1] if nombre in ARGS else defecto


def muestra(n: int) -> list:
    """La mitad de los primeros mensajes del banco, los de mas cosas; la otra mitad del desmenuzado, los mas largos."""
    from app.core.flujo import interprete
    sys.path.insert(0, os.path.join(AQUI, "nexos"))
    import desmenuzado as D
    t91 = []
    for f, cid, msg, est, h in P._turnos_sueltos():
        if "vacia" in interprete.libreta(est, h, P.TID):
            vara = M.EP._vara_de(f, cid, est)[0]
            t91.append((len([c for c in vara["cosas"] if c["acto"] not in M.FUERA]), ("91", cid, msg, vara)))
    t138 = sorted([c for c in D.CASOS if c[1] is None], key=lambda c: -len(c[2]))
    return [x for _, x in sorted(t91, key=lambda x: -x[0])[:n // 2]] + [("138", c[0], c[2], c[3]) for c in t138[:n - n // 2]]


def bien(fuente, vara, salida) -> bool:
    ls = salida.get("lineas") or []
    if fuente == "91":
        return not M.completo(vara, ls)
    ts = [V.n(f"{x.get('texto')} {x.get('destino') or ''} {x.get('cosa') or ''} "
              f"{'si: ' + str(x['si']) if x.get('si') else ''} {M._nombres(x.get('texto'))}") for x in ls]
    todo = " ".join(ts) + " " + V.n(json.dumps(salida.get("todo"), ensure_ascii=False)) + (
        " SI:" if any(x.get("si") for x in ls) else "")
    return all(M._cumple(x, ts, todo) for x in vara["partes"])


def main() -> None:
    from openai import OpenAI
    from app.config import get_settings
    if not PAGA:
        sys.exit("va con la paga: MARTIN_AUTORIZO_LA_PAGA=<fecha>")
    cli = OpenAI(api_key=PAGA.split()[0], base_url=get_settings().GEMINI_BASE_URL)
    modelo = "gemini-3.1-flash-lite"
    j = lambda e: json.dumps(e, ensure_ascii=False)  # noqa: E731
    consigna = M.LINEAS.format(contar="", temas=", ".join(M.F._temas_de(P.TID)), ej1=j(M.EJ1), ej2=j(M.EJ2))
    casos = muestra(int(_opt("--n", 30)))
    niveles = _opt("--niveles", "sin,minimal,low,medium,high").split(",")
    filas, crudo = {}, []
    for nivel in niveles:
        filas[nivel] = []
        for fuente, cid, msg, vara in casos:
            libro_paga.puede()
            kw = {} if nivel == "sin" else {"reasoning_effort": nivel}
            t0 = time.time()
            try:
                r = cli.chat.completions.create(model=modelo, temperature=0, response_format=M._formato_lineas(False),
                                                messages=[{"role": "system", "content": consigna},
                                                          {"role": "user", "content": f"MENSAJE DEL CLIENTE: {msg}"}], **kw)
            except Exception as e:  # noqa: BLE001
                filas[nivel].append({"id": cid, "error": f"{type(e).__name__}: {str(e)[:100]}"})
                continue
            seg = time.time() - t0
            u = r.usage
            det = getattr(u, "completion_tokens_details", None)
            razona = int(getattr(det, "reasoning_tokens", 0) or 0) if det else 0
            salida = int(u.completion_tokens or 0)
            # El proveedor cobra el razonamiento como salida; si no lo suma a completion_tokens, se suma aca.
            total = int(getattr(u, "total_tokens", 0) or 0)
            cobrada = max(salida, total - int(u.prompt_tokens or 0))
            libro_paga.anotar(modelo, u.prompt_tokens, cobrada)
            s = M.interprete._json(r.choices[0].message.content or "")
            filas[nivel].append({"id": cid, "seg": seg, "entrada": u.prompt_tokens, "salida": salida,
                                 "razona": razona, "cobrada": cobrada, "bien": bien(fuente, vara, s)})
            # Cada llamada se graba al momento: si el tope del dia corta la corrida, lo pagado no se pierde.
            with open(os.path.join(AQUI, "razonar_corrida.jsonl"), "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"nivel": nivel, "id": cid, "salida": s, "uso": filas[nivel][-1]},
                                    ensure_ascii=False) + "\n")
    print(f"\nRAZONAR AL SEPARAR · {len(casos)} mensajes, los de mas cosas del banco y los mas largos del desmenuzado")
    print(f"  {'nivel':8} {'bien':>5} {'seg mediana':>12} {'seg peor':>9} {'entrada':>8} {'salida':>7} {'razona':>7} {'dolares x 1000 msj':>19}")
    for nivel, fs in filas.items():
        ok = [f for f in fs if "error" not in f]
        if not ok:
            print(f"  {nivel:8} sin respuesta: {fs[0].get('error')}")
            continue
        segs = sorted(f["seg"] for f in ok)
        usd = statistics.mean(costo.dolares(f["entrada"], f["cobrada"], modelo) for f in ok) * 1000
        print(f"  {nivel:8} {sum(f['bien'] for f in ok):>3}/{len(ok):<2} {statistics.median(segs):>10.1f}s {segs[-1]:>8.1f}s "
              f"{statistics.mean(f['entrada'] for f in ok):>8.0f} {statistics.mean(f['salida'] for f in ok):>7.0f} "
              f"{statistics.mean(f['razona'] for f in ok):>7.0f} {usd:>18.2f}"
              + (f"  · {len(fs) - len(ok)} con error" if len(ok) < len(fs) else ""))


def deepseek() -> None:
    """La misma prueba con DeepSeek, por orden de Martin del 27-oct: el modelo sin razonar y el que razona, con la consigna
    de las lineas y el JSON pedido en el texto, que DeepSeek no acepta atado. Medido el 27-oct que atado o libre separa
    igual."""
    from openai import OpenAI
    from app.config import get_settings
    if not DEEPSEEK:
        sys.exit("va con la paga: MARTIN_AUTORIZO_LA_PAGA=<fecha>")
    cli = OpenAI(api_key=DEEPSEEK.split()[0], base_url=get_settings().DEEPSEEK_BASE_URL)
    j = lambda e: json.dumps(e, ensure_ascii=False)  # noqa: E731
    consigna = M.LINEAS.format(contar="", temas=", ".join(M.F._temas_de(P.TID)), ej1=j(M.EJ1), ej2=j(M.EJ2)) + M.SALIDA_JSON
    casos = muestra(int(_opt("--n", 30)))
    filas, crudo = {}, []
    for modelo in _opt("--modelos", "deepseek-chat,deepseek-reasoner").split(","):
        filas[modelo] = []
        for fuente, cid, msg, vara in casos:
            libro_paga.puede()
            kw = {"temperature": 0, "response_format": {"type": "json_object"}} if modelo == "deepseek-chat" else {}
            t0 = time.time()
            try:
                r = cli.chat.completions.create(model=modelo, messages=[
                    {"role": "system", "content": consigna}, {"role": "user", "content": f"MENSAJE DEL CLIENTE: {msg}"}], **kw)
            except Exception as e:  # noqa: BLE001
                filas[modelo].append({"id": cid, "error": f"{type(e).__name__}: {str(e)[:100]}"})
                continue
            seg = time.time() - t0
            u = r.usage
            det = getattr(u, "completion_tokens_details", None)
            razona = int(getattr(det, "reasoning_tokens", 0) or 0) if det else 0
            libro_paga.anotar("deepseek-chat", u.prompt_tokens, u.completion_tokens)
            s = M.interprete._json(r.choices[0].message.content or "")
            filas[modelo].append({"id": cid, "seg": seg, "entrada": u.prompt_tokens, "salida": u.completion_tokens,
                                  "razona": razona, "cobrada": u.completion_tokens, "bien": bien(fuente, vara, s)})
            crudo.append({"modelo": modelo, "id": cid, "salida": s, "uso": filas[modelo][-1]})
    with open(os.path.join(AQUI, "razonar_deepseek.jsonl"), "w", encoding="utf-8") as fh:
        for c in crudo:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"\nDEEPSEEK AL SEPARAR · {len(casos)} mensajes, la misma muestra")
    for modelo, fs in filas.items():
        ok = [f for f in fs if "error" not in f]
        if not ok:
            print(f"  {modelo:18} sin respuesta: {fs[0].get('error')}")
            continue
        segs = sorted(f["seg"] for f in ok)
        usd = statistics.mean(costo.dolares(f["entrada"], f["cobrada"], "deepseek-chat") for f in ok) * 1000
        print(f"  {modelo:18} bien {sum(f['bien'] for f in ok)}/{len(ok)} · mediana {statistics.median(segs):.1f}s · peor "
              f"{segs[-1]:.1f}s · entrada {statistics.mean(f['entrada'] for f in ok):.0f} · salida "
              f"{statistics.mean(f['salida'] for f in ok):.0f} · razona {statistics.mean(f['razona'] for f in ok):.0f} · "
              f"{usd:.2f} dolares cada mil" + (f" · {len(fs) - len(ok)} con error" if len(ok) < len(fs) else ""))


if __name__ == "__main__":
    deepseek() if "--deepseek" in ARGS else main()

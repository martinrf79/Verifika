"""Cuatro mensajes complejos pasados a Python por el modelo de produccion, por OpenRouter: libre y con nuestras funciones.
El codigo solo se lee, nunca se ejecuta.

  python3 banco_pruebas/avisos/python_libre.py
"""
import ast, json, os, sys
from openai import OpenAI
RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)
from app.core.flujo import agenda as A
d = json.load(open(os.path.join(RAIZ, "banco_pruebas", "vara_58.json")))
by = {c["id"]: c for c in d["charlas"]}
MSJ = {"K08": by["K08"]["turnos"][0]["texto"], "K21": by["K21"]["turnos"][0]["texto"],
       "C56": by["C56"]["turnos"][0]["texto"], "C26": by["C26"]["turnos"][0]["texto"]}
cli = OpenAI(api_key=os.environ["OPENROUTER_API_KEY"], base_url="https://openrouter.ai/api/v1")
MODELO = "google/gemini-3.1-flash-lite"
LIBRE = ("Pasa este mensaje de un cliente de una tienda online a codigo Python que lo represente tal cual: todo lo que "
         "pide, en su orden, sin resolverlo, sin calcular y sin inventar precios ni datos que el cliente no dijo. "
         "Devolve solo el codigo.\n\nMENSAJE: ")
FUNCS = "\n".join(f"def {k}(**datos): ...  # {v[:150]}" for k, v in A.ACCIONES.items())
CON = ("Pasa este mensaje de un cliente de una tienda online a codigo Python que lo represente tal cual, usando SOLO estas "
       "funciones, una llamada por cada cosa que pide, en su orden. No lo resuelvas, no calcules, no inventes precios ni "
       "datos. Lo que depende de otra llamada va con si=(numero, 'si' o 'no'). Devolve solo las llamadas, una por renglon, "
       "como p1 = funcion(...).\n\n" + FUNCS + "\n\nMENSAJE: ")
gasto = 0
for nombre, consigna in (("LIBRE", LIBRE), ("CON NUESTRAS FUNCIONES", CON)):
    for cid, m in MSJ.items():
        r = cli.chat.completions.create(model=MODELO, temperature=0, messages=[{"role": "user", "content": consigna + m}],
                                        extra_body={"reasoning": {"effort": "minimal"}, "usage": {"include": True}})
        t = r.choices[0].message.content.strip().strip("`").removeprefix("python").strip()
        gasto += float(getattr(r.usage, "cost", 0) or 0)
        try:
            arbol = ast.parse(t); ok = "se lee"
            llamadas = [n.func.id for n in ast.walk(arbol) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
        except SyntaxError as e:
            ok, llamadas = f"NO se lee: {e.msg}", []
        print(f"\n===== {nombre} · {cid} · {ok} · {r.usage.completion_tokens} tokens · llamadas: {llamadas}")
        print(t[:1400])
print(f"\nGASTO: {gasto:.4f} dolares")

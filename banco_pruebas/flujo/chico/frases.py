"""LAS FRASES PARA ENTRENAR AL MODELO CHICO (23-nov-2026). Ver plan.md.

Las reglas salen del catalogo por codigo y sus aceptables de `traductor/catalogo.acept`. Luna solo redacta como lo
diria un cliente: la etiqueta es la de la regla. Cada resultado se graba al momento en frases.jsonl.

    python3 banco_pruebas/flujo/chico/frases.py [n_reglas]
"""
import json, os, random, sys, time
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(AQUI, "..", "traductor")]
sys.dont_write_bytecode = True
import catalogo as K  # noqa: E402

OUT = os.path.join(AQUI, "frases.jsonl")
TOPE = 0.15
PLAT = {"ps4": "PS4", "ps5": "PS5", "xbox": "Xbox", "nintendo_switch": "Nintendo Switch", "macos": "Mac",
        "ios": "iPhone o iPad", "android": "celular Android", "notebook": "notebook", "pc_escritorio": "PC"}


def reglas(n):
    """[(regla, pedido en palabras)], una o dos por modelo al azar, sin repetir, todas con aceptables."""
    rnd, out, vistas = random.Random(105), [], set()
    ks = list(K.MOD)
    rnd.shuffle(ks)
    for k in ks:
        cat, marca, mod = k
        p, c = K.MOD[k][0], K.C[k]
        op = [({"rubro": [cat]}, f"un producto del rubro {cat}"),
              ({"rubro": [cat], "marca": [marca]}, f"{cat} de la marca {marca}"),
              ({"rubro": [cat], "modelos": [mod]}, f"el {cat} {marca} {mod}")]
        con = c["conecta_por"].split("|")
        if c["conecta_por"]:
            ina = K.inal(k)
            op.append(({"rubro": [cat], "inal": ina}, f"{cat} {'inalambrico' if ina else 'con cable'}"))
        pl = [x for x in c["plataformas"].split("|") if x in PLAT]
        if pl:
            x = rnd.choice(pl)
            op.append(({"rubro": [cat], "plat": [x]}, f"{cat} que sirva para {PLAT[x]}"))
        cols = [r["color"] for r in K.MOD[k] if r["color"]]
        if cols:
            col = rnd.choice(cols)
            op.append(({"rubro": [cat], "color": col}, f"{cat} de color {col.lower()}"))
            op.append(({"rubro": [cat], "modelos": [mod], "color": col}, f"el {cat} {marca} {mod} en {col.lower()}"))
        if p["uso_recomendado"].startswith("Gaming"):
            op.append(({"rubro": [cat], "gaming": True}, f"{cat} para jugar, gamer"))
        for r, txt in rnd.sample(op, min(2, len(op))):
            clave = json.dumps(r, sort_keys=True)
            if clave in vistas or not K.acept(r):
                continue
            vistas.add(clave)
            out.append((r, txt))
        if len(out) >= n:
            break
    return out


SIS = ("Escribis como clientes argentinos que mandan un WhatsApp a una tienda de tecnologia. Te doy lo que el cliente "
       "quiere, en palabras tecnicas. Escribi 4 mensajes distintos de clientes distintos pidiendo eso: con jerga, "
       "abreviaturas, errores de tipeo, voseo, a veces con saludo o preguntando precio o stock. No copies las palabras "
       "tecnicas: decilo como lo diria la gente, por ejemplo 'auris', 'mause', 'la play', 'sin cable'. No agregues "
       "pedidos que no esten: ni otros productos, ni otra marca, ni un tope de plata. Responde solo el JSON.")
SCH = {"type": "json_schema", "json_schema": {"name": "f", "strict": True, "schema": {
    "type": "object", "properties": {"mensajes": {"type": "array", "items": {"type": "string"}}},
    "required": ["mensajes"], "additionalProperties": False}}}


def main():
    from openai import OpenAI
    cli = OpenAI(api_key=os.environ["OPENAI_API_KEY"].split()[0], timeout=60, max_retries=2)
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    hechas = {json.loads(x)["pedido"] for x in open(OUT)} if os.path.exists(OUT) else set()
    gasto = sum(json.loads(x)["usd"] for x in open(OUT)) if os.path.exists(OUT) else 0.0
    for r, txt in reglas(n):
        if txt in hechas:
            continue
        if gasto >= TOPE:
            raise SystemExit(f"tope de {TOPE} dolares")
        t = time.time()
        q = cli.chat.completions.create(model="gpt-6-luna", reasoning_effort="none", response_format=SCH,
                                        messages=[{"role": "system", "content": SIS},
                                                  {"role": "user", "content": f"Lo que quiere: {txt}"}])
        u = q.usage
        usd = u.prompt_tokens * 0.10e-6 + u.completion_tokens * 0.50e-6
        gasto += usd
        fila = {"pedido": txt, "regla": r, "acept": sorted(list(x) for x in K.acept(r)),
                "frases": json.loads(q.choices[0].message.content)["mensajes"], "usd": round(usd, 7),
                "seg": round(time.time() - t, 2)}
        with open(OUT, "a", encoding="utf-8") as f:
            f.write(json.dumps(fila, ensure_ascii=False) + "\n")
        print(txt, "|", fila["frases"][0], flush=True)
    print(f"gasto total {gasto:.4f} dolares")


if __name__ == "__main__":
    main()

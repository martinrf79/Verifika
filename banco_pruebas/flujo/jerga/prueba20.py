"""LAS 20 FILAS QUE LUNA SEPARO BIEN Y TRADUJO MAL, CON LA BASE DE JERGA COMO AYUDA (28-nov-2026).

Orden de Martin: una prueba chica del hibrido. La fila es la que escribio Luna al separar, no el tramo de la etiqueta.
Para cada fila: lo que el codigo da por claro en la base de jerga, mas los cinco candidatos de los embeddings, con la
expresion que trajo a cada uno; Luna elige uno, vago o ninguno. Dos modos: pensando bajo y sin pensar. Latencia y costo
de cada paso. El juicio es a mano, leyendo cada salida: no hay respuesta escrita de antemano.

Las 20 salen de lo grabado de Luna, `primeros/luna.jsonl`, `primeros/luna_reales.jsonl` y `examen/luna_b.jsonl`: 13
rubros sin marcar o mal marcados y 7 condiciones sin traducir. El contexto es el rubro que el cliente dijo en otra fila.

    python3 prueba20.py [--correr]
"""
import json, os, sys, time

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(AQUI, "..", "..", ".."))
sys.path[:0] = [AQUI, REPO]
import nexo as NX  # noqa: E402
import elegir as E  # noqa: E402

GRABADO = os.path.join(AQUI, "prueba20.jsonl")

# (id, mensaje del cliente, la fila que escribio Luna, rubro de otra fila como contexto)
CASOS = [
    ("S027", "fuente y gabinete para armar pc, 650w", "gabinete", ""),
    ("S271", "quiero esa cosa para que se vea mas grande la pantalla de la compu",
     "quiero esa cosa para que se vea más grande la pantalla de la compu", ""),
    ("S272", "una cosita para pasar las fotos del celu a la compu y guardarlas",
     "una cosita para pasar las fotos del celu a la compu y guardarlas", ""),
    ("S280", "una pantalla tactil portatil para leer y ver series", "una pantalla táctil portátil", ""),
    ("S300", "lo que imprime, hacen factura?", "lo que imprime", ""),
    ("prod:367", "kiero la tablet esa de sansun, la s9 fe creo... si le meto un pendrive kingston de 4tb, c vuelve una compu cuantica?",
     "si le meto un pendrive Kingston de 4 TB, se vuelve una compu cuántica?", ""),
    ("prod:473", "Bueno, me calme. Si en vez de devolverlo te lo cambio por un disco SSD Samsung 980 2TB, me haces el descuento?",
     "te lo cambio por un disco SSD Samsung 980 2TB", ""),
    ("prod:483", "ola kiero una compu o algo pa jugar tenes el moderbor asus tuf 650 i un prosesador inter cor i5",
     "Hola, quiero una compu o algo para jugar", ""),
    ("prod:676", "Dame precio de 7 articulos 2 notebooks 1 microfono y los demas serian memorias", "y los demás serían memorias", ""),
    ("prod:772", "Necesito notebook o tablet cual es mas eco", "tablet", ""),
    ("cosecha:796", "Dame precio de aparato cuadrado con teclas", "de aparato cuadrado con teclas", ""),
    ("cosecha:841", "decime la memoria mas cara que tengas, y la mas barata", "decime la memoria", ""),
    ("cosecha:885", "necesito una compu para mi hijo de 8 años, para que juegue y haga la tarea, que no sea muy cara",
     "necesito una compu", ""),
    ("S049", "hola, un pendrive grande para pasar fotos", "grande para pasar fotos", "almacenamiento externo"),
    ("S061", "mouse ineal logi baratp", "ineal", "mouse"),
    ("S271b", "quiero esa cosa para que se vea mas grande la pantalla de la compu", "para que se vea más grande", "monitor"),
    ("prod:312", "quiero parlantes de esos que se escuchan de la otra cuadra antes me compre unos y no se escuchaban nada",
     "de esos que se escuchan de la otra cuadra", "parlante"),
    ("S092", "busco auriculares para mi hijo que juega al fortnite, nada muy caro", "para mi hijo que juega al Fortnite",
     "auriculares"),
    ("cosecha:815", "Hola, tienen garantia en los teclados mecanicos? y cual me conviene para escribir mucho todos los dias",
     "para escribir mucho todos los días", "teclado"),
    ("cosecha:885b", "necesito una compu para mi hijo de 8 años, para que juegue y haga la tarea, que no sea muy cara",
     "para que juegue y haga la tarea", "notebook"),
]


def candidatos(ix, fila, ctx):
    """El codigo primero: lo que la base da por claro va arriba. Despues los embeddings, sin repetir."""
    t0 = time.time()
    r = NX.base().resolver(fila)
    claros = [x["concepto"] for x in r.get("conceptos", [])] if r["veredicto"] == "claro" else []
    t1 = time.time()
    emb = ix.candidatos(fila, 5, contexto=ctx)
    t2 = time.time()
    out = [{"concepto": c, "expresion": "codigo: " + next(x["expresion"] for x in r["conceptos"] if x["concepto"] == c)}
           for c in claros]
    out += [x for x in emb if x["concepto"] not in claros]
    return out[:6], round(t1 - t0, 3), round(t2 - t1, 2)


def correr():
    import vectores as V
    ix = V.Indice()
    hechos = {(r["id"], r["motor"]) for r in map(json.loads, open(GRABADO))} if os.path.exists(GRABADO) else set()
    with open(GRABADO, "a") as f:
        for cid, msg, fila, ctx in CASOS:
            cands, seg_cod, seg_emb = candidatos(ix, fila, ctx)
            for motor in ("luna-bajo", "luna-nada"):
                if (cid, motor) in hechos:
                    continue
                el, uso = E.pedir(motor, msg, fila, cands, con_expresion=True)
                f.write(json.dumps({"id": cid, "motor": motor, "fila": fila, "contexto": ctx,
                                    "candidatos": [(c["concepto"], c["expresion"]) for c in cands], "elegido": el,
                                    "seg_codigo": seg_cod, "seg_embeddings": seg_emb, **uso}, ensure_ascii=False) + "\n")
                f.flush()


def ver():
    rs = [json.loads(l) for l in open(GRABADO)]
    for cid, _m, fila, _c in CASOS:
        a = {r["motor"]: r for r in rs if r["id"] == cid}
        if not a:
            continue
        b = a.get("luna-bajo", {})
        n = a.get("luna-nada", {})
        print(f"{cid:13} {fila[:48]!r:52} bajo: {b.get('elegido')} {b.get('seg')} s | nada: {n.get('elegido')} {n.get('seg')} s")
        print(f"{'':13} candidatos: {[c for c, _ in b.get('candidatos', [])]}")
    for m in ("luna-bajo", "luna-nada"):
        x = [r for r in rs if r["motor"] == m]
        s = sorted(r["seg"] for r in x)
        e = sorted(r["seg_embeddings"] for r in x)
        if s:
            print(f"{m}: {len(x)} llamadas, Luna mediana {s[len(s) // 2]} s, maximo {s[-1]} s; embeddings mediana "
                  f"{e[len(e) // 2]} s; costo {sum(r['dolares'] for r in x) * 100:.3f} centavos")


if __name__ == "__main__":
    if "--correr" in sys.argv:
        correr()
    ver()

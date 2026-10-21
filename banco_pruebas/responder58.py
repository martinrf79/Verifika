"""EL MODELO RESPONDE SOLO — las 58 y las K con la fuente entera en el contexto, sin codigo en el medio (21-oct-2026, orden de Martin).

POR QUE EXISTE. `traduccion58.py` mide al modelo traduciendo para el codigo. Esto mide lo otro: si un modelo con toda la
fuente de la tienda delante contesta bien de cabeza. Si lo hace, el limite no es el modelo sino como le damos la
informacion.

  la fuente    el catalogo compacto, las fichas tecnicas, la compatibilidad, las politicas y las tarifas de envio por
               provincia, armado desde `data/clientes/verifika_prod/` y la tabla de envio que usa la calculadora.
               Va en el sistema con cache: se cobra entera una vez y despues al diez por ciento.
  la charla    cada charla de las 58 y las K, turno por turno, con las respuestas del propio modelo como historial,
               en cada una de las cinco formas de `traduccion58.py`. Una vez, con el razonamiento apagado.
  la nota      las mismas casillas de `vara_58.json` sobre lo que contesta, turno por turno.

Es REANUDABLE: cada charla y forma se anota en `responder58_corridas.jsonl`; lo ya corrido se saltea. El gasto exacto lo
devuelve OpenRouter en cada llamada, se anota en `traduccion58_gasto.jsonl` como "responder" y corta en TOPE.

  python3 -m banco_pruebas.responder58 --parte 1/4
  python3 -m banco_pruebas.responder58 --informe
"""
import csv
import json
import os
import re
import sys
import zlib

AQUI = os.path.dirname(os.path.abspath(__file__))
CORRIDAS = os.path.join(AQUI, "responder58_corridas.jsonl")
MODELO = "anthropic/claude-haiku-5.5"
TOPE = 3.90  # el saldo de OpenRouter, orden de Martin del 21-oct: correrla completa aunque se agote
FUENTE_DIR = os.path.join(os.path.dirname(AQUI), "data", "clientes", "verifika_prod")

SISTEMA = """Sos el vendedor de Verifika Tech, una tienda online de tecnologia de Argentina, por WhatsApp. Contesta en
español rioplatense, con voseo, corto y claro.
Usa SOLO los datos de la FUENTE DE LA TIENDA: precios, stock, colores, fichas, compatibilidad, politicas y tarifas de
envio. Si un dato no esta, deci que no lo tenes: nunca lo inventes. Hace las cuentas que pida el cliente con los precios
de la fuente: subtotal, envio por destino, descuentos, total y pago dividido. Si algo es ambiguo, pregunta. Para
reservar pedi solo el nombre."""


def fuente() -> str:
    from app.core import fuente as F
    from app.storage.firestore_client import get_all_faq
    faq = get_all_faq(tienda_id="verifika_prod")
    k = ["id", "nombre", "precio_ars", "stock", "color", "garantia_meses", "origen", "caracteristicas_extra"]
    cat = "\n".join("|".join(p[x] for x in k) for p in csv.DictReader(open(os.path.join(FUENTE_DIR, "productos.csv"))))
    specs = open(os.path.join(FUENTE_DIR, "specs_por_modelo.csv")).read()
    comp = "\n".join("|".join(r[x] for x in ("marca", "modelo", "conecta_por", "plataformas", "requiere", "no_compatible"))
                     for r in csv.DictReader(open(os.path.join(FUENTE_DIR, "compatibilidad.csv"))))
    pol = "\n".join(f"- {t}: {v.get('respuesta')}" for t, v in faq.items())
    tabla = "\n".join(f"- {p.replace('_', ' ')}: ${m}" for p, m in sorted(F._tabla_interior("verifika_prod").items()))
    return ("FUENTE DE LA TIENDA\n\nCATALOGO (id|nombre|precio en pesos|stock|color|garantia en meses|origen|extra):\n" + cat
            + "\n\nFICHAS TECNICAS:\n" + specs
            + "\n\nCOMPATIBILIDAD (marca|modelo|se conecta por|plataformas|requiere|no compatible con):\n" + comp
            + "\n\nPOLITICAS:\n" + pol + "\n\nENVIOS: " + F._tarifas(faq, "verifika_prod")
            + "\nTarifa al interior por provincia:\n" + tabla)


def _gastado() -> float:
    from banco_pruebas.traduccion58 import gastado_otro
    return gastado_otro("responder")


def _llamar(cli, sistema: str, mensajes: list) -> str:
    from banco_pruebas.traduccion58 import GASTO
    if _gastado() >= TOPE:
        raise RuntimeError(f"tope de {TOPE} dolares")
    r = cli.chat.completions.create(
        model=MODELO, temperature=0, max_tokens=1200,
        messages=[{"role": "system", "content": [{"type": "text", "text": sistema,
                                                  "cache_control": {"type": "ephemeral"}}]}] + mensajes,
        extra_body={"reasoning": {"effort": "none"}, "usage": {"include": True}})
    u = r.usage
    detalle = getattr(u, "prompt_tokens_details", None)
    cache = int(getattr(detalle, "cached_tokens", 0) or 0) if detalle else 0
    costo = float(getattr(u, "cost", 0) or 0)
    with open(GASTO, "a", encoding="utf-8") as f:
        f.write(json.dumps({"proveedor": "responder", "entrada": u.prompt_tokens, "cache": cache,
                            "salida": u.completion_tokens, "dolares": round(costo, 6)}) + "\n")
    return r.choices[0].message.content or ""


def _hechas() -> set:
    if not os.path.exists(CORRIDAS):
        return set()
    return {(x["charla"], x["forma"]) for x in map(json.loads, open(CORRIDAS, encoding="utf-8"))}


def correr(parte: int, partes: int) -> bool:
    from openai import OpenAI
    from banco_pruebas import cableado58 as R
    from banco_pruebas import clon_produccion as C
    from banco_pruebas import traduccion58 as T
    from banco_pruebas.sonda_charlas import nota_casilla
    C.preparar_entorno()
    C.instalar()
    cli = OpenAI(api_key=os.environ["OPENROUTER_API_KEY"], base_url="https://openrouter.ai/api/v1")
    sistema = SISTEMA + "\n\n" + fuente()
    hechas, protegidas = _hechas(), T._protegidas()
    trabajo = [(c, f) for c in R.charlas() for f in T.FORMAS
               if (c["id"], f) not in hechas and zlib.crc32(f"{c['id']}{f}".encode()) % partes == parte - 1]
    print(f"[parte {parte}/{partes}] faltan {len(trabajo)} charlas", flush=True)
    for charla, forma in trabajo:
        mensajes, respuestas, turnos = [], [], []
        try:
            for k, t in enumerate(charla["turnos"]):
                texto = T.formas_de(charla["id"], k, t["texto"], protegidas)[forma]
                mensajes.append({"role": "user", "content": texto})
                r = _llamar(cli, sistema, mensajes)
                mensajes.append({"role": "assistant", "content": r})
                respuestas.append(r)
                malas = [c["n"] for c in t["casillas"] if nota_casilla(c, [], r, respuestas) is not True]
                turnos.append({"texto": texto, "respuesta": r, "bien": not malas, "malas": malas})
        except Exception as e:  # noqa: BLE001 — la charla queda sin anotar y se repite entera
            print(f"[parte {parte}] {charla['id']} {forma}: se corta, {type(e).__name__}: {str(e)[:160]}", flush=True)
            return False
        with open(CORRIDAS, "a", encoding="utf-8") as out:
            out.write(json.dumps({"charla": charla["id"], "forma": forma, "modelo": MODELO, "turnos": turnos},
                                 ensure_ascii=False) + "\n")
        print(f"[parte {parte}] {charla['id']} {forma}: {sum(x['bien'] for x in turnos)} de {len(turnos)} turnos bien",
              flush=True)
    return True


def informe() -> None:
    from banco_pruebas import clon_produccion as C
    from banco_pruebas.traduccion58 import FORMAS, _leidas, _huella
    C.preparar_entorno()
    C.instalar()
    filas = list(map(json.loads, open(CORRIDAS, encoding="utf-8"))) if os.path.exists(CORRIDAS) else []
    huella, trad = _huella(), _leidas()
    print(f"\nEL MODELO RESPONDE SOLO, {MODELO}, con la fuente entera · gastado {_gastado():.2f} dolares")
    for forma in FORMAS:
        ts = [(x["charla"], k, t["bien"]) for x in filas if x["forma"] == forma for k, t in enumerate(x["turnos"])]
        bot = sum(1 for ch, k, _ in ts if trad.get((huella, ch, k, forma, 0, "gemini"), {}).get("bien"))
        print(f"  {forma:10} responde solo {sum(b for *_, b in ts)} · el bot con Gemini {bot} · de {len(ts)} turnos")


def main(argv: list) -> int:
    sys.path.insert(0, os.path.dirname(AQUI))
    if "--informe" not in argv:
        parte, partes = 1, 1
        if "--parte" in argv:
            parte, partes = map(int, argv[argv.index("--parte") + 1].split("/"))
        if not correr(parte, partes):
            return 2
    informe()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

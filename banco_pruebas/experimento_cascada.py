"""
EXPERIMENTO (banco, NO produccion) — cascada de 3 capas, idea de Martin 9-jul.

Hipotesis: cuando todo estaba roto, lo unico que dio un respiro fue DARLE
LIBERTAD al modelo. El valor comercial del bot es que sepa VENDER, y eso el
codigo rigido no lo hace. Se prueba una arquitectura distinta a la viva:

  Capa 1  DeepSeek LIBRE (interprete + solver 2 en 1): un prompt vendedor,
          centrado en la fuente de verdad que se le pasa en contexto. VA a
          alucinar algun dato, se asume.
  Capa 2  GPT-4 mini FILTRO: recibe el borrador de DeepSeek + la MISMA fuente
          de verdad y corrige todo numero/producto que no coincida, saca lo que
          no se puede verificar, y CONSERVA la prosa vendedora.
  Capa 3  Verificador de codigo (el JUEZ reusa los MISMOS detectores de
          produccion): mide cuanta mentira de dato queda DESPUES del filtro.

No toca el camino vivo ni ningun flag. Solo mide. Uso:
  python3 banco_pruebas/experimento_cascada.py [guion1.txt guion2.txt ...]
Sin argumentos corre la charla real compuesta de Martin (la que se rompio hoy).
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from banco_pruebas.sim_firestore import install
from banco_pruebas.juez import juzgar

from openai import OpenAI

_DS_MODEL = os.getenv("EXP_DS_MODEL", "deepseek-chat")
_FILTRO_MODEL = os.getenv("EXP_FILTRO_MODEL", "gpt-4o-mini")


def _cli_deepseek() -> OpenAI:
    return OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"],
                  base_url="https://api.deepseek.com/v1", timeout=60)


def _cli_openai() -> OpenAI:
    return OpenAI(api_key=os.environ["OPENAI_API_KEY"], timeout=60)


def _contexto_fuente(mensaje: str, tienda_id: str) -> str:
    """La FUENTE DE VERDAD que ven las dos capas: productos relevantes con
    precio y stock REALES + la politica curada (envio, pagos, cuotas...)."""
    from app.storage.firestore_client import get_all_products, get_all_faq, get_categories
    from app.core.guia_pedido import opciones_por_categoria
    import unicodedata

    def _n(s):
        s = unicodedata.normalize("NFKD", str(s or "").lower())
        return "".join(c for c in s if not unicodedata.combining(c))

    m = _n(mensaje)
    cats = [c for c in (get_categories(tienda_id=tienda_id) or [])
            if _n(c).rstrip("s") in m or _n(c) in m]
    lineas = []
    vistos = set()
    if cats:
        for c in cats:
            for p in opciones_por_categoria(c, tienda_id, k=8):
                if p["id"] not in vistos:
                    vistos.add(p["id"])
                    lineas.append(
                        f"- {p['nombre']} | ${int(p['precio_ars']):,} | "
                        f"stock {p.get('stock', 0)} | cat {p.get('categoria')}")
    if not lineas:
        from app.storage.search import hybrid_search_relajada
        for p in (hybrid_search_relajada(query=mensaje, top_n=20,
                                         tienda_id=tienda_id).get("productos") or []):
            if p.get("precio_ars") is not None:
                lineas.append(
                    f"- {p['nombre']} | ${int(p['precio_ars']):,} | "
                    f"stock {p.get('stock', 0)} | cat {p.get('categoria')}")
    faq = get_all_faq(tienda_id=tienda_id) or {}
    pol = []
    for tema, d in faq.items():
        txt = (d.get("respuesta_curada") or d.get("respuesta") or "").strip()
        if txt:
            pol.append(f"- {tema}: {txt}")
    return ("CATALOGO (unica fuente de precios, stock e identidad; no inventar "
            "ni un producto ni un precio fuera de esto):\n"
            + ("\n".join(lineas) if lineas else "(sin coincidencias)")
            + "\n\nPOLITICA DE LA TIENDA (envio, pagos, cuotas, garantia):\n"
            + "\n".join(pol[:44]))


_PROMPT_DS = """Sos el mejor vendedor de Verifika, una tienda de tecnologia argentina. Hablas en voseo, calido, directo, sin vueltas. Tu trabajo es VENDER y hacer facil la compra.

Reglas de oro:
- Solo podes nombrar productos, precios y stock que esten en el bloque CATALOGO. Jamas inventes un producto, un precio ni un stock.
- Envio, pagos, cuotas, garantia: solo lo que diga el bloque POLITICA.
- Si el cliente pide varias cosas, atendelas todas en el mismo mensaje.
- Si arma un pedido, sumalo y dale el total. Si pide lo mas barato, ofrecele lo mas barato con stock.
- No prometas dias exactos de entrega ni retiro en local si la politica no lo dice.
- Se breve y vendedor. Cerra siempre con una pregunta que empuje la compra."""

_PROMPT_FILTRO = """Sos un CORRECTOR de datos. Recibis un borrador de respuesta de un vendedor y la FUENTE DE VERDAD (catalogo + politica). Tu unica tarea: devolver el mismo mensaje pero con TODOS los datos correctos.

- Todo precio, stock o nombre de producto DEBE coincidir exacto con el CATALOGO. Si el borrador puso un numero o producto que no esta o no coincide, corregilo al real o sacalo.
- Todo dato de envio, pago, cuotas o garantia DEBE coincidir con POLITICA. Si no se puede verificar, sacalo.
- Conserva el tono vendedor y la estructura. No agregues datos nuevos. No expliques lo que corregiste.
- Devolve SOLO el mensaje final para el cliente."""


def _ds_libre(cli, mensaje, historial, contexto):
    msgs = [{"role": "system", "content": _PROMPT_DS},
            {"role": "system", "content": contexto}]
    msgs += historial
    msgs.append({"role": "user", "content": mensaje})
    r = cli.chat.completions.create(model=_DS_MODEL, messages=msgs,
                                    temperature=0.5, max_tokens=700)
    return (r.choices[0].message.content or "").strip()


def _filtro(cli, borrador, contexto):
    r = cli.chat.completions.create(
        model=_FILTRO_MODEL, temperature=0,
        messages=[{"role": "system", "content": _PROMPT_FILTRO},
                  {"role": "user", "content":
                   f"{contexto}\n\nBORRADOR DEL VENDEDOR:\n{borrador}"}],
        max_tokens=700)
    return (r.choices[0].message.content or "").strip()


def correr(guiones):
    install()
    ds, oa = _cli_deepseek(), _cli_openai()
    tot_raw, tot_filt, turnos = 0, 0, 0
    for g in guiones:
        mensajes = [l for l in Path(g).read_text(encoding="utf-8").splitlines()
                    if l.strip() and not l.strip().startswith("#")]
        print(f"\n{'='*70}\nGUION: {Path(g).name}\n{'='*70}")
        hist = []
        for msg in mensajes:
            turnos += 1
            ctx = _contexto_fuente(msg, "verifika_prod")
            borrador = _ds_libre(ds, msg, hist, ctx)
            final = _filtro(oa, borrador, ctx)
            v_raw = juzgar(borrador)
            v_filt = juzgar(final)
            tot_raw += len(v_raw)
            tot_filt += len(v_filt)
            print(f"\n--- CLIENTE: {msg[:90]}")
            print(f"[DeepSeek libre] violaciones={len(v_raw)} {v_raw if v_raw else ''}")
            print(f"[GPT-4 mini filtro] violaciones={len(v_filt)} {v_filt if v_filt else ''}")
            print(f"RESPUESTA FINAL:\n{final}")
            hist.append({"role": "user", "content": msg})
            hist.append({"role": "assistant", "content": final})
            hist = hist[-10:]
    print(f"\n{'='*70}\nRESUMEN: {turnos} turnos | "
          f"violaciones DeepSeek crudo={tot_raw} | "
          f"tras filtro GPT-4 mini={tot_filt}")
    return tot_filt


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        args = [str(Path(__file__).resolve().parent / "guiones"
                     / "26_experimento_compuesto.txt")]
    correr(args)

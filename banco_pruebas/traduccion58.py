"""LO QUE EL MODELO PUEDE TRADUCIR — cada turno de las 58 y las K, en cinco formas y tres veces (21-oct-2026, orden de Martin).

POR QUE EXISTE. Para decidir hasta donde responde el sistema y que pasa a repregunta directa hace falta un numero
confiable de lo que el modelo de produccion traduce bien, con la consigna y el control de hoy, y dicho de muchas formas.

  la base      con las agendas a mano, `cableado58.py` da 65 de 65: el codigo responde bien todo lo traducido bien.
               Entonces cada falla de aca es de la traduccion.
  el turno     se mide uno por vez. Los turnos anteriores de la charla van con la agenda a mano, asi la memoria es la
               correcta, y el turno medido lo traduce el modelo real: `interpretar` con su devuelta y `elegir`.
               `vender` queda apagado, porque contesta y no traduce: lo que no se resolvio queda con la repregunta.
               `explicar` devuelve lo escrito a mano: es saber general, no traduccion.
  las formas   original; `plano`, sin mayusculas, tildes ni signos; `whatsapp`, plano con abreviaturas y un error de
               tipeo; `redactada` y `coloquial`, escritas a mano en `traduccion58_formas.py` antes de correr.
  la nota      las casillas de `vara_58.json` sobre lo que recibe el cliente en ese turno. Un caso vale si sale bien las
               tres veces. Se guarda la agenda del modelo para comparar con la de `agendas58.py`.

Es REANUDABLE: cada corrida se anota en `traduccion58_corridas.jsonl` con la huella de la consigna, y lo ya corrido se
saltea. Si la cuota se agota, se corta limpio y se sigue con el mismo comando, con la gratis otro dia o con la paga.

  python3 -m banco_pruebas.traduccion58                    todo, con la clave gratis
  python3 -m banco_pruebas.traduccion58 --parte 1/3        un tercio, para correr en paralelo
  python3 -m banco_pruebas.traduccion58 C27 K10            solo esas charlas
  python3 -m banco_pruebas.traduccion58 --informe          solo el informe de lo ya corrido
"""
import asyncio
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
import zlib

AQUI = os.path.dirname(os.path.abspath(__file__))
CORRIDAS = os.path.join(AQUI, "traduccion58_corridas.jsonl")
FORMAS = ("original", "plano", "whatsapp", "redactada", "coloquial")
REPS = 3

# OTROS MODELOS, para comparar con el de produccion (21-oct, orden de Martin): una sola vez, por su propia puerta, con
# su gasto anotado en GASTO y un tope por proveedor. `TRAD_PROVEEDOR=deepseek` o `haiku`; sin eso, Gemini.
PROVEEDORES = {"deepseek": ("DEEPSEEK_API_KEY", "https://api.deepseek.com", "deepseek-chat"),
               "haiku": ("OPENROUTER_API_KEY", "https://openrouter.ai/api/v1", "anthropic/claude-haiku-5.5"),
               "luna": ("OPENROUTER_API_KEY", "https://openrouter.ai/api/v1", "openai/gpt-5.6-luna"),
               "mini54": ("OPENROUTER_API_KEY", "https://openrouter.ai/api/v1", "openai/gpt-5.4-mini"),
               "terra": ("OPENROUTER_API_KEY", "https://openrouter.ai/api/v1", "openai/gpt-5.6-terra"),
               "gemini_or": ("OPENROUTER_API_KEY", "https://openrouter.ai/api/v1", "google/gemini-3.1-flash-lite"),
               "minimax_gratis": ("OPENROUTER_API_KEY", "https://openrouter.ai/api/v1", "minimax/minimax-m3.1-flash:free")}

# LA INFORMACION IDEAL, por clase (21-oct): lo mismo que recibe el modelo en produccion, con tres cambios que el codigo
# podria hacer solo. Si con esto traduce bien, el arreglo es que el marcador arme esto; si no, es el modelo.
#   destinos   cada localidad del mensaje se marca como destino de envio, con `envio.clasificar_provincia`.
#   repiten    fuera las pistas de temas que repiten una accion: el costo de un envio es la accion envio.
#   producto   con un producto nombrado, la pista de garantia se va: la garantia de un producto es un dato suyo.
REPITEN = {"costo_envio", "envios", "plazo_envio", "stock_disponibilidad", "especificaciones", "compatibilidad",
           "garantia_como_usar"}


def ideal() -> bool:
    return os.environ.get("TRAD_IDEAL", "") in ("1", "tabla")


def solo_tabla() -> bool:
    """La mejora va solo en la tabla de pistas, que es por mensaje: la consigna queda igual y lo que no cambia de
    entrada no puede cambiar de traduccion. Se corre solo donde la tabla cambia."""
    return os.environ.get("TRAD_IDEAL", "") == "tabla"


def _tabla_ideal(mensaje: str, tienda_id: str) -> str:
    from app.core.envio import clasificar_provincia
    from app.core.flujo import marcador
    marcas = marcador.marcar(mensaje, tienda_id)
    hay_producto = any(e.startswith("el producto") for _, e in marcas)
    out = []
    for d, e in marcas:
        temas = re.findall(r"el tema ([a-z_]+(?: o [a-z_]+)*)", e)
        if temas:
            quedan = [t for t in temas[0].split(" o ") if t not in REPITEN and not (hay_producto and t == "garantia")]
            if not quedan:
                continue
            e = "SOLO si pregunta una regla de la tienda, el tema " + " o ".join(quedan)
        out.append(f'- "{d}" es {e}')
    ws = re.findall(r"[A-Za-zÁÉÍÓÚáéíóúñÑ]+", mensaje)
    usadas = set()
    for n in (1, 2, 3):  # el tramo mas corto que nombra una localidad, sin pisar uno ya marcado
        for i in range(len(ws) - n + 1):
            if usadas & set(range(i, i + n)):
                continue
            frase = " ".join(ws[i:i + n])
            if len(frase) > 3 and clasificar_provincia(frase):
                usadas |= set(range(i, i + n))
                out.append(f'- "{frase}" es una localidad: un destino de envio')
    if not out:
        return "LO QUE EL CODIGO RECONOCIO EN EL MENSAJE: nada."
    return "LO QUE EL CODIGO RECONOCIO EN EL MENSAJE:\n" + "\n".join(out)


def marcador_tabla(texto: str) -> str:
    from app.core.flujo import marcador
    return marcador.tabla(texto, "verifika_prod")


def instalar_ideal() -> None:
    from app.core.flujo import interprete

    def mensajes(mensaje, historial, estado, tienda_id):
        temas = ", ".join(t for t in __import__("app.core.agente", fromlist=["indice"]).indice(tienda_id)["temas"]
                          if t not in REPITEN)
        sistema = interprete.consigna(tienda_id) if solo_tabla() else \
            re.sub(r"TEMAS: .*", "TEMAS: " + temas, interprete.consigna(tienda_id), count=1)
        return [{"role": "system", "content": sistema},
                {"role": "user", "content": interprete.libreta(estado, historial, tienda_id) + "\n"
                 + _tabla_ideal(mensaje, tienda_id) + f"\nULTIMO MENSAJE: {mensaje}"}]
    interprete.mensajes = mensajes
GASTO = os.path.join(AQUI, "traduccion58_gasto.jsonl")
TOPE_OTRO = float(os.environ.get("TRAD_TOPE", "2.00"))


def proveedor() -> str:
    return os.environ.get("TRAD_PROVEEDOR", "gemini")


def gastado_otro(nombre: str) -> float:
    if not os.path.exists(GASTO):
        return 0.0
    return sum(json.loads(x)["dolares"] for x in open(GASTO, encoding="utf-8") if json.loads(x)["proveedor"] == nombre)


def _puerta_otra(nombre: str):
    """El cliente del otro proveedor, con cada llamada anotada y el tope mirado antes."""
    from openai import OpenAI
    from banco_pruebas import costo
    env, url, modelo = PROVEEDORES[nombre]
    cli = OpenAI(api_key=os.environ[env], base_url=url)
    crear = cli.chat.completions.create

    def create(*a, **k):
        if gastado_otro(nombre) >= TOPE_OTRO:
            raise RuntimeError(f"tope de {TOPE_OTRO} dolares para {nombre}")
        k["model"] = modelo
        if url.startswith("https://openrouter.ai"):
            # Sin razonamiento, como Gemini al minimo, y con el costo real que cobra OpenRouter, no el de la tabla.
            # Los gratis de OpenRouter no dejan apagar el razonamiento: va al minimo que aceptan.
            k["extra_body"] = {"reasoning": {"effort": "minimal" if modelo.startswith("google/") else
                                             "low" if modelo.endswith(":free") else "none"},
                               "usage": {"include": True}}
        r = crear(*a, **k)
        u = getattr(r, "usage", None)
        e, sa = int(getattr(u, "prompt_tokens", 0) or 0), int(getattr(u, "completion_tokens", 0) or 0)
        with open(GASTO, "a", encoding="utf-8") as f:
            f.write(json.dumps({"proveedor": nombre, "entrada": e, "salida": sa,
                                "dolares": round(float(getattr(u, "cost", 0) or 0) or costo.dolares(e, sa, modelo), 6)}) + "\n")
        return r
    cli.chat.completions.create = create
    return cli

_ABREVIA = {"que": "q", "porque": "xq", "tambien": "tmb", "auriculares": "auris", "mensaje": "msj", "favor": "fa"}


def plano(t: str) -> str:
    t = "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[¿?¡!.,;:]", " ", t)).strip()


def whatsapp(t: str, protegidas: set) -> str:
    """Plano, con abreviaturas de WhatsApp y un error de tipeo: dos letras cambiadas en la primera palabra larga que no
    es de un producto ni un nombre propio."""
    propias = {plano(w) for w in t.split() if w[:1].isupper() or re.search(r"\d", w)}
    ws = plano(t).split()
    out, tipeo = [], False
    for i, w in enumerate(ws):
        if w == "por" and (i + 1 >= len(ws) or ws[i + 1] != "ciento"):
            w = "x"
        w = _ABREVIA.get(w, w)
        if not tipeo and len(w) >= 6 and w.isalpha() and w not in propias and w not in protegidas:
            w, tipeo = w[:2] + w[3] + w[2] + w[4:], True
        out.append(w)
    return " ".join(out)


def _protegidas() -> set:
    from app.core.flujo import catalogo as K
    return {w for p in K.productos("verifika_prod") for w in plano(f"{p.get('marca')} {p.get('modelo')}").split()}


def formas_de(charla: str, turno: int, texto: str, protegidas: set) -> dict:
    from banco_pruebas.traduccion58_formas import FORMAS as A_MANO
    redactada, coloquial = A_MANO[f"{charla}|{turno}"]
    return {"original": texto, "plano": plano(texto), "whatsapp": whatsapp(texto, protegidas),
            "redactada": redactada, "coloquial": coloquial}


def _huella() -> str:
    from app.core.flujo import interprete
    return hashlib.sha1(interprete.consigna("verifika_prod").encode()).hexdigest()[:10]


def _leidas() -> dict:
    out = {}
    if os.path.exists(CORRIDAS):
        for linea in open(CORRIDAS, encoding="utf-8"):
            x = json.loads(linea)
            out[(x["huella"], x["charla"], x["turno"], x["forma"], x["rep"], x.get("modelo", "gemini"))] = x
    return out


def _acciones(agenda) -> list:
    from app.core.flujo import agenda as A
    return sorted(str(p.get("accion")) for p in A.preguntas(agenda or {}))


def _explicacion(agenda: dict, explicar: dict) -> str:
    from app.core.flujo import agenda as A
    return next((explicar.get(p.get("pregunta"), "") for p in A.preguntas(agenda) if p.get("accion") == "explicar"), "")


def correr(parte: int, partes: int, solo: list = None, turnos: set = None) -> bool:
    """Corre lo que falta. Devuelve False si el modelo dejo de contestar."""
    from banco_pruebas import cableado58 as R
    from banco_pruebas import clon_produccion as C
    C.preparar_entorno()
    C.instalar()  # antes de tomar la puerta: con la paga, `instalar` la envuelve con el libro y su tope diario
    from app.core import llm_reintento
    from app.core.flujo import interprete
    puerta, real_interpretar, real_elegir = llm_reintento._cliente, interprete.interpretar, interprete.elegir
    from banco_pruebas.agendas58 import AGENDAS, EXPLICAR
    from banco_pruebas.sonda_charlas import nota_casilla
    it = R.instalar()
    llm_reintento._cliente = puerta  # el modelo real: lo que se mide es su traduccion
    nombre = proveedor() + ("+tabla" if solo_tabla() else "+ideal" if ideal() else "")
    reps = REPS
    if ideal():
        instalar_ideal()
    base = nombre.split("+")[0]
    if base != "gemini":
        otra = _puerta_otra(base)
        llm_reintento._cliente, llm_reintento._modelo, reps = (lambda: otra), (lambda: PROVEEDORES[base][2]), 1
    if ideal():
        reps = 1
    elegir_mano = it.elegir
    huella, hechas, protegidas = _huella(), _leidas(), _protegidas()
    trabajo = []
    for rep in range(reps):
        for charla in R.charlas():
            if solo and charla["id"] not in solo:
                continue
            for k, t in enumerate(charla["turnos"]):
                if turnos and (charla["id"], k) not in turnos:
                    continue
                for forma, texto in formas_de(charla["id"], k, t["texto"], protegidas).items():
                    if solo_tabla() and marcador_tabla(texto) == _tabla_ideal(texto, "verifika_prod"):
                        continue
                    clave = (huella, charla["id"], k, forma, rep, nombre)
                    if clave not in hechas and zlib.crc32(repr(clave[1:]).encode()) % partes == parte - 1:
                        trabajo.append((charla, k, forma, texto, rep))
    print(f"[parte {parte}/{partes}] faltan {len(trabajo)} corridas, consigna {huella}", flush=True)
    for charla, k, forma, texto, rep in trabajo:
        agendas = AGENDAS[charla["id"]]
        uid = f"trad_{parte}_{charla['id']}"
        C.reiniciar_cliente(uid)
        respuestas = []
        for i, t in enumerate(charla["turnos"][:k]):
            async def _mano(*a, _ag=agendas[i], **kw):
                return _ag

            async def _expl(pregunta, *a, _ag=agendas[i], **kw):
                return _explicacion(_ag, EXPLICAR)
            it.interpretar, it.explicar, it.elegir = _mano, _expl, elegir_mano
            respuestas.append("\n".join(asyncio.run(C.turno(uid, t["texto"]))))
        vistas = []

        async def _modelo(*a, **kw):
            for intento in range(5):
                r = await real_interpretar(*a, **kw)
                if r is not None:
                    vistas.append(r)
                    return r
                await asyncio.sleep(15 * (intento + 1))
            return None

        async def _expl_k(pregunta, *a, **kw):
            return _explicacion(agendas[k], EXPLICAR)
        it.interpretar, it.explicar, it.elegir = _modelo, _expl_k, real_elegir
        t0 = time.time()
        texto_r = "\n".join(asyncio.run(C.turno(uid, texto)))
        if not vistas:
            print(f"[parte {parte}] {charla['id']} T{k} {forma}: el modelo no contesto, se corta", flush=True)
            return False
        respuestas.append(texto_r)
        casillas = charla["turnos"][k]["casillas"]
        malas = [c["n"] for c in casillas if nota_casilla(c, [], texto_r, respuestas) is not True]
        x = {"huella": huella, "modelo": nombre, "charla": charla["id"], "turno": k, "forma": forma, "rep": rep, "texto": texto,
             "bien": not malas, "malas": malas, "acciones_iguales": _acciones(vistas[-1]) == _acciones(agendas[k]),
             "agenda": vistas[-1], "respuesta": texto_r,
             "clave": nombre if nombre != "gemini" else
             "paga" if os.environ.get("BANCO_CLAVE_PAGA", "").lower() == "true" else "gratis", "segundos": round(time.time() - t0, 1)}
        with open(CORRIDAS, "a", encoding="utf-8") as out:
            out.write(json.dumps(x, ensure_ascii=False) + "\n")
        print(f"[parte {parte}] {charla['id']} T{k} {forma} r{rep}: {'bien' if not malas else 'MAL ' + '; '.join(malas)}",
              flush=True)
    return True


def informe() -> None:
    from banco_pruebas import cableado58 as R
    from banco_pruebas import clon_produccion as C
    C.preparar_entorno()
    C.instalar()
    huella, hechas = _huella(), _leidas()
    turnos = [(c["id"], k) for c in R.charlas() for k in range(len(c["turnos"]))]
    print(f"\nLO QUE EL MODELO TRADUCE, consigna {huella}: {len(turnos)} turnos, {len(FORMAS)} formas, {REPS} veces")
    hechas_h = {k[1:5]: v for k, v in hechas.items() if k[0] == huella and k[5] == "gemini"}
    print(f"  corridas: {len(hechas_h)} de {len(turnos) * len(FORMAS) * REPS}")
    estables = {}
    for forma in FORMAS:
        corr = [v for (ch, k, f, r), v in hechas_h.items() if f == forma]
        casos = [(ch, k) for ch, k in turnos if all((ch, k, forma, r) in hechas_h for r in range(REPS))]
        firmes = [c for c in casos if all(hechas_h[(*c, forma, r)]["bien"] for r in range(REPS))]
        nunca = [c for c in casos if not any(hechas_h[(*c, forma, r)]["bien"] for r in range(REPS))]
        estables[forma] = set(firmes)
        b = sum(1 for v in corr if v["bien"])
        print(f"  {forma:10} corridas bien {b} de {len(corr)} · turnos firmes, tres de tres, {len(firmes)} de {len(casos)}"
              f" · nunca {len(nunca)} · a veces {len(casos) - len(firmes) - len(nunca)}")
    completos = [c for c in turnos if all((*c, f, r) in hechas_h for f in FORMAS for r in range(REPS))]
    todas = [c for c in completos if all(c in estables[f] for f in FORMAS)]
    print(f"  firmes en las cinco formas: {len(todas)} de {len(completos)} turnos completos")
    flojos = [c for c in completos if c not in todas]
    if flojos:
        print("  los que fallan alguna vez, con cuantas de quince salieron bien:")
        for c in flojos:
            n = sum(1 for f in FORMAS for r in range(REPS) if hechas_h[(*c, f, r)]["bien"])
            print(f"    {c[0]} T{c[1]}: {n} de 15")


def main(argv: list) -> int:
    sys.path.insert(0, os.path.dirname(AQUI))
    if "--informe" not in argv:
        parte, partes = 1, 1
        if "--parte" in argv:
            parte, partes = map(int, argv[argv.index("--parte") + 1].split("/"))
        turnos = {(a.split(":")[0], int(a.split(":")[1])) for a in argv if re.fullmatch(r"[CK]\d\d:\d+", a)}
        if not correr(parte, partes, [a for a in argv if re.fullmatch(r"[CK]\d\d", a)] or sorted({c for c, _ in turnos}),
                      turnos):
            return 2
    informe()
    comparar()
    return 0


def comparar() -> None:
    """Los otros modelos, una vez, contra la primera vuelta de Gemini en los mismos turnos y formas."""
    huella, hechas = _huella(), _leidas()
    gem = {k[1:4]: v["bien"] for k, v in hechas.items() if k[0] == huella and k[5] == "gemini" and k[4] == 0}
    for nombre in PROVEEDORES:
        otro = {k[1:4]: v["bien"] for k, v in hechas.items() if k[0] == huella and k[5] == nombre}
        if not otro:
            continue
        print(f"\n{nombre.upper()}, una vez, contra Gemini en lo mismo · gastado {gastado_otro(nombre):.2f} dolares")
        for forma in FORMAS:
            ks = [k for k in otro if k[2] == forma]
            print(f"  {forma:10} {nombre} {sum(otro[k] for k in ks)} · gemini {sum(gem.get(k, False) for k in ks)} · de {len(ks)}")
        mejor = sorted({(k[0], k[1]) for k in otro if otro[k] and not gem.get(k, True)})
        peor = sorted({(k[0], k[1]) for k in otro if not otro[k] and gem.get(k, False)})
        print(f"  arregla alguna forma de: {' '.join(f'{c}T{t}' for c, t in mejor) or 'ninguno'}")
        print(f"  rompe alguna forma de:   {' '.join(f'{c}T{t}' for c, t in peor) or 'ninguno'}")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

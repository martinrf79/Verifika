"""LA CALCULADORA — cuanto cuesta una prueba, antes de correrla y despues (29-sep-2026).

POR QUE EXISTE. El 28 y 29-sep el banco se llevo unos diez dolares de la clave
paga en un dia y nadie lo supo hasta ver la factura. Con esto el costo se ve
ANTES de correr y se mide DESPUES, con los tokens que devolvio el proveedor.

No esta en el camino del mensaje: no la importa nada de `app/`, no deploya.

TRES COSAS:

  estimar   cuanto va a costar una tanda, con los promedios medidos en las
            corridas guardadas: llamadas por turno y tokens por llamada.
  real      cuanto costaron las corridas guardadas, por etiqueta, al precio
            de la paga. La gratis no se cobra, pero si hubiera sido paga
            costaba eso: es la cuenta que importa para saber que se gasta.
  medir     el peso fijo de cada llamada del bot —prompt y herramientas—
            contado por el tokenizador del proveedor, con una llamada de un
            token de salida. Casi gratis.

LO QUE NO SABE, dicho adelante. Las corridas del agente guardan solo los
tokens de ENTRADA: la salida se estima con SALIDA_POR_LLAMADA, medida en el
laboratorio. La entrada es mas del noventa por ciento de la factura.

  python3 -m banco_pruebas.costo estimar --charlas 58 --turnos 2 --reps 3
  python3 -m banco_pruebas.costo estimar --modo sala --charlas 58 --modelo deepseek-chat
  python3 -m banco_pruebas.costo estimar --modo interpretar --charlas 68 --reps 3 --entrada 900
  python3 -m banco_pruebas.costo real
  python3 -m banco_pruebas.costo medir --modelo deepseek-chat
"""
import datetime
import json
import os
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
PRECIOS = AQUI / "precios_llm.json"
CORRIDAS = ["sonda_charlas_corridas.jsonl", "sala_corridas.jsonl", "desmenuzar_corridas.jsonl",
            "sonda_modelo_corridas.jsonl", "laboratorio_corridas.jsonl"]
# Tokens de salida por llamada del agente: la mayoria de las vueltas es una
# llamada a herramienta, corta; la ultima es la respuesta. Medido en el
# laboratorio; se corrige ahi.
SALIDA_POR_LLAMADA = 150
# Cuando no hay corridas guardadas: lo medido el 29-sep sobre 2.700 turnos.
LLAMADAS_POR_TURNO = 2.0
ENTRADA_POR_LLAMADA = 2300


def precios() -> dict:
    return {k: v for k, v in json.load(open(PRECIOS, encoding="utf-8")).items() if not k.startswith("_")}


def modelo_de(nombre: str) -> str:
    """El renglon de precios que corresponde a un nombre de modelo."""
    n = (nombre or "").lower().replace(" (paga)", "")
    p = precios()
    if n in p:
        return n
    if "deepseek" in n:
        return "deepseek-chat"
    return next(k for k in p if k.startswith("gemini"))


def es_pico(p: dict, cuando: datetime.datetime = None) -> bool:
    pico = p.get("pico")
    if not pico:
        return False
    t = cuando or datetime.datetime.now(datetime.timezone.utc)
    if pico.get("solo_dias_habiles") and t.weekday() >= 5:
        return False
    return any(a <= t.hour < b for a, b in pico["horas_utc"])


def dolares(entrada: int, salida: int, modelo: str, cache: int = 0, pico: bool = False) -> float:
    """Entrada incluye la parte cacheada, como la cuenta el proveedor."""
    p = precios()[modelo_de(modelo)]
    f = p["pico"]["factor"] if pico and p.get("pico") else 1
    return f * ((entrada - cache) * p["entrada"] + cache * p["cache"] + salida * p["salida"]) / 1e6


# ══ ESTIMAR ═════════════════════════════════════════════════════════════════

def perfil() -> dict:
    """Llamadas por turno y entrada por llamada, de las corridas del agente."""
    f = AQUI / "sonda_charlas_corridas.jsonl"
    turnos = llamadas = entrada = 0
    if f.exists():
        for x in open(f, encoding="utf-8"):
            for t in json.loads(x).get("turnos", []):
                u = t.get("uso") or []
                if u:
                    turnos += 1
                    llamadas += len(u)
                    entrada += sum(a.get("entrada", 0) for a in u)
    if not llamadas:
        return {"llamadas_por_turno": LLAMADAS_POR_TURNO, "entrada_por_llamada": ENTRADA_POR_LLAMADA, "turnos": 0}
    return {"llamadas_por_turno": llamadas / turnos, "entrada_por_llamada": entrada / llamadas, "turnos": turnos}


def estimar(charlas: int, turnos: float, reps: int, modelo: str, modo: str = "vara",
            entrada: int = 0, salida: int = 0) -> dict:
    """modo vara: todos los turnos por el agente. sala: solo el ultimo turno.
    interpretar: una llamada sin herramientas por mensaje —desmenuzar, laboratorio—."""
    pf = perfil()
    if modo == "interpretar":
        n_llamadas = charlas * reps
        e = entrada or 900
        s = salida or 200
    else:
        por_charla = 1 if modo == "sala" else turnos
        n_llamadas = charlas * por_charla * reps * pf["llamadas_por_turno"]
        e = entrada or pf["entrada_por_llamada"]
        s = salida or SALIDA_POR_LLAMADA
    tok_e, tok_s = int(n_llamadas * e), int(n_llamadas * s)
    p = precios()[modelo_de(modelo)]
    return {"modelo": modelo_de(modelo), "modo": modo, "llamadas": int(n_llamadas),
            "entrada": tok_e, "salida": tok_s, "dolares": dolares(tok_e, tok_s, modelo),
            "dolares_pico": dolares(tok_e, tok_s, modelo, pico=True) if p.get("pico") else None,
            "perfil": pf}


# ══ REAL ════════════════════════════════════════════════════════════════════

def real() -> dict:
    """{(archivo, etiqueta): {entrada, llamadas, salida, modelo}} de lo guardado."""
    out = {}
    for nombre in CORRIDAS:
        f = AQUI / nombre
        if not f.exists():
            continue
        for x in open(f, encoding="utf-8"):
            r = json.loads(x)
            k = (nombre.replace("_corridas.jsonl", ""), r.get("etiqueta", "base"))
            a = out.setdefault(k, {"entrada": 0, "salida": 0, "cache": 0, "llamadas": 0, "medida": 0,
                                   "modelo": r.get("modelo") or ""})
            if "turnos" in r:
                for t in r["turnos"]:
                    for u in t.get("uso") or []:
                        a["entrada"] += u.get("entrada", 0)
                        a["cache"] += u.get("cache", 0)
                        a["llamadas"] += 1
                        if "salida" in u:
                            a["salida"] += u["salida"]
                            a["medida"] += 1
            else:
                a["entrada"] += r.get("entrada", r.get("tokens", 0)) or 0
                a["llamadas"] += 1
                if "salida_tokens" in r:
                    a["salida"] += r["salida_tokens"]
                    a["medida"] += 1
    for a in out.values():  # la salida que no se guardo, estimada
        a["salida"] += (a["llamadas"] - a["medida"]) * SALIDA_POR_LLAMADA
        a["dolares"] = dolares(a["entrada"], a["salida"], a["modelo"], a["cache"])
    return out


# ══ MEDIR ═══════════════════════════════════════════════════════════════════

def medir(modelo: str) -> dict:
    """El prompt del agente y sus herramientas, contados por el proveedor."""
    from banco_pruebas.laboratorio import cliente, llamar
    from banco_pruebas.peso_del_turno import TIENDA, _preparar
    _preparar()
    from app.core import agente
    cli, nombre = cliente(modelo)
    sistema = agente.sistema(TIENDA)
    tools = agente.esquema(TIENDA)
    solo = llamar(cli, nombre, [{"role": "user", "content": "hola"}], max_tokens=1)
    con_sis = llamar(cli, nombre, [{"role": "system", "content": sistema}, {"role": "user", "content": "hola"}],
                     max_tokens=1)
    todo = llamar(cli, nombre, [{"role": "system", "content": sistema}, {"role": "user", "content": "hola"}],
                  tools=tools, max_tokens=1)
    return {"modelo": nombre, "mensaje": solo["entrada"], "prompt": con_sis["entrada"] - solo["entrada"],
            "herramientas": todo["entrada"] - con_sis["entrada"], "fijo": todo["entrada"]}


# ══ LA SALIDA ═══════════════════════════════════════════════════════════════

def _opt(a, nombre, defecto, tipo=str):
    if nombre in a:
        i = a.index(nombre)
        v = tipo(a[i + 1])
        del a[i:i + 2]
        return v
    return defecto


def main():
    a = sys.argv[1:]
    que = a.pop(0) if a else "estimar"
    modelo = _opt(a, "--modelo", "gemini-3.1-flash-lite")
    if que == "estimar":
        r = estimar(_opt(a, "--charlas", 58, int), _opt(a, "--turnos", 2.0, float), _opt(a, "--reps", 1, int),
                    modelo, _opt(a, "--modo", "vara"), _opt(a, "--entrada", 0, int), _opt(a, "--salida", 0, int))
        pf = r["perfil"]
        print(f"{r['modelo']} · modo {r['modo']} · {r['llamadas']} llamadas al modelo")
        print(f"  entrada {r['entrada']:,} tokens · salida {r['salida']:,} tokens")
        print(f"  COSTO: {r['dolares']:.3f} dolares" + (f" · en hora pico {r['dolares_pico']:.3f}" if r["dolares_pico"] else ""))
        print(f"  perfil: {pf['llamadas_por_turno']:.2f} llamadas por turno, {pf['entrada_por_llamada']:.0f} tokens"
              f" por llamada, medido en {pf['turnos']} turnos")
    elif que == "real":
        filas = sorted(real().items(), key=lambda kv: -kv[1]["dolares"])
        total = sum(v["dolares"] for _, v in filas)
        tok = sum(v["entrada"] for _, v in filas)
        print(f"CORRIDAS GUARDADAS · {tok:,} tokens de entrada · {total:.2f} dolares al precio de la paga")
        for (arch, et), v in filas[:_opt(a, "--primeras", 20, int)]:
            print(f"  {v['dolares']:7.3f}  {v['entrada']:>11,}  {v['llamadas']:>6} llamadas  {arch} · {et}")
    elif que == "medir":
        r = medir(modelo)
        print(f"{r['modelo']}: fijo por llamada {r['fijo']} tokens = prompt {r['prompt']}"
              f" + herramientas {r['herramientas']} + mensaje {r['mensaje']}")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()

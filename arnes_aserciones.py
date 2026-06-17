"""
ARNES DE ASERCIONES POR TURNO — evaluacion estilo Promptfoo/DeepEval/VRUNAI.

Corre conversaciones guionadas por el flujo real (process_message) y evalua
ASERCIONES AUTOMATICAS por turno contra la respuesta y la telemetria
(TELEMETRIA_TURNO): tool correcta llamada, args esperados, montos respaldados
por la fuente (resultados de tools + verdad del turno), frases prohibidas
(no-invencion), frases requeridas, fallback esperado o no, outcome y estado.

Tipos de asercion por turno (todas opcionales, en la clave "asserts"):
  tools           lista de tools que DEBEN haberse llamado este turno
  tools_no        lista de tools que NO deben haberse llamado
  args_contiene   lista de {tool, contiene}: el substring debe estar en los args
  contiene        lista de substrings requeridos en la respuesta (sin acentos, sin caso)
  contiene_alguna lista: al menos UNO debe estar en la respuesta
  no_contiene     lista de substrings prohibidos en la respuesta
  regex           regex que la respuesta debe matchear
  no_regex        regex que la respuesta NO debe matchear
  montos_respaldados  true: todo monto con $ en la respuesta debe existir en
                      la fuente del turno (resultados crudos de tools + verdad)
  no_fallback     true: la respuesta no debe ser un mensaje de fallback
  fallback        true: SI debe ser fallback (caso honesto de "no se")
  outcome         outcome esperado del turno (ok, venta_cerrada, tomando_datos...)

Uso (via lanzador, que carga .secrets6.env y provider):
    .\\correr_local.ps1 arnes                          # suite completa
    .\\correr_local.ps1 arnes verifika_prod
    .\\correr_local.ps1 py arnes_aserciones.py --solo a01,a05
    .\\correr_local.ps1 py arnes_aserciones.py --solo-fallidos

Salida: resultados_arnes.csv (una fila por turno) + arnes_fallas.txt (detalle).
"""
import asyncio
import csv
import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# La telemetria es la columna vertebral del arnes: sin ella no hay aserciones
# de tools ni de montos. Solo memoria de proceso, no toca prod.
os.environ["TELEMETRIA_TURNO"] = "true"

from app.core.orchestrator import process_message, reset_user
from app.core.telemetria import leer_turno, tools_compacto
from app.config import get_settings

ARCHIVO = "casos_arnes.json"
SALIDA = "resultados_arnes.csv"
DETALLE = "arnes_fallas.txt"
TIENDA_DEFAULT = os.getenv("SMOKE_TIENDA", "verifika_prod")
DELAY = 0.3


def norm(s: str) -> str:
    """Minusculas y sin acentos, para comparar frases sin fragilidad."""
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return s.lower()


def montos_de(texto: str) -> set[str]:
    """Montos con $ en el texto, normalizados a solo digitos. $58.500 -> 58500."""
    out = set()
    for m in re.findall(r"\$\s?[\d][\d\.\,]*", texto or ""):
        digitos = re.sub(r"\D", "", m)
        if digitos:
            out.add(digitos.lstrip("0") or "0")
    return out


def numeros_fuente(turno: dict) -> set[str]:
    """Todo numero presente en la fuente del turno: resultados crudos de tools
    y la verdad calculada por codigo. Cada numero entra como esta y sin
    separadores de miles, para matchear $58.500 contra 58500."""
    piezas = [t.get("raw") or "" for t in turno.get("tools", [])]
    for t in turno.get("tools", []):
        piezas.append(" ".join(t.get("nums") or []))
    piezas.append(turno.get("verdad") or "")
    fuente = " ".join(piezas)
    out = set()
    for m in re.findall(r"[\d][\d\.\,]*", fuente):
        crudo = re.sub(r"\D", "", m)
        if crudo:
            out.add(crudo.lstrip("0") or "0")
        # variante por si la fuente trae 58500.0 (float): sin decimales
        sin_dec = re.sub(r"[\.,]\d{1,2}$", "", m)
        sin_dec = re.sub(r"\D", "", sin_dec)
        if sin_dec:
            out.add(sin_dec.lstrip("0") or "0")
    return out


def ids_calculadora(turno: dict) -> list[str]:
    """IDs de producto que entraron a calculate_total en este turno."""
    out = []
    for t in turno.get("tools", []):
        if t.get("tool") == "calculate_total":
            out.extend(t.get("ids") or [])
    return out


def evaluar(asserts: dict, respuesta: str, turno: dict, es_fb: bool,
            fuente_acumulada: set[str] | None = None,
            carrito_previo: set[str] | None = None) -> list[str]:
    """Evalua las aserciones de un turno. Devuelve la lista de fallas.

    fuente_acumulada: numeros devueltos por tools en turnos ANTERIORES de la
    misma conversacion. Citar un precio ya verificado antes es legitimo (igual
    que la red de precios del verificador); inventar uno que ninguna tool
    devolvio jamas sigue fallando."""
    fallas = []
    r = norm(respuesta)
    tools_llamadas = [t.get("tool") for t in turno.get("tools", [])]

    for t in asserts.get("tools", []):
        if t not in tools_llamadas:
            fallas.append(f"tool_no_llamada:{t}")
    for t in asserts.get("tools_no", []):
        if t in tools_llamadas:
            fallas.append(f"tool_prohibida_llamada:{t}")
    for spec in asserts.get("args_contiene", []):
        ok = any(t.get("tool") == spec["tool"]
                 and norm(spec["contiene"]) in norm(t.get("args") or "")
                 for t in turno.get("tools", []))
        if not ok:
            fallas.append(f"args_sin:{spec['tool']}:{spec['contiene']}")
    for frase in asserts.get("contiene", []):
        if norm(frase) not in r:
            fallas.append(f"falta_frase:{frase}")
    alguna = asserts.get("contiene_alguna", [])
    if alguna and not any(norm(f) in r for f in alguna):
        fallas.append(f"falta_alguna:{'|'.join(alguna)}")
    for frase in asserts.get("no_contiene", []):
        if norm(frase) in r:
            fallas.append(f"frase_prohibida:{frase}")
    if asserts.get("regex") and not re.search(asserts["regex"], respuesta or "",
                                              re.IGNORECASE):
        fallas.append(f"no_matchea_regex:{asserts['regex']}")
    if asserts.get("no_regex") and re.search(asserts["no_regex"], respuesta or "",
                                             re.IGNORECASE):
        fallas.append(f"matchea_regex_prohibida:{asserts['no_regex']}")
    if asserts.get("montos_respaldados"):
        fuente = numeros_fuente(turno) | (fuente_acumulada or set())
        for monto in montos_de(respuesta):
            if monto not in fuente:
                fallas.append(f"monto_sin_fuente:${monto}")
    if asserts.get("carrito_subset"):
        # El pedido solo puede ACHICARSE o mantenerse en este turno (el cliente
        # saco o confirmo, no nombro productos nuevos): los ids que entran a la
        # calculadora deben ser subconjunto del ultimo carrito calculado. Caza
        # la clase "carrito muta de identidad" (precios reales, productos
        # cambiados) que ningun verificador de montos puede ver.
        actuales = set(ids_calculadora(turno))
        if actuales and carrito_previo is not None:
            intrusos = actuales - carrito_previo
            if intrusos:
                fallas.append(f"carrito_drift:{sorted(intrusos)}")
    if asserts.get("no_fallback") and es_fb:
        fallas.append("fallback_inesperado")
    if asserts.get("fallback") and not es_fb:
        fallas.append("esperaba_fallback")
    if asserts.get("outcome") and turno.get("outcome") != asserts["outcome"]:
        fallas.append(f"outcome:{turno.get('outcome')}!={asserts['outcome']}")
    return fallas


# ── Estresador: mutadores de casos. Cada mutador deriva variantes nuevas de
# los casos existentes manteniendo las MISMAS aserciones: si el bot es robusto,
# la variante pasa igual. Deterministico (seed por caso) para reproducir.
_TYPOS_PALABRA = {
    "hola": "ola", "quiero": "kiero", "que": "q", "por": "x",
    "cuanto": "cuannto", "envio": "embio", "tenes": "tenez",
    "hacen": "asen", "para": "pa", "gracias": "grasias",
    "transferencia": "transferensia", "barato": "varato",
    "teclado": "tecaldo", "mouse": "mause", "auriculares": "auriculres",
    "garantia": "garantia", "factura": "factura", "descuento": "descuneto",
}


def _mutar_typos(texto: str, seed: int) -> str:
    """Typos argentinos de chat: palabras mal escritas + swap de letras
    adyacentes en palabras largas. No toca numeros ni nombres propios en
    mayuscula (un telefono o un modelo mal tipeado cambia el caso de verdad)."""
    import random
    rng = random.Random(seed)
    out = []
    for w in texto.split():
        bajo = w.lower()
        if bajo in _TYPOS_PALABRA:
            out.append(_TYPOS_PALABRA[bajo])
        elif (len(w) > 5 and w.isalpha() and w.islower()
                and rng.random() < 0.35):
            i = rng.randint(1, len(w) - 2)
            out.append(w[:i] + w[i + 1] + w[i] + w[i + 2:])
        else:
            out.append(w)
    return " ".join(out)


# Ruido de presion/apuro de chat real: no cambia la intencion ni el dato, asi
# que las aserciones del caso base tienen que pasar igual.
_PRESION_PREFIJOS = ["dale rapido ", "necesito YA, ", "apurame con esto: ",
                     "contestame rapido!! ", "es urgente, "]
_PRESION_SUFIJOS = [" dale dale", " pero ya!!", " no tengo todo el dia",
                    " respondeme rapido porfa", " ...hola??"]


def _mutar_presion(texto: str, seed: int) -> str:
    import random
    rng = random.Random(seed)
    pre = rng.choice(_PRESION_PREFIJOS) if rng.random() < 0.5 else ""
    suf = rng.choice(_PRESION_SUFIJOS) if rng.random() < 0.5 else ""
    return f"{pre}{texto}{suf}"


_MUTADORES = {"typos": ("_ty", _mutar_typos), "presion": ("_pr", _mutar_presion)}


def derivar_mutados(casos: list[dict], clase: str) -> list[dict]:
    """Deriva la variante mutada de cada caso manteniendo las aserciones.
    Cada falla nueva del molino se vuelve clase de mutador aca."""
    if clase not in _MUTADORES:
        raise SystemExit(f"Clase de mutador desconocida: {clase}. "
                         f"Disponibles: {sorted(_MUTADORES)}")
    sufijo, fn = _MUTADORES[clase]
    mutados = []
    for c in casos:
        seed = sum(ord(ch) for ch in c["id"])
        turnos = []
        for j, paso in enumerate(c["turnos"]):
            nuevo = dict(paso)
            nuevo["m"] = fn(paso["m"], seed + j)
            turnos.append(nuevo)
        mutados.append({**c, "id": c["id"] + sufijo, "turnos": turnos})
    return mutados


def cargar_solo_fallidos() -> set[str]:
    if not Path(SALIDA).exists():
        return set()
    with open(SALIDA, encoding="utf-8") as f:
        return {row["caso"] for row in csv.DictReader(f) if row["fallas"]}


async def main():
    s = get_settings()
    args = sys.argv[1:]
    print(f"[args] {args}")
    tienda = TIENDA_DEFAULT
    solo: set[str] | None = None
    # PowerShell come los guiones dobles al rebindear args, asi que ademas de
    # --solo se acepta solo=a01,a05, solo-fallidos y paralelo=N como palabras.
    paralelo = 4
    mutar = ""
    pendiente_solo = False
    for a in args:
        a_limpio = a.lstrip("-")
        if a_limpio.startswith("mutar="):
            mutar = a_limpio.split("=", 1)[1]
        elif pendiente_solo:
            solo = set(re.split(r"[,\s]+", a.strip()))
            pendiente_solo = False
        elif a_limpio == "solo-fallidos":
            solo = cargar_solo_fallidos()
            print(f"Re-corriendo solo casos fallidos: {sorted(solo)}")
        elif a_limpio.startswith("solo="):
            # PowerShell parte solo=a,b en lista y la re-une con ESPACIOS:
            # se aceptan ambos separadores.
            solo = set(re.split(r"[,\s]+", a_limpio.split("=", 1)[1].strip()))
        elif a_limpio == "solo":
            pendiente_solo = True
        elif a_limpio.startswith("paralelo="):
            paralelo = max(1, int(a_limpio.split("=", 1)[1]))
        elif "," in a:
            solo = set(re.split(r"[,\s]+", a.strip()))
        elif not a.startswith("-"):
            tienda = a

    with open(ARCHIVO, encoding="utf-8") as f:
        casos = json.load(f)["casos"]
    if mutar:
        casos = derivar_mutados(casos, mutar)
        print(f"[mutador] clase={mutar}: corriendo SOLO las variantes mutadas")
    if solo is not None:
        casos = [c for c in casos
                 if any(c["id"] == s or c["id"].startswith(s) for s in solo)]
        if not casos:
            print("Nada que correr (sin casos fallidos o ids no encontrados).")
            return

    n_asserts = sum(1 for c in casos for t in c["turnos"] if t.get("asserts"))
    print("=" * 64)
    print(f"ARNES DE ASERCIONES  |  tienda={tienda}  |  paralelo={paralelo}")
    print(f"Solver={s.LLM_PROVIDER}  Interpreter={s.INTERPRETER_PROVIDER}")
    print(f"{len(casos)} casos, {sum(len(c['turnos']) for c in casos)} turnos, "
          f"{n_asserts} turnos con aserciones")
    print("=" * 64)

    filas, detalles = [], []
    t_total = time.time()
    sem = asyncio.Semaphore(paralelo)

    async def correr_caso(c):
        """Corre una conversacion completa (turnos en orden, mismo user_id).
        Devuelve filas, detalles y las lineas de consola ya armadas, para que
        el paralelismo no entrevere la salida."""
        cid = c["id"]
        user = f"arnes_{cid}"
        filas_c, detalles_c = [], []
        fuente_acumulada: set[str] = set()
        carrito_previo: set[str] | None = None
        lineas = [f"\n### {cid}  ({c['categoria']})"]
        async with sem:
            reset_user(user, tienda_id=c.get("tienda", tienda))
            for i, paso in enumerate(c["turnos"], 1):
                msg = paso["m"]
                asserts = paso.get("asserts") or {}
                t0 = time.time()
                try:
                    resp = await process_message(
                        user_id=user, raw_message=msg,
                        tienda_id=c.get("tienda", tienda), canal="telegram")
                    err = ""
                except Exception as e:
                    import traceback
                    resp = ""
                    err = f"{type(e).__name__}: {e}"
                    detalles_c.append(
                        f"{cid} T{i} TRACEBACK:\n{traceback.format_exc()}\n")
                dt = round(time.time() - t0, 1)
                turno = leer_turno(user)
                es_fb = resp in (s.FALLBACK_MESSAGE, s.VERIFIKA_FALLBACK_MESSAGE)
                fallas = ([f"error_tecnico:{err}"] if err
                          else evaluar(asserts, resp, turno, es_fb,
                                       fuente_acumulada, carrito_previo))
                fuente_acumulada |= numeros_fuente(turno)
                ids_turno = ids_calculadora(turno)
                if ids_turno:
                    carrito_previo = set(ids_turno)
                marca = "FALLA" if fallas else ("ok" if asserts else "-")
                lineas.append(f"  T{i:02d} ({dt:4.1f}s) [{marca}]  C: {msg[:70]}")
                if fallas:
                    lineas.append(f"       !! {'; '.join(fallas)[:140]}")
                    lineas.append(f"       B: {resp[:160]}")
                    detalles_c.append(
                        f"{cid} T{i} | {msg}\n  FALLAS: {'; '.join(fallas)}\n"
                        f"  RESP: {resp}\n  TOOLS: {tools_compacto(user)}\n"
                        f"  VERDAD: {turno.get('verdad') or '-'}\n")
                filas_c.append({
                    "caso": cid, "categoria": c["categoria"], "turno": i,
                    "mensaje": msg, "respuesta": resp, "tiempo_seg": dt,
                    "fallback": "si" if es_fb else "no",
                    "tools": tools_compacto(user),
                    "fallas": "; ".join(fallas),
                })
                await asyncio.sleep(DELAY)
        print("\n".join(lineas))
        filas.extend(filas_c)
        detalles.extend(detalles_c)
        guardar(filas)

    await asyncio.gather(*(correr_caso(c) for c in casos))
    # Orden estable del CSV aunque los casos terminen desordenados.
    filas.sort(key=lambda r: (r["caso"], int(r["turno"])))
    guardar(filas)

    with open(DETALLE, "w", encoding="utf-8") as f:
        f.write("\n".join(detalles) if detalles else "SIN FALLAS\n")
    resumen(filas, casos, round(time.time() - t_total, 1))


def guardar(filas):
    with open(SALIDA, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "caso", "categoria", "turno", "mensaje", "respuesta",
            "tiempo_seg", "fallback", "tools", "fallas"])
        w.writeheader()
        w.writerows(filas)


def resumen(filas, casos, t_total):
    con_assert = [r for r in filas if r["fallas"] or _tenia_asserts(casos, r)]
    fallados = [r for r in filas if r["fallas"]]
    casos_fallados = sorted({r["caso"] for r in fallados})
    por_tipo: dict[str, int] = {}
    for r in fallados:
        for f in r["fallas"].split("; "):
            tipo = f.split(":")[0]
            por_tipo[tipo] = por_tipo.get(tipo, 0) + 1
    n = len(con_assert) or 1
    print("\n" + "=" * 64)
    print("RESUMEN ARNES")
    print(f"Turnos con aserciones: {len(con_assert)}")
    print(f"Turnos que PASAN     : {len(con_assert) - len(fallados)} "
          f"({round(100 * (len(con_assert) - len(fallados)) / n, 1)}%)")
    print(f"Turnos que FALLAN    : {len(fallados)}")
    print(f"Casos con falla      : {len(casos_fallados)}  {casos_fallados}")
    if por_tipo:
        print("Fallas por tipo:")
        for tipo, cnt in sorted(por_tipo.items(), key=lambda x: -x[1]):
            print(f"  {tipo:24s} {cnt}")
    print(f"Tiempo total: {t_total}s")
    print(f"\nCSV: {SALIDA}  |  Detalle de fallas: {DETALLE}")


def _tenia_asserts(casos, fila) -> bool:
    for c in casos:
        if c["id"] == fila["caso"]:
            paso = c["turnos"][int(fila["turno"]) - 1]
            return bool(paso.get("asserts"))
    return False


if __name__ == "__main__":
    asyncio.run(main())

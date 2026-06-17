"""
Molino de FOCOS: corre conversaciones dirigidas a los puntos flojos y AUDITA
cada respuesta por codigo. Nace de la leccion de jun-2026: la planilla del
molino clasico dio 0 fallbacks con ventas caidas adentro; este arnes LEE el
texto y marca las clases de falla conocidas, mas las expectativas declaradas
por turno en conversaciones_multiturno_focos.json.

Clases de alerta genericas (corren en todos los turnos):
  corte             respuesta truncada a mitad de frase o de numero
  fuga_marcador     bloque [interno] o placeholder que llego al cliente
  puente_en_cierre  el cliente quiso cerrar y recibio un puente enlatado
  descuento_no_aplicado  dice "con descuento" pero ningun monto esta rebajado
  repeticion        misma respuesta que un turno anterior de la conversacion
Mas las declaradas en el JSON: espera_contiene_alguno / espera_no_contiene.

Uso (via el lanzador, que carga las env vars):
    correr_local.ps1 molino-focos
    correr_local.ps1 molino-focos verifika_prod -AllGemini

Salida: resultados_focos[_TAG].csv (columna alertas) + resumen por clase.
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

from app.core.orchestrator import process_message, reset_user
from app.config import get_settings

ARCHIVO = "conversaciones_multiturno_focos.json"
_TAG = os.getenv("BENCH_TAG", "").strip()
_TAG = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in _TAG)
SALIDA = f"resultados_focos_{_TAG}.csv" if _TAG else "resultados_focos.csv"
TIENDA = sys.argv[1] if len(sys.argv) > 1 else os.getenv("SMOKE_TIENDA", "verifika_prod")
DELAY = 0.3

RE_MONTO = re.compile(r"\$\s?([\d.]+)")
RE_FUGA = re.compile(
    r"\[(?:[^\]]*(?:Contexto|Estado de la|cliente se refiere|Presupuesto YA|"
    r"Productos ya|aqu[ií]|aqui\]|datos de pago|link)[^\]]*)\]", re.IGNORECASE)
RE_CIERRE = re.compile(
    r"\b(me lo llevo|lo llevo|cerralo|lo cierro|cierro|confirmo|lo confirmo|"
    r"dale,? cerra|lo compro|comprame)\b", re.IGNORECASE)
RE_DESC_NARRADO = re.compile(
    r"(con (el )?descuento|descuento aplicado|te queda(ria)? (en|con).{0,30}descuento)",
    re.IGNORECASE)


def _plano(t: str) -> str:
    """minusculas y sin tildes, para comparar textos sin pelearse con la forma"""
    t = unicodedata.normalize("NFD", t or "")
    return "".join(c for c in t if unicodedata.category(c) != "Mn").lower()


def _cargar_puentes() -> list[str]:
    """primeras ~50 letras de cada puente del banco, para reconocerlos"""
    try:
        with open(Path(__file__).parent / "data" / "puentes.json", encoding="utf-8") as f:
            data = json.load(f)
        textos = [p["texto"] for p in data.get("puentes", {}).values()]
        textos.append(data.get("derivar_humano", ""))
        return [_plano(t)[:50] for t in textos if t]
    except Exception:
        return []


PUENTES = _cargar_puentes()


def _precios_catalogo(tienda_id: str) -> set[int]:
    """todos los precios de lista de la tienda, para detectar montos SIN rebaja"""
    try:
        from app.storage.firestore_client import get_all_products
        return {int(p["precio_ars"]) for p in get_all_products(tienda_id=tienda_id)
                if p.get("precio_ars")}
    except Exception:
        return set()


def _montos(texto: str) -> list[int]:
    out = []
    for m in RE_MONTO.findall(texto or ""):
        try:
            out.append(int(m.replace(".", "")))
        except ValueError:
            pass
    return out


def auditar(msg: str, resp: str, previas: list[str], espera: dict,
            precios_lista: set[int]) -> list[str]:
    """Devuelve la lista de clases de alerta que dispara esta respuesta."""
    alertas = []
    r = resp or ""
    rp = _plano(r)

    # corte: termina sin cierre de frase. Un monto final COMPLETO es valido
    # (un presupuesto pelado termina en "Total: $38.000"); un numero corto
    # colgado ("= $225", "y $2") es un numero ARS truncado, eso si es corte.
    rs = r.strip()
    m_final = re.search(r"\$\s?([\d.]+)$", rs)
    if len(rs) > 40:
        if m_final:
            try:
                if int(m_final.group(1).replace(".", "")) < 1000:
                    alertas.append("corte")
            except ValueError:
                alertas.append("corte")
        elif re.search(r"[a-záéíóúñ0-9,=\$-]$", rs, re.IGNORECASE):
            alertas.append("corte")

    # fuga de marcador interno o placeholder
    if RE_FUGA.search(r):
        alertas.append("fuga_marcador")

    # el cliente quiso cerrar y recibio un puente enlatado
    if RE_CIERRE.search(msg or "") and any(rp.startswith(p) for p in PUENTES):
        alertas.append("puente_en_cierre")

    # dice "con descuento" pero todos los montos son precio de lista
    if RE_DESC_NARRADO.search(r):
        montos = _montos(r)
        if montos and precios_lista and all(m in precios_lista for m in montos):
            alertas.append("descuento_no_aplicado")

    # repeticion textual de un turno anterior (enlatado en loop)
    if len(rp) > 60 and any(rp == _plano(p) for p in previas):
        alertas.append("repeticion")

    # expectativas declaradas en el JSON para este turno
    debe = espera.get("espera_contiene_alguno") or []
    if debe and not any(_plano(e) in rp for e in debe):
        alertas.append(f"falta_esperado({'|'.join(debe)})")
    no_debe = espera.get("espera_no_contiene") or []
    pegados = [e for e in no_debe if _plano(e) in rp]
    if pegados:
        alertas.append(f"contiene_prohibido({'|'.join(pegados)})")

    return alertas


async def main():
    s = get_settings()
    with open(ARCHIVO, encoding="utf-8") as f:
        data = json.load(f)
    convs = data["conversaciones"]
    precios_lista = _precios_catalogo(TIENDA)

    print("=" * 64)
    print(f"MOLINO FOCOS  |  tienda={TIENDA}")
    print(f"Solver={s.LLM_PROVIDER}  Interpreter={s.INTERPRETER_PROVIDER}")
    print(f"{len(convs)} conversaciones, "
          f"{sum(len(c['turnos']) for c in convs)} turnos, "
          f"{len(precios_lista)} precios de lista cargados")
    print("=" * 64)

    filas = []
    t_total = time.time()

    for c in convs:
        cid = c["id"]
        user = f"focos_{cid}"
        reset_user(user, tienda_id=TIENDA)
        print(f"\n### {cid}  ({c['escenario']})")
        previas: list[str] = []

        for i, turno in enumerate(c["turnos"], 1):
            if isinstance(turno, str):
                msg, espera = turno, {}
            else:
                msg, espera = turno["msg"], turno
            t0 = time.time()
            try:
                resp = await process_message(
                    user_id=user, raw_message=msg, tienda_id=TIENDA,
                    canal="telegram")
                dt = round(time.time() - t0, 1)
            except Exception as e:
                dt = round(time.time() - t0, 1)
                resp = f"ERROR: {type(e).__name__}: {e}"
            alertas = auditar(msg, resp, previas, espera, precios_lista)
            previas.append(resp)
            marca = f"  [!] {', '.join(alertas)}" if alertas else ""
            print(f"  T{i:02d} ({dt:4.1f}s){marca}  C: {msg}")
            print(f"            B: {str(resp)[:160]}")
            filas.append({
                "conv_id": cid, "escenario": c["escenario"], "turno": i,
                "mensaje": msg, "respuesta": resp, "tiempo_seg": dt,
                "alertas": "; ".join(alertas),
                "error": "si" if str(resp).startswith("ERROR:") else "no",
            })
            guardar(filas)
            await asyncio.sleep(DELAY)

    resumen(filas, round(time.time() - t_total, 1))


def guardar(filas):
    with open(SALIDA, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "conv_id", "escenario", "turno", "mensaje", "respuesta",
            "tiempo_seg", "alertas", "error"])
        w.writeheader()
        w.writerows(filas)


def resumen(filas, t_total):
    n = len(filas)
    con_alerta = [r for r in filas if r["alertas"]]
    err = sum(1 for r in filas if r["error"] == "si")
    tprom = round(sum(r["tiempo_seg"] for r in filas) / n, 1) if n else 0
    clases: dict[str, int] = {}
    for r in con_alerta:
        for a in r["alertas"].split("; "):
            clave = a.split("(")[0]
            clases[clave] = clases.get(clave, 0) + 1
    print("\n" + "=" * 64)
    print("RESUMEN FOCOS")
    print(f"Turnos totales       : {n}")
    print(f"Tiempo promedio/turno: {tprom}s")
    print(f"Turnos con alerta    : {len(con_alerta)}  "
          f"({round(100*len(con_alerta)/n,1) if n else 0}%)")
    print(f"Errores tecnicos     : {err}")
    for clase, cant in sorted(clases.items(), key=lambda x: -x[1]):
        print(f"  - {clase}: {cant}")
    print(f"Tiempo total corrida : {t_total}s")
    print(f"\nResultados en {SALIDA}")
    if con_alerta:
        print("\nTurnos a LEER (conv/turno):")
        for r in con_alerta:
            print(f"  {r['conv_id']} t{r['turno']}: {r['alertas']}")


if __name__ == "__main__":
    asyncio.run(main())

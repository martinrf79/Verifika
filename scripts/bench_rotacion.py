"""
ROTACION DE MODELOS (PARALELA) — corre los MISMOS casos del banco contra varios
modelos gratis de OpenRouter, en paralelo, y compara estabilidad.

En serie es inviable (media hora). Acá las llamadas se disparan concurrentes con
un grupo acotado de obreros y reintento si el free tier frena, así el tiempo
total es ~la tanda mas lenta, no la suma.

Correr (carga .secrets10.env con la clave de OpenRouter):
    .\\correr_local.ps1 py scripts\\bench_rotacion.py -AllOpenRouter

Ajustes por entorno: ROT_REPS (default 2), ROT_CONCURRENCIA (default 6),
ROT_MODELOS (lista separada por coma para forzar modelos).
"""
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bench_interpretacion as B

OR_KEY = (os.getenv("OPENROUTER_API_KEY") or os.getenv("BENCH_API_KEY") or "").strip()
OR_BASE = "https://openrouter.ai/api/v1"
REPS = int(os.getenv("ROT_REPS", "2"))
CONC = int(os.getenv("ROT_CONCURRENCIA", "6"))

_PREFERIDOS = ("qwen", "llama-3.3", "llama-4", "deepseek", "mistral",
               "gemini-2", "gemma-3", "glm")

_client = OpenAI(api_key=OR_KEY, base_url=OR_BASE, timeout=45)


def _modelos_gratis():
    forzados = os.getenv("ROT_MODELOS")
    if forzados:
        return [m.strip() for m in forzados.split(",") if m.strip()]
    try:
        r = httpx.get(f"{OR_BASE}/models",
                      headers={"Authorization": f"Bearer {OR_KEY}"}, timeout=30)
        data = r.json().get("data", [])
    except Exception as e:
        print(f"[rotacion] no pude listar modelos: {str(e)[:100]}", flush=True)
        return []
    def _gratis(m):
        p = m.get("pricing", {}) or {}
        return str(p.get("prompt")) in ("0", "0.0") and \
            str(p.get("completion")) in ("0", "0.0")
    gratis = [m["id"] for m in data if _gratis(m) and m.get("id")]
    elegidos, familias = [], set()
    for fam in _PREFERIDOS:
        for mid in gratis:
            if fam in mid.lower() and fam not in familias:
                elegidos.append(mid)
                familias.add(fam)
                break
    return elegidos[:4]


def _caso_pasa(res, caso):
    for path, op, val in caso["afirma"]:
        if not B._chequear(B._get(res, path), op, val):
            return False
    return True


def _una_llamada(model, caso):
    """Una corrida con reintento; True si el caso pasa todas sus afirmaciones."""
    from app.config import openrouter_reasoning_off
    prompt = (B._PROMPT.format(estado=caso["estado"] or "vacío",
                               contexto=caso["contexto"] or "sin turnos previos",
                               mensaje=caso["mensaje"]) + B._ESQUEMA)
    extra = openrouter_reasoning_off("openrouter", model) or {}
    for intento in range(3):
        try:
            r = _client.chat.completions.create(
                model=model, temperature=0.0, max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
                **({"extra_body": extra} if extra else {}))
            return _caso_pasa(B._parsear(r.choices[0].message.content or ""), caso)
        except Exception as e:
            msg = str(e).lower()
            espera = 10 if ("429" in msg or "rate" in msg or "limit" in msg) else 2
            time.sleep(espera * (intento + 1))
    return False


def main():
    if not OR_KEY:
        print("[rotacion] falta OPENROUTER_API_KEY (corré con -AllOpenRouter)",
              flush=True)
        raise SystemExit(1)
    modelos = _modelos_gratis()
    if not modelos:
        print("[rotacion] no encontré modelos gratis", flush=True)
        raise SystemExit(1)
    print(f"[rotacion PARALELA] {len(modelos)} modelos, {REPS} reps/caso, "
          f"{len(B.CASOS)} casos, {CONC} en paralelo", flush=True)
    for m in modelos:
        print(f"   - {m}", flush=True)
    print("=" * 70, flush=True)

    # Todas las (modelo, caso, rep) como tareas concurrentes.
    tareas = [(m, c) for m in modelos for c in B.CASOS for _ in range(REPS)]
    resultados = {}  # (modelo, caso_id) -> lista de bool
    hechas, total, t0 = 0, len(tareas), time.time()
    with ThreadPoolExecutor(max_workers=CONC) as pool:
        fut = {pool.submit(_una_llamada, m, c): (m, c["id"]) for m, c in tareas}
        for f in as_completed(fut):
            m, cid = fut[f]
            try:
                ok = f.result()
            except Exception:
                ok = False
            resultados.setdefault((m, cid), []).append(ok)
            hechas += 1
            if hechas % 10 == 0 or hechas == total:
                print(f"   ... {hechas}/{total} llamadas "
                      f"({round(time.time() - t0)}s)", flush=True)

    print("=" * 70, flush=True)
    tabla = []
    for m in modelos:
        estables = sum(1 for c in B.CASOS
                       if len(resultados.get((m, c["id"]), [])) == REPS
                       and all(resultados[(m, c["id"])]))
        tabla.append((m, estables))
    print(f"RANKING (casos estables sobre {len(B.CASOS)}, {REPS} reps):", flush=True)
    for m, est in sorted(tabla, key=lambda x: -x[1]):
        print(f"   {est:>2}/{len(B.CASOS)}  {m}", flush=True)
    print(f"(referencia DeepSeek v4 flash: 15/{len(B.CASOS)})", flush=True)
    print(f"tiempo total: {round(time.time() - t0)}s", flush=True)


if __name__ == "__main__":
    main()

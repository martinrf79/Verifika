"""
EL PISO HISTORICO Y LA COMPUERTA.

POR QUE EXISTE (Martin, 2-ago-2026). El 2-ago, en una sola tarde, se rompio el
bot dos veces y las dos se detectaron a mano, corriendo el control aparte. Una
fue AGREGAR una regla al prompt para tapar un caso: bajo "vende" de 3/5 a 2/5 y
"no alucina" de 5/5 a 4/5. La otra fue prender el pensamiento del redactor sin
medir: corto el presupuesto a mitad de palabra. Las dos se revirtieron, pero
porque alguien se acordo de mirar. Sin esto, el patron de cinco sesiones
seguidas es el mismo: una sesion nueva encuentra un agujero real, lo tapa, rompe
otra cosa que no mira, y declara verde.

Esto es la aguja del tacometro. Guarda el mejor numero alcanzado en
`banco_pruebas/piso.json` y hace fallar la corrida cuando un numero DURO
empeora. No opina, no interpreta: compara.

LAS CUATRO METRICAS, y por que estas.
El juez que ya existia solo mide invariantes NEGATIVOS: que no mienta sobre el
catalogo. Eso deja ciega la clase de error que mata la venta -contestar de
costado, amurallarse con el dato en la mano, perder la mitad del pedido-. Por
eso hay dos duras y dos blandas:

  DURAS, la compuerta falla si empeoran:
    sin_caida   - el turno no exploto ni cayo al fallback.
    sin_invento - ningun invariante del juez violado.
  BLANDAS, avisan pero no frenan, porque son mas ruidosas:
    completa    - cumplio las expectativas escritas en el guion.
    avanza      - la respuesta mueve la venta: trae un precio o pregunta algo.
                  Un muro honesto -"no tenemos nada"- NO avanza.

EL RUIDO ES REAL Y NO SE TAPA. El modelo no es determinista: con 5 vueltas, un
turno de diferencia son 20 puntos. Por eso la compuerta tiene tolerancia y por
eso el piso guarda con cuantas vueltas se midio. Un piso hecho con 3 vueltas no
autoriza a nadie a declarar nada.

USO:
    python3 banco_pruebas/banco_repetido.py 5 '7?_*.txt'            # compara
    python3 banco_pruebas/banco_repetido.py 5 '7?_*.txt' --fijar-piso
"""
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

ARCHIVO = Path(__file__).with_name("piso.json")

# Cuanto puede bajar una metrica dura sin que la compuerta frene, en puntos
# porcentuales. Con pocas vueltas el ruido del modelo es mayor que esto; el
# reporte lo dice en la cara para que nadie lea un 5% como una regresion.
TOLERANCIA = 5

DURAS = ("sin_caida", "sin_invento")
BLANDAS = ("completa", "avanza")

_RE_PLATA = re.compile(r"\$\s?\d")


def _avanza(texto: str) -> bool:
    """Mueve la venta: da un numero o pregunta algo util. Medido el 2-ago: la
    respuesta honesta "no contamos con productos de origen no chino" pasaba el
    juez como LIMPIA y era una venta perdida con las opciones en la mano."""
    t = texto or ""
    return bool(_RE_PLATA.search(t)) or "?" in t


def metricas(informe: dict) -> dict:
    """Las cuatro tasas sobre TODOS los turnos de todas las vueltas."""
    tot = caidas = inventos = incompletos = quietos = 0
    ms: list[int] = []
    for corridas in informe.values():
        for corrida in corridas:
            for t in corrida:
                tot += 1
                ms.append(t.get("ms") or 0)
                probs = t.get("problemas") or []
                cayo = any(p.startswith("EXCEPCION") or "fallback" in p
                           for p in probs)
                # Una expectativa del guion la escribimos nosotros; un invariante
                # lo dicta el juez. Se cuentan aparte a proposito.
                espera = any(p.startswith(("falta:", "no deberia decir:"))
                             for p in probs)
                if cayo:
                    caidas += 1
                elif any(not p.startswith(("falta:", "no deberia decir:"))
                         for p in probs):
                    inventos += 1
                if espera:
                    incompletos += 1
                if not _avanza(t.get("respuesta", "")):
                    quietos += 1
    pct = lambda malos: round(100 * (tot - malos) / tot, 1) if tot else 0.0
    ordenados = sorted(ms)
    return {
        "turnos": tot,
        "sin_caida": pct(caidas),
        "sin_invento": pct(inventos),
        "completa": pct(incompletos),
        "avanza": pct(quietos),
        "latencia_p50_ms": ordenados[len(ordenados) // 2] if ordenados else 0,
        "latencia_p95_ms": (ordenados[int(len(ordenados) * 0.95) - 1]
                            if len(ordenados) >= 20 else
                            (ordenados[-1] if ordenados else 0)),
    }


def _commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True,
                              timeout=10).stdout.strip() or "?"
    except Exception:
        return "?"


def leer() -> dict:
    if not ARCHIVO.exists():
        return {}
    try:
        return json.loads(ARCHIVO.read_text(encoding="utf-8"))
    except Exception:
        return {}


def fijar(m: dict, guiones: list[str], vueltas: int, modelo: str) -> dict:
    """Graba el piso. Se hace A MANO y a proposito: si el piso se moviera solo
    con cada corrida, una regresion lenta se volveria el piso nuevo y nadie la
    veria nunca."""
    piso = dict(m)
    piso.update({"fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                 "commit": _commit(), "modelo": modelo, "vueltas": vueltas,
                 "guiones": sorted(guiones)})
    ARCHIVO.write_text(json.dumps(piso, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    return piso


def comparar(m: dict, piso: dict) -> dict:
    """Devuelve veredicto y renglones. `frena` True = la corrida tiene que
    fallar."""
    if not piso:
        return {"frena": False, "lineas": [
            "No hay piso guardado todavia. Corre con --fijar-piso para grabar "
            "este resultado como referencia."]}
    lineas, frena = [], False
    if sorted(piso.get("guiones") or []) != sorted(m.get("_guiones") or []):
        lineas.append("AVISO: el piso se midio con OTROS guiones. La "
                      "comparacion es orientativa, no una compuerta.")
    for k in DURAS + BLANDAS:
        antes, ahora = piso.get(k), m.get(k)
        if antes is None or ahora is None:
            continue
        delta = round(ahora - antes, 1)
        dura = k in DURAS
        peor = delta < -TOLERANCIA
        marca = "OK " if delta >= 0 else ("BAJA" if peor else "~ ")
        if peor and dura:
            frena = True
            marca = "FRENA"
        lineas.append(f"  {marca:<6} {k:<12} piso {antes:>5}%  ahora "
                      f"{ahora:>5}%  ({delta:+})")
    if piso.get("vueltas", 0) < 5:
        lineas.append(f"AVISO: el piso se fijo con solo {piso.get('vueltas')} "
                      f"vueltas. Ruido alto, no declarar nada con eso.")
    return {"frena": frena, "lineas": lineas}


def reporte(m: dict, piso: dict) -> str:
    c = comparar(m, piso)
    out = ["", "=" * 62,
           f"METRICAS  ({m['turnos']} turnos)   "
           f"p50 {m['latencia_p50_ms']}ms  p95 {m['latencia_p95_ms']}ms",
           "=" * 62]
    for k in DURAS:
        out.append(f"  DURA   {k:<12} {m[k]}%")
    for k in BLANDAS:
        out.append(f"  blanda {k:<12} {m[k]}%")
    if piso:
        out += ["", f"CONTRA EL PISO del {piso.get('fecha')} "
                    f"commit {piso.get('commit')} modelo {piso.get('modelo')}:"]
    out += c["lineas"]
    if c["frena"]:
        out += ["", "*** REGRESION EN UNA METRICA DURA. No se declara verde, "
                    "se revierte o se explica con el numero al lado. ***"]
    return "\n".join(out)

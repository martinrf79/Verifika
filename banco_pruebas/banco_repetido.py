"""
BANCO REPETIDO — el portón que mide lo que el verde nunca midió.

POR QUE EXISTE. Hasta hoy convivian dos cosas que se confundian:
  - 398 tests offline que NUNCA le hablan al modelo. Prueban la calculadora, el
    certificador, los candados. Dan verde siempre, y ese verde no dice nada
    sobre como contesta el bot.
  - un banco vivo que corre UNA vez cada guion. Y el modelo no es determinista:
    la misma pregunta, otra eleccion de herramientas. Una corrida sale perfecta
    y la siguiente rompe. Por eso el banco daba bien y WhatsApp daba mal con la
    MISMA pregunta: no eran dos sistemas distintos, era una muestra de uno.

QUE HACE. Corre cada guion N veces por el camino REAL de produccion -el mismo
que atiende el webhook- y reporta TASA DE FALLO por turno. Un guion que pasa 3
de 5 no es verde: es un 40 por ciento de fallo, y eso es exactamente lo que el
cliente ve en WhatsApp.

QUE JUZGA, en tres capas, de la mas dura a la mas blanda:
  1. el JUEZ de invariantes (`juez.py`): stock contradicho, promesa prohibida,
     narracion interna, marcador sin estampar.
  2. los CANDADOS del hub, leidos del log del turno: plata inventada, cuenta
     retipeada, cobro inventado, JSON filtrado, herramientas recortadas.
  3. las EXPECTATIVAS del guion (`> contiene:` / `> no_contiene:`).

Uso:
    export GEMINI_API_KEY=$GEMINI_API_KEY_PROD
    python3 banco_pruebas/banco_repetido.py            # los guiones 70 al 79, 3 vueltas
    python3 banco_pruebas/banco_repetido.py 5 70_*.txt # 5 vueltas, guiones elegidos

Deja el reporte en banco_pruebas/corridas/.
"""
import asyncio
import datetime as _dt
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from banco_pruebas import clon_produccion, juez  # noqa: E402
from banco_pruebas.puntaje import leer_guion  # noqa: E402

GUIONES = Path(__file__).resolve().parent / "guiones"
CORRIDAS = Path(__file__).resolve().parent / "corridas"
PAUSA_S = float(os.getenv("BANCO_PAUSA_S", "2"))

# Los candados del hub. Si alguno dispara, el turno tuvo que ser corregido por
# el codigo: no es un fallo del cliente, pero SI es una senal de que el modelo
# se salio del carril. Se cuentan aparte de los errores duros.
_CANDADOS = {
    "hub_venta_plata_inventada": "plata inventada",
    "hub_venta_cuenta_retipeada": "cuenta retipeada",
    "hub_venta_cobro_inventado": "cobro inventado",
    "hub_venta_json_filtrado": "json filtrado",
    "hub_venta_bloque_repuesto": "bloque repuesto",
    "hub_venta_pedidos_recortados": "herramientas recortadas",
}


class _Espia:
    """Escucha los eventos del turno sin tocar el codigo vivo. Los candados no
    se deducen del texto: se leen del log que ya emite el hub."""

    def __init__(self):
        self.eventos: list[str] = []

    def __enter__(self):
        from app.core import hub_venta as HV
        self._log = HV.log
        espia = self

        class _Proxy:
            def __getattr__(self, nivel):
                real = getattr(espia._log, nivel)

                def _cap(evento=None, **kw):
                    if evento:
                        espia.eventos.append(str(evento))
                    return real(evento, **kw) if evento else real(**kw)
                return _cap
        HV.log = _Proxy()
        return self

    def __exit__(self, *a):
        from app.core import hub_venta as HV
        HV.log = self._log
        return False

    def candados(self) -> list[str]:
        return sorted({_CANDADOS[e] for e in self.eventos if e in _CANDADOS})


def _expectativas(turno: dict, respuesta: str) -> list[str]:
    """Las expectativas del guion. Un grupo con `|` son alternativas: alcanza
    con que aparezca una."""
    fallos = []
    baja = (respuesta or "").lower()
    for alternativas in turno.get("contiene", []):
        if not any(a.lower() in baja for a in alternativas):
            fallos.append("falta: " + " | ".join(alternativas))
    for alternativas in turno.get("no_contiene", []):
        for a in alternativas:
            if a.lower() in baja:
                fallos.append("no deberia decir: " + a)
    return fallos


async def _una_vuelta(nombre: str, turnos: list, vuelta: int) -> list[dict]:
    """Una pasada completa del guion. Devuelve un dict por turno."""
    user = f"rep_{nombre}_{vuelta}_{int(time.time())}"
    salida = []
    for i, turno in enumerate(turnos, 1):
        t0 = time.time()
        with _Espia() as espia:
            try:
                partes = await clon_produccion.turno(user, turno["mensaje"])
                texto = "\n".join(partes)
                error_duro = None
            except Exception as e:  # noqa: BLE001 — el banco reporta, no rompe
                texto, error_duro = "", f"{type(e).__name__}: {str(e)[:120]}"
        problemas = []
        if error_duro:
            problemas.append("EXCEPCION " + error_duro)
        elif clon_produccion.es_fallback(texto):
            problemas.append("cayo al fallback")
        else:
            problemas += juez.juzgar(texto, "verifika_prod", turno["mensaje"])
            problemas += _expectativas(turno, texto)
        salida.append({
            "n": i, "mensaje": turno["mensaje"], "respuesta": texto,
            "ms": int((time.time() - t0) * 1000),
            "problemas": problemas, "candados": espia.candados(),
        })
        await asyncio.sleep(PAUSA_S)
    return salida


async def correr(nombres: list[str], vueltas: int) -> dict:
    clon_produccion.instalar()
    informe: dict = {}
    for path in nombres:
        turnos = leer_guion(Path(path).read_text(encoding="utf-8"))
        nombre = Path(path).stem
        print(f"\n=== {nombre}  ({len(turnos)} turnos x {vueltas} vueltas)")
        corridas = []
        for v in range(1, vueltas + 1):
            r = await _una_vuelta(nombre, turnos, v)
            fallados = sum(1 for t in r if t["problemas"])
            print(f"  vuelta {v}: {fallados}/{len(r)} turnos con problema"
                  + (f"  candados: {sorted({c for t in r for c in t['candados']})}"
                     if any(t["candados"] for t in r) else ""))
            for t in r:
                if t["problemas"]:
                    print(f"    T{t['n']} {t['mensaje'][:52]!r}")
                    for p in t["problemas"][:4]:
                        print(f"       - {p}")
            corridas.append(r)
        informe[nombre] = corridas
    return informe


def _percentil(valores: list[int], p: float) -> int:
    """p50 y p95 de la latencia por turno. Sin numpy: son cuatrocientos numeros."""
    if not valores:
        return 0
    ord_ = sorted(valores)
    i = min(len(ord_) - 1, int(round(p * (len(ord_) - 1))))
    return ord_[i]


def _latencias(informe: dict) -> list[int]:
    return [t["ms"] for c in informe.values() for corrida in c for t in corrida]


def _reporte(informe: dict, vueltas: int) -> str:
    lineas = ["# BANCO REPETIDO — " + _dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
              "", f"{vueltas} vueltas por guion, camino vivo de produccion.", ""]
    total_turnos = total_malos = 0
    lineas.append("| guion | turno | fallo | detalle mas comun |")
    lineas.append("|---|---|---|---|")
    for nombre, corridas in informe.items():
        por_turno = defaultdict(list)
        for corrida in corridas:
            for t in corrida:
                por_turno[t["n"]].append(t)
        for n, ts in sorted(por_turno.items()):
            malos = [t for t in ts if t["problemas"]]
            total_turnos += len(ts)
            total_malos += len(malos)
            pct = int(100 * len(malos) / max(1, len(ts)))
            detalle = malos[0]["problemas"][0][:60] if malos else ""
            marca = "" if pct == 0 else (" ⚠" if pct < 50 else " ✗")
            lineas.append(f"| {nombre} | T{n} | {pct}%{marca} | {detalle} |")
    pct_total = int(100 * total_malos / max(1, total_turnos))
    ms = _latencias(informe)
    lineas += ["", f"**TASA DE FALLO GLOBAL: {pct_total}% "
                   f"({total_malos} de {total_turnos} turnos)**", "",
               f"**LATENCIA por turno: p50 {_percentil(ms, .50)}ms, "
               f"p95 {_percentil(ms, .95)}ms**", ""]
    lineas.append("## Turnos con problema, texto completo")
    for nombre, corridas in informe.items():
        for v, corrida in enumerate(corridas, 1):
            for t in corrida:
                if not t["problemas"]:
                    continue
                lineas += [f"\n### {nombre} vuelta {v} turno {t['n']}",
                           f"**Cliente:** {t['mensaje']}", "",
                           "**Bot:**", "```", t["respuesta"][:1200], "```",
                           "Problemas: " + "; ".join(t["problemas"]),
                           ("Candados: " + ", ".join(t["candados"])
                            if t["candados"] else "")]
    return "\n".join(lineas)


def main():
    args = [a for a in sys.argv[1:]]
    vueltas = 3
    if args and re.fullmatch(r"\d+", args[0]):
        vueltas = int(args.pop(0))
    if args:
        nombres = []
        for a in args:
            # se acepta el nombre pelado, el patron o la ruta completa: el que
            # corre el banco no tiene por que acordarse de la carpeta.
            if Path(a).exists():
                nombres.append(a)
            else:
                nombres += [str(p) for p in sorted(GUIONES.glob(a))]
    else:
        nombres = [str(p) for p in sorted(GUIONES.glob("7?_*.txt"))]
    if not nombres:
        print("sin guiones que correr")
        return 1
    informe = asyncio.run(correr(sorted(nombres), vueltas))
    CORRIDAS.mkdir(exist_ok=True)
    destino = CORRIDAS / (_dt.datetime.now().strftime("%Y%m%d_%H%M")
                          + "_repetido.md")
    destino.write_text(_reporte(informe, vueltas), encoding="utf-8")
    print(f"\nreporte: {destino}")
    malos = sum(1 for c in informe.values() for corrida in c
                for t in corrida if t["problemas"])
    todos = sum(1 for c in informe.values() for corrida in c for _ in corrida)
    print(f"TASA DE FALLO GLOBAL: {int(100 * malos / max(1, todos))}% "
          f"({malos} de {todos} turnos)")
    ms = _latencias(informe)
    print(f"LATENCIA: p50 {_percentil(ms, .50)}ms, p95 {_percentil(ms, .95)}ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

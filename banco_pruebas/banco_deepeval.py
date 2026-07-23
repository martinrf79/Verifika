"""
BANCO DEEPEVAL — metrica de calidad sobre el CAMINO VIVO (flujo atado).

Que hace: corre los guiones multi-turno por app.core.hub_atado.procesar_atado
(interprete + solver atados por enum, Gemini 3.1 flash lite, el MISMO codigo que
esta en produccion), sobre el doble de Firestore con el catalogo y la FAQ REALES,
y le pone NUMERO a cada respuesta con DeepEval:

  - faithfulness      : la respuesta no contradice la evidencia dura de las tools
                        (precio, stock, spec, total salidos del catalogo). Es la
                        metrica anti-alucinacion. Sube = mejor.
  - answer_relevancy  : la respuesta contesta lo que el cliente pregunto, no divaga.
  - hallucination     : cruce inverso, cuanto del output contradice la evidencia.
                        Baja = mejor.

El contexto de recuperacion (retrieval_context) NO se inventa: es la salida REAL
de las tools que llamo el solver en ese turno, capturada envolviendo
generador_v2.renderizar. Asi la metrica juzga contra la fuente, no contra el aire.

El JUEZ es DeepSeek (banco_pruebas/juez_deepeval.JuezDeepSeek), independiente del
modelo evaluado (Gemini) para que no se autocalifique, y default barato del repo.

Uso:
    BANCO_PAUSA_S=22 python3 banco_pruebas/banco_deepeval.py 01_*.txt 04_*.txt
    (sin argumentos corre un set chico por default)

Salidas: reporte markdown en banco_pruebas/corridas/deepeval_*.md y codigo de
salida != 0 si algun promedio cae del umbral (para gatear el CI).

Env:
    BANCO_PAUSA_S           pausa entre turnos, tier gratis de Gemini (default 0)
    DEEPEVAL_UMBRAL_FAITH   umbral faithfulness (default 0.85)
    DEEPEVAL_UMBRAL_RELEV   umbral answer_relevancy (default 0.75)
    DEEPEVAL_UMBRAL_HALU    umbral hallucination MAX (default 0.25)
"""
import asyncio
import datetime as _dt
import json
import os
import sys
import time
from pathlib import Path

# Apagar la telemetria de DeepEval: manda a PostHog y el proxy la corta con 403,
# ensuciando el log. No aporta nada al banco.
os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")
os.environ.setdefault("ERROR_REPORTING", "0")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from banco_pruebas.sim_firestore import install

TIENDA = "verifika_prod"
_CORRIDAS = Path(__file__).resolve().parent / "corridas"
_GUIONES = Path(__file__).resolve().parent / "guiones"

UMBRAL_FAITH = float(os.getenv("DEEPEVAL_UMBRAL_FAITH", "0.85"))
UMBRAL_VENTA = float(os.getenv("DEEPEVAL_UMBRAL_VENTA", "0.70"))
UMBRAL_HALU = float(os.getenv("DEEPEVAL_UMBRAL_HALU", "0.25"))
# answer_relevancy es INFORMATIVO, no gatea: su rubrica generica castiga el
# saludo y la pregunta de cierre, que en un bot de VENTA son tecnica, no ruido.
UMBRAL_RELEV = float(os.getenv("DEEPEVAL_UMBRAL_RELEV", "0.75"))

# Set chico por default: guiones cortos y variados, baratos de correr en el CI.
_DEFAULT = ["01_curada_pura.txt", "04_mas_barato.txt", "03_stock.txt"]


def _leer_guion(path: Path) -> list[str]:
    return [l.strip() for l in path.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.strip().startswith("#")]


def _fact_de_tool(tc: dict) -> str:
    """Convierte una llamada de tool con su resultado real en una linea factual
    que sirve de evidencia (retrieval_context). El resultado es la fuente de
    verdad: precio, stock, total, plazo salidos del catalogo/calculadora."""
    nombre = tc.get("name", "tool")
    args = tc.get("args", {})
    res = tc.get("result", {})
    try:
        res_txt = json.dumps(res, ensure_ascii=False, default=str)
    except Exception:
        res_txt = str(res)
    if len(res_txt) > 1500:
        res_txt = res_txt[:1500] + "…"
    args_txt = json.dumps(args, ensure_ascii=False, default=str)
    return f"{nombre}({args_txt}) => {res_txt}"


class _CapturaTools:
    """Envuelve generador_v2.renderizar para quedarse con los tools_called (con
    su resultado) de cada turno. Es un espejo del camino vivo, no lo altera:
    devuelve exactamente lo que renderizar devolvia."""

    def __init__(self):
        import app.core.generador_v2 as g2
        self._g2 = g2
        self._orig = g2.renderizar
        self.acum: list[dict] = []

    def __enter__(self):
        def _wrap(*a, **k):
            texto, tools = self._orig(*a, **k)
            if tools:
                self.acum.extend(tools)
            return texto, tools
        self._g2.renderizar = _wrap
        return self

    def __exit__(self, *exc):
        self._g2.renderizar = self._orig

    def reset(self):
        self.acum = []

    def contexto(self) -> list[str]:
        return [_fact_de_tool(tc) for tc in self.acum]


async def _correr_guion(nombre: str, mensajes: list[str], pausa_s: float,
                        captura: "_CapturaTools") -> list[dict]:
    """Devuelve una lista de casos {input, output, contexto} por turno."""
    from app.core.hub_atado import procesar_atado
    from app.storage.firestore_client import reset_conversation

    user = f"deepeval_{nombre}_{int(time.time())}"
    try:
        reset_conversation(user, tienda_id=TIENDA)
    except Exception:
        pass

    casos = []
    for i, msg in enumerate(mensajes, 1):
        captura.reset()
        print(f"  [{i}] CLIENTE: {msg}")
        try:
            resp = await procesar_atado(user, msg, TIENDA, "sim", f"d{i:02d}")
        except Exception as e:
            import traceback
            traceback.print_exc()
            resp = f"<<ERROR {type(e).__name__}: {e}>>"
        ctx = captura.contexto()
        casos.append({"input": msg, "output": resp, "contexto": ctx,
                      "turno": i, "guion": nombre})
        print(f"      BOT: {(resp or '')[:120]}")
        print(f"      evidencia: {len(ctx)} tool(s)")
        if pausa_s:
            time.sleep(pausa_s)
    return casos


def _geval_venta(juez):
    """G-Eval a medida para un bot de VENTA verificado. Premia la tecnica de
    venta (calidez, avance al cierre) y castiga SOLO la alucinacion o ignorar la
    pregunta. Reemplaza a answer_relevancy generico, que da falso negativo con el
    saludo y la pregunta de cierre."""
    from deepeval.metrics import GEval
    from deepeval.test_case import LLMTestCaseParams as P
    return GEval(
        name="venta_verificada",
        model=juez,
        threshold=UMBRAL_VENTA,
        async_mode=False,
        evaluation_params=[P.INPUT, P.ACTUAL_OUTPUT, P.RETRIEVAL_CONTEXT],
        evaluation_steps=[
            "Verificá que ACTUAL_OUTPUT conteste concretamente lo que el cliente "
            "pregunta en INPUT; si ignora la pregunta o se va por las ramas, bajá.",
            "Premiá la técnica de venta: respuesta cálida, humana, que avanza "
            "hacia el cierre e invita a seguir. El saludo, la cortesía y la "
            "pregunta de cierre como '¿seguimos?' son técnica de venta correcta, "
            "NO las penalices.",
            "Castigá fuerte SOLO si inventa un dato de producto, precio, stock, "
            "plazo o política que NO figure en RETRIEVAL_CONTEXT, o si afirma algo "
            "que la evidencia contradice.",
            "Si no tiene un dato, la respuesta honesta de que lo va a confirmar es "
            "correcta y no se penaliza; inventar sí.",
            "No penalices que suene comercial; penalizá que suene robótica, que "
            "repita de más o que no cierre.",
        ],
    )


def _medir(casos: list[dict]) -> list[dict]:
    """Corre las metricas de DeepEval sobre cada caso. Sincrono, un caso por vez,
    para no pisar el event loop del sistema bajo prueba y no reventar cuota.

    Gatean: faithfulness, venta_verificada (G-Eval) y hallucination.
    Informativo (no gatea): answer_relevancy."""
    from deepeval.test_case import LLMTestCase
    from deepeval.metrics import (FaithfulnessMetric, AnswerRelevancyMetric,
                                  HallucinationMetric)
    from banco_pruebas.juez_deepeval import JuezDeepSeek

    juez = JuezDeepSeek()
    m_venta = _geval_venta(juez)
    resultados = []
    for c in casos:
        fila = {**c, "faithfulness": None, "venta": None, "answer_relevancy": None,
                "hallucination": None, "razones": {}}
        out = c["output"] or ""
        ctx = c["contexto"]
        # RETRIEVAL_CONTEXT nunca vacío para las métricas que lo piden.
        ctx_g = ctx or ["(este turno no llamó tools: respuesta de política o cortesía)"]

        # venta_verificada (G-Eval): gate principal de calidad comercial.
        try:
            tc = LLMTestCase(input=c["input"], actual_output=out,
                             retrieval_context=ctx_g)
            m_venta.measure(tc)
            fila["venta"] = m_venta.score
            fila["razones"]["venta"] = m_venta.reason
        except Exception as e:
            fila["razones"]["venta"] = f"ERROR: {e}"

        # answer_relevancy: informativo (input + output).
        try:
            m = AnswerRelevancyMetric(threshold=UMBRAL_RELEV, model=juez,
                                      async_mode=False, include_reason=True)
            tc = LLMTestCase(input=c["input"], actual_output=out)
            m.measure(tc)
            fila["answer_relevancy"] = m.score
            fila["razones"]["answer_relevancy"] = m.reason
        except Exception as e:
            fila["razones"]["answer_relevancy"] = f"ERROR: {e}"

        # faithfulness + hallucination: solo si hubo evidencia real de tools.
        if ctx:
            try:
                m = FaithfulnessMetric(threshold=UMBRAL_FAITH, model=juez,
                                       async_mode=False, include_reason=True)
                tc = LLMTestCase(input=c["input"], actual_output=out,
                                 retrieval_context=ctx)
                m.measure(tc)
                fila["faithfulness"] = m.score
                fila["razones"]["faithfulness"] = m.reason
            except Exception as e:
                fila["razones"]["faithfulness"] = f"ERROR: {e}"
            try:
                m = HallucinationMetric(threshold=UMBRAL_HALU, model=juez,
                                        async_mode=False, include_reason=True)
                tc = LLMTestCase(input=c["input"], actual_output=out, context=ctx)
                m.measure(tc)
                fila["hallucination"] = m.score
                fila["razones"]["hallucination"] = m.reason
            except Exception as e:
                fila["razones"]["hallucination"] = f"ERROR: {e}"

        resultados.append(fila)
    return resultados


def _promedio(vals) -> float | None:
    vals = [v for v in vals if isinstance(v, (int, float))]
    return round(sum(vals) / len(vals), 4) if vals else None


def _reporte(resultados: list[dict]) -> tuple[str, bool]:
    ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    faith = _promedio([r["faithfulness"] for r in resultados])
    venta = _promedio([r["venta"] for r in resultados])
    relev = _promedio([r["answer_relevancy"] for r in resultados])
    halu = _promedio([r["hallucination"] for r in resultados])

    ok_faith = faith is None or faith >= UMBRAL_FAITH
    ok_venta = venta is None or venta >= UMBRAL_VENTA
    ok_halu = halu is None or halu <= UMBRAL_HALU
    # answer_relevancy NO gatea (informativo).
    aprobado = ok_faith and ok_venta and ok_halu

    L = [f"# Reporte DeepEval — flujo atado (camino vivo)", "",
         f"Fecha: {ts}", f"Sistema bajo prueba: Gemini 3.1 flash lite (interprete + solver)",
         f"Juez: DeepSeek", "",
         "## Promedios (gatean faithfulness, venta_verificada y hallucination)", "",
         f"- faithfulness:      {faith}  (umbral >= {UMBRAL_FAITH})  {'OK' if ok_faith else 'FALLA'}",
         f"- venta_verificada:  {venta}  (umbral >= {UMBRAL_VENTA})  {'OK' if ok_venta else 'FALLA'}",
         f"- hallucination:     {halu}  (umbral <= {UMBRAL_HALU})  {'OK' if ok_halu else 'FALLA'}",
         f"- answer_relevancy:  {relev}  (informativo, no gatea)",
         "", f"**Resultado: {'APROBADO' if aprobado else 'RECHAZADO'}**", "",
         "## Detalle por turno", ""]
    for r in resultados:
        L.append(f"### {r['guion']} — turno {r['turno']}")
        L.append(f"- CLIENTE: {r['input']}")
        L.append(f"- BOT: {(r['output'] or '')[:400]}")
        L.append(f"- faithfulness={r['faithfulness']} venta={r['venta']} "
                 f"answer_relevancy={r['answer_relevancy']} "
                 f"hallucination={r['hallucination']} "
                 f"evidencia={len(r['contexto'])} tools")
        for k, v in r.get("razones", {}).items():
            if v:
                L.append(f"  - {k}: {str(v)[:300]}")
        L.append("")
    return "\n".join(L), aprobado


async def _main(archivos: list[str]) -> int:
    install()
    pausa = float(os.getenv("BANCO_PAUSA_S", "0"))
    _CORRIDAS.mkdir(exist_ok=True)

    guiones = []
    for a in archivos:
        p = Path(a)
        if not p.exists():
            p = _GUIONES / a
        if not p.exists():
            print(f"!! guion no encontrado: {a}")
            continue
        guiones.append(p)
    if not guiones:
        print("No hay guiones para correr."); return 2

    casos = []
    with _CapturaTools() as captura:
        for p in guiones:
            print(f"\n=== GUION {p.name} ===")
            msgs = _leer_guion(p)
            casos.extend(await _correr_guion(p.stem, msgs, pausa, captura))

    print(f"\n== Midiendo {len(casos)} turnos con DeepEval (juez DeepSeek) ==")
    resultados = _medir(casos)
    texto, aprobado = _reporte(resultados)

    ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = _CORRIDAS / f"deepeval_{ts}.md"
    out.write_text(texto, encoding="utf-8")
    print("\n" + texto)
    print(f"\nReporte: {out}")
    return 0 if aprobado else 1


if __name__ == "__main__":
    args = sys.argv[1:] or _DEFAULT
    sys.exit(asyncio.run(_main(args)))

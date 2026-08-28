"""
BANCO DE LA LLAMADA UNO — ¿el modelo DECLARA bien, con registrar_pedido?

QUE MIDE. Una request por mensaje. No redacta, no encadena, no arma
presupuesto. El modelo ve una sola herramienta y no elige que buscar: deja
por escrito lo que entendio. Este banco mira ESA declaracion.

Las doce preguntas son las mismas de cuando el modelo elegia tool. Cambio el
blanco, no la pregunta: "¿entendio que era una condicion de origen?" se
afirma sobre lo declarado, no sobre el nombre de una herramienta.

    python3 banco_pruebas/banco_llamada_uno.py
"""
import asyncio
import os
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from banco_pruebas import clon_produccion  # noqa: E402

DETALLE = clon_produccion.instalar()

from app.core import hub_venta as HV  # noqa: E402

TIENDA = "verifika_prod"

# Cada caso: el mensaje y QUE tiene que aparecer en lo DECLARADO.
# `senales` son subcadenas que tienen que estar en el blob de la declaracion.
CASOS = [
    ("Necesito el mouse que menos partes chinas tenga, pero que no sea "
     "Logitech",
     {"senales": {"mouse", "china", "logitech"}}),
    ("Mostrame el mouse mas barato que tengas",
     {"senales": {"mouse", "barato"}}),
    ("Cual es el mouse mas liviano que tengas para viajar?",
     {"senales": {"mouse", "livian"}}),
    ("Que teclado tiene la garantia mas larga?",
     {"senales": {"teclado", "garantia"}}),
    ("Busco unos auriculares de hasta 80 mil pesos",
     {"senales": {"auricular", "80"}}),
    ("Cuantos productos tenes que no se fabriquen en China?",
     {"senales": {"china"}}),
    ("Cuantos mouse blancos tenes?",
     {"senales": {"mouse", "blanc"}}),
    ("Cual es el producto mas caro de toda la tienda?",
     {"senales": {"caro"}}),
    ("Que marcas manejas?",
     {"senales": {"marca"}}),
    ("Un mouse inalambrico negro de menos de 120 gramos y que salga menos de "
     "50 mil",
     {"senales": {"mouse", "inalambric", "negro", "50"}}),
    ("Tengo una notebook Lenovo IdeaPad 3, que memoria RAM le sirve?",
     {"una_de": [{"senales": {"ram", "lenovo"}},
                 {"senales": {"ram", "notebook"}},
                 {"senales": {"memoria", "lenovo"}},
                 {"senales": {"memoria", "notebook"}},
                 {"compatibilidad": True}]}),
    ("Quiero un teclado inalambrico para la oficina",
     {"senales": {"teclado", "inalambric"}}),
]


def _declarado(pedidos: list) -> dict | None:
    for p in pedidos:
        if p.get("nombre") == "registrar_pedido":
            return p.get("args") or {}
    return None


def _join(xs) -> str:
    partes = []
    for x in xs or []:
        if isinstance(x, dict):
            partes.extend(str(v) for v in x.values()
                          if v not in (None, "", [], False))
        else:
            partes.append(str(x))
    return " ".join(partes).lower()


def _blob(d: dict) -> str:
    return " ".join([
        _join(d.get("items")),
        _join(d.get("restricciones")),
        _join(d.get("atributos")),
        _join(d.get("compatibilidad")),
        _join(d.get("stock")),
        _join(d.get("temas")),
    ])


def _resumen(d: dict | None) -> str:
    if d is None:
        return "NO DECLARO"
    partes = []
    for it in (d.get("items") or []):
        if isinstance(it, dict) and it.get("que"):
            partes.append(f"item={it.get('que')!s:.28}")
    for r in (d.get("restricciones") or []):
        partes.append(f"rest={str(r)[:28]!r}")
    for c in (d.get("compatibilidad") or []):
        if isinstance(c, dict):
            partes.append(f"compat={c.get('que')}->{c.get('para')}")
    for a in (d.get("atributos") or []):
        if isinstance(a, dict):
            partes.append(f"attr={a.get('de')}.{a.get('campo')}")
    for s in (d.get("stock") or []):
        partes.append(f"stock={s}")
    for t in (d.get("temas") or []):
        partes.append(f"tema={t}")
    return " | ".join(partes) or "(declaro vacio)"


def _evaluar(d: dict | None, esperado: dict) -> tuple:
    if esperado.get("una_de"):
        motivos = []
        for alt in esperado["una_de"]:
            ok, motivo = _evaluar(d, alt)
            if ok:
                return True, ""
            motivos.append(motivo)
        return False, " / ".join(motivos)
    if d is None:
        return False, "no llamo a registrar_pedido"
    blob = _blob(d)
    if esperado.get("compatibilidad"):
        if not (d.get("compatibilidad") or []):
            return False, "sin compatibilidad declarada"
    for s in esperado.get("senales") or ():
        if s.lower() not in blob:
            return False, f"falta {s!r} en {blob[:80]!r}"
    return True, ""


async def main():
    print(f"clave: {DETALLE.get('clave')} | modelo: {DETALLE.get('solver_model')}")
    print(f"decisor reasoning: {os.getenv('DECISOR_REASONING', 'low')} | "
          f"redactor reasoning: {os.getenv('REDACTOR_REASONING', 'low')}")
    print("=" * 78)
    verdes = 0
    declararon = 0
    for mensaje, esperado in CASOS:
        pedidos, texto = await HV._pedir_herramientas(
            "Verifika", "", [], mensaje, TIENDA, "banco1")
        d = _declarado(pedidos)
        if d is not None:
            declararon += 1
        ok, motivo = _evaluar(d, esperado)
        verdes += 1 if ok else 0
        print(f"\n[{'OK ' if ok else 'MAL'}] {mensaje[:64]}")
        print(f"   declaro: {_resumen(d)}")
        if not ok:
            print(f"   falta : {motivo}")
        await asyncio.sleep(float(os.getenv("BANCO_PAUSA_S", "2")))
    print("\n" + "=" * 78)
    print(f"LLAMADA UNO — {verdes} de {len(CASOS)} en verde "
          f"(control: {declararon} de {len(CASOS)} llamaron registrar_pedido)")
    return 0 if verdes == len(CASOS) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

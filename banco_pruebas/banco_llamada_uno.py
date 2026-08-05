"""
BANCO DE LA LLAMADA UNO — ¿el modelo pide bien, con el esquema nuevo?

QUE MIDE Y POR QUE ES LA PRUEBA MAS BARATA QUE HAY. El banco de candidatos mide
el TECHO: que devuelve el codigo cuando la llamada es perfecta. Este mide la
otra mitad y solo esa: que llamada PIDE el modelo. No redacta, no encadena
rondas, no arma presupuesto. Una request por mensaje.

Existe porque el 5-ago se colapsaron las cuatro puertas de `buscar_productos`:
`orden`, `tope_precio` y `excluir` dejaron de ser argumentos y ahora todo es
`filtros` mas `ordenar_por`. El modelo ve un esquema distinto al que venia
usando, y eso NO se puede saber sin gastar tokens. Es el unico riesgo real del
cambio y esta es la forma mas barata de medirlo.

    BANCO_CLAVE_PAGA=true python3 banco_pruebas/banco_llamada_uno.py
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

# Cada caso: el mensaje del cliente y QUE tiene que aparecer en el pedido para
# considerarlo bien. Se chequea la FORMA de la llamada, no la respuesta.
CASOS = [
    # ── lo que antes era `excluir` ─────────────────────────────────────────
    ("Necesito el mouse que menos partes chinas tenga, pero que no sea "
     "Logitech",
     {"herramienta": "buscar_productos", "operadores": {"no_contiene"},
      "campos_entre": {"pais_fabricacion", "pais_marca", "origen", "marca"}}),
    # ── lo que antes era `orden: barato` ───────────────────────────────────
    ("Mostrame el mouse mas barato que tengas",
     {"herramienta": "buscar_productos",
      "ordenar_por": {"precio_ars"}, "direccion": "min"}),
    # ── lo que antes NO TENIA PUERTA ───────────────────────────────────────
    ("Cual es el mouse mas liviano que tengas para viajar?",
     {"herramienta": "buscar_productos",
      "ordenar_por": {"peso_gramos"}, "direccion": "min"}),
    # El extremo de un campo que no es el precio se puede pedir por las DOS
    # puertas: como busqueda ordenada o como agregado sobre el catalogo. Las
    # dos son correctas; lo que no puede pasar es que no exista ninguna.
    ("Que teclado tiene la garantia mas larga?",
     {"herramienta": None,
      "una_de": [{"herramienta": "buscar_productos",
                  "ordenar_por": {"garantia_meses"}, "direccion": "max"},
                 {"herramienta": "consultar_catalogo", "operacion": "el_mayor",
                  "campos_entre": {"garantia_meses"}}]}),
    # ── lo que antes era `tope_precio` ─────────────────────────────────────
    ("Busco unos auriculares de hasta 80 mil pesos",
     {"herramienta": "buscar_productos", "operadores": {"menor"},
      "campos_entre": {"precio_ars"}}),
    # ── el agregado, ahora con condicion ───────────────────────────────────
    ("Cuantos productos tenes que no se fabriquen en China?",
     {"herramienta": "consultar_catalogo", "operacion": "contar"}),
    ("Cuantos mouse blancos tenes?",
     {"herramienta": "consultar_catalogo", "operacion": "contar",
      "campos_entre": {"color"}}),
    ("Cual es el producto mas caro de toda la tienda?",
     {"herramienta": "consultar_catalogo", "operacion": "mas_caro"}),
    ("Que marcas manejas?",
     {"herramienta": "consultar_catalogo", "operacion": "valores"}),
    # ── condiciones combinadas, que antes no se podian pedir juntas ────────
    ("Un mouse inalambrico negro de menos de 120 gramos y que salga menos de "
     "50 mil",
     {"herramienta": "buscar_productos", "minimo_filtros": 3}),
    # ── producto contra producto ───────────────────────────────────────────
    ("Tengo una notebook Lenovo IdeaPad 3, que memoria RAM le sirve?",
     {"herramienta": None,
      "una_de": [{"herramienta": "buscar_productos"},
                 {"herramienta": "ver_compatibilidad"}]}),
    # ── la descripcion, que ahora ordena por relevancia ────────────────────
    ("Quiero un teclado inalambrico para la oficina",
     {"herramienta": "buscar_productos", "con_descripcion": True}),
]


def _resumen(pedidos: list) -> str:
    fuera = []
    for p in pedidos:
        a = p.get("args") or {}
        partes = [p["nombre"]]
        if a.get("categoria"):
            partes.append(f"cat={a['categoria']}")
        if a.get("descripcion"):
            partes.append(f"desc={str(a['descripcion'])[:28]!r}")
        if a.get("operacion"):
            partes.append(f"op={a['operacion']}")
        if a.get("campo"):
            partes.append(f"campo={a['campo']}")
        for f in (a.get("filtros") or []):
            partes.append(f"[{f.get('campo')} {f.get('operador')} "
                          f"{f.get('valor')}]")
        if a.get("ordenar_por"):
            partes.append(f"orden={a['ordenar_por']} {a.get('direccion', '')}")
        fuera.append(" ".join(partes))
    return " | ".join(fuera) or "NO PIDIO NADA"


def _evaluar(pedidos: list, esperado: dict) -> tuple:
    if esperado.get("una_de"):
        motivos = []
        for alt in esperado["una_de"]:
            ok, motivo = _evaluar(pedidos, alt)
            if ok:
                return True, ""
            motivos.append(f"{alt['herramienta']}: {motivo}")
        return False, " / ".join(motivos)
    del_tipo = [p for p in pedidos
                if p["nombre"] == esperado.get("herramienta")]
    if not del_tipo:
        return False, f"no llamo a {esperado.get('herramienta')}"
    args = {}
    for p in del_tipo:
        for k, v in (p.get("args") or {}).items():
            if v not in (None, "", []):
                args.setdefault(k, v)
        filtros = (p.get("args") or {}).get("filtros") or []
        args.setdefault("filtros", [])
        args["filtros"] = (args["filtros"] or []) + filtros
    filtros = args.get("filtros") or []
    campos = {str(f.get("campo")) for f in filtros}
    operadores = {str(f.get("operador")) for f in filtros}

    if "operacion" in esperado and args.get("operacion") != esperado["operacion"]:
        return False, f"operacion={args.get('operacion')}"
    if "operadores" in esperado and not (esperado["operadores"] & operadores):
        return False, f"operadores={sorted(operadores) or 'sin filtros'}"
    if "campos_entre" in esperado and not (esperado["campos_entre"] & campos) \
            and str(args.get("campo")) not in esperado["campos_entre"]:
        return False, f"campos={sorted(campos) or 'sin filtros'}"
    if "ordenar_por" in esperado:
        if str(args.get("ordenar_por")) not in esperado["ordenar_por"]:
            return False, f"ordenar_por={args.get('ordenar_por')}"
        if esperado.get("direccion") and \
                args.get("direccion") != esperado["direccion"]:
            return False, f"direccion={args.get('direccion')}"
    if "minimo_filtros" in esperado and len(filtros) < esperado["minimo_filtros"]:
        return False, f"solo {len(filtros)} condiciones"
    if esperado.get("con_descripcion") and not args.get("descripcion"):
        return False, "sin descripcion"
    return True, ""


async def main():
    print(f"clave: {DETALLE.get('clave')} | modelo: {DETALLE.get('solver_model')}")
    print(f"decisor reasoning: {os.getenv('DECISOR_REASONING', 'low')} | "
          f"redactor reasoning: {os.getenv('REDACTOR_REASONING', 'low')}")
    print("=" * 78)
    verdes = 0
    for mensaje, esperado in CASOS:
        pedidos, texto = await HV._pedir_herramientas(
            "Verifika", "", [], mensaje, TIENDA, "banco1")
        ok, motivo = _evaluar(pedidos, esperado)
        verdes += 1 if ok else 0
        print(f"\n[{'OK ' if ok else 'MAL'}] {mensaje[:64]}")
        print(f"   pidio : {_resumen(pedidos)}")
        if not ok:
            print(f"   falta : {motivo}")
        await asyncio.sleep(float(os.getenv("BANCO_PAUSA_S", "2")))
    print("\n" + "=" * 78)
    print(f"LLAMADA UNO — {verdes} de {len(CASOS)} en verde")
    return 0 if verdes == len(CASOS) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

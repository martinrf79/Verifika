"""
BANCO DE LA LLAMADA UNO — ¿el modelo declara en la CASILLA que corresponde?

QUE MIDE. Una request por mensaje. No redacta, no encadena, no arma
presupuesto. El modelo ve una sola herramienta y no elige que buscar: deja
por escrito lo que entendio. Este banco mira ESA declaracion, y nada mas.

    python3 banco_pruebas/banco_llamada_uno.py
    python3 banco_pruebas/banco_llamada_uno.py --json vara.json

── LO QUE CAMBIO EL 10-SEP-2026, Y ES LO QUE HACE QUE ESTA VARA SIRVA ──────

1. ESTABA MUERTO. Importaba `app.core.hub_venta`, que se borro el 3-sep con el
   hub. Desde ese dia este archivo no corria: cualquiera que quisiera medir la
   interpretacion se llevaba un ImportError. Ahora entra por
   `app.core.turno._pedir_herramientas`, que es la llamada uno de verdad.

2. MEDIA SEÑALES SOBRE UN BLOB, Y ASI NO SE PUEDE VER EL DEFECTO QUE HAY. La
   version vieja pegaba TODAS las casillas en una sola cadena y buscaba
   subcadenas: para "cual es el producto mas caro" pedia que apareciera "caro"
   en algun lugar. Medido con la sonda el 9-sep, el modelo declara eso como
   `atributos` con `de` igual a "el producto mas caro", que no identifica
   ningun producto y no se puede contestar; la palabra "caro" aparece, la vara
   daba verde y el bot contestaba mal. Una vara que junta las casillas no puede
   ver el unico error que el modelo comete seguido: poner la cosa en la casilla
   equivocada.

3. AHORA SE MIDE LA CASILLA, y en las dos direcciones: las que TIENEN que
   estar llenas y las que tienen que quedar VACIAS. La segunda mitad es la que
   importa, porque el fallo tipico es llenar `atributos` de mas.

── LOS DOS NUMEROS ────────────────────────────────────────────────────────

    TURNOS EXACTOS      todas las casillas del turno bien, o el turno falla.
                        Es la vara dura y es la que se compara entre corridas.
    ACIERTO POR CASILLA en cuantos turnos esa casilla quedo como debia, y
                        cuantas veces se lleno de mas o de menos. Es la que
                        dice DONDE trabajar.

Y un tercer listado que no puntua pero que es el que mas dice: LOS NOMBRES DE
CAMPO QUE DECLARO. Medido sobre los casetes grabados, el modelo llama al mismo
dato de tres formas distintas en tres turnos -`resolucion`, `sensor`,
`caracteristicas_extra` para los DPI de un mouse- e inventa campos que la ficha
no tiene, como `pais_fabricacion`. Esa dispersion es lo que un vocabulario
cerrado corta de raiz, y hasta que exista conviene tenerla a la vista.

── DE DONDE SALEN LOS CASOS ───────────────────────────────────────────────

De lo que ya estaba en el repo, no de casos inventados: los mensajes son de
`banco_pruebas/casetes/`, las charlas grabadas, mas los cuatro de WhatsApp del
9-sep que estan en el issue 31. La casilla esperada de cada uno sale de la
definicion del molde en `herramientas.RegistrarPedido`, no de una opinion:

    items           lo que quiere COTIZAR o ver, con su rubro
    restricciones   TODA condicion y TODO extremo, incluido el ORIGEN y los
                    superlativos -el mas barato, el de mas garantia-. Lo dice
                    la descripcion del campo, textual.
    atributos       un dato de la ficha de un producto IDENTIFICABLE. Si el
                    `de` no identifica nada -"algun producto", "el producto
                    mas caro"- la casilla es la equivocada.
    stock           si HAY algo
    compatibilidad  si algo sirve PARA algo
    temas           una politica de la casa, y es una CLAVE de la FAQ
    destinos        localidades de envio
    pide_precio     espera un numero de plata
    contradicciones lo que no cierra y no se puede resolver sin elegir por el
                    cliente
"""
import argparse
import asyncio
import json
import os
import sys
from collections import Counter
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from banco_pruebas import clon_produccion  # noqa: E402

DETALLE = clon_produccion.instalar()

from app.core import turno as T  # noqa: E402

TIENDA = os.getenv("TIENDA_ID", "verifika_prod")

CASILLAS = ("items", "restricciones", "atributos", "stock", "compatibilidad",
            "temas", "destinos", "pide_precio", "contradicciones",
            "reparto_pago")

# (mensaje, casillas que TIENEN que venir llenas, casillas que TIENEN que
#  quedar vacias). Lo que no se nombra en ninguna de las dos no puntua.
CASOS = [
    # ── Superlativos y condiciones. La casilla es `restricciones`, y con el
    #    rubro nombrado el modelo ya lo hace bien: estos son el piso.
    ("hola, cuanto sale el mouse mas barato que tengas?",
     {"items", "restricciones", "pide_precio"}, {"atributos", "temas"}),
    ("bueno, dame la notebook mas barata que tengas para trabajar",
     {"items", "restricciones"}, {"atributos", "temas"}),
    ("Mostrame el mouse mas barato que tengas",
     {"items", "restricciones"}, {"atributos", "temas"}),
    ("Que teclado tiene la garantia mas larga?",
     {"items", "restricciones"}, {"temas"}),
    ("Cual es el mouse mas liviano que tengas para viajar?",
     {"items", "restricciones"}, {"temas"}),
    ("Busco unos auriculares de hasta 80 mil pesos",
     {"items", "restricciones"}, {"atributos", "temas"}),
    ("Un mouse inalambrico negro de menos de 120 gramos y que salga menos de "
     "50 mil",
     {"items", "restricciones"}, {"temas"}),
    ("Necesito el mouse que menos partes chinas tenga, pero que no sea "
     "Logitech",
     {"items", "restricciones"}, {"temas"}),
    ("Quiero un teclado inalambrico para la oficina",
     {"items", "restricciones"}, {"atributos", "temas"}),

    # ── EL SUPERLATIVO SIN RUBRO. Los cuatro que fallan hoy, y fallan igual:
    #    el modelo se queda sin que poner en `items` y mete la pregunta en
    #    `atributos` con un `de` que no identifica nada.
    ("Dime cual es el producto mas caro que tienen",
     {"restricciones"}, {"atributos"}),
    ("Cual es el producto mas caro de toda la tienda?",
     {"restricciones"}, {"atributos"}),
    ("Tienes algun producto con origen estados unidos",
     {"restricciones"}, {"atributos"}),
    ("Cuantos productos tenes que no se fabriquen en China?",
     {"restricciones"}, {"atributos"}),

    # ── EL ORIGEN ES UNA CONDICION, y lo dice el molde con esas palabras.
    ("Dame lista de productos que no sean fabricados en china",
     {"restricciones"}, {"atributos"}),
    ("Pasame microfonos marcas estados unidos",
     {"items", "restricciones"}, {"atributos"}),

    # ── AGREGADOS SOBRE EL CATALOGO. No hay producto que identificar.
    ("Que marcas manejas?", set(), {"atributos", "items"}),
    # AFLOJADO EL 10-SEP, Y LA VARA ESTABA MAL, NO EL MODELO. Pedia
    # `restricciones` para "cuantos mouse blancos tenes"; el modelo declaro
    # `stock` con "mouse blancos" adentro, que contesta igual de bien y es
    # defendible. Una vara que exige UNA de dos formas correctas mide el gusto
    # del que la escribio. Queda lo que si es seguro: no es un atributo.
    ("Cuantos mouse blancos tenes?", set(), {"atributos"}),

    # ── ATRIBUTOS DE VERDAD: el producto se identifica y se pide un dato.
    ("que garantia tiene el mouse logitech g203?",
     {"atributos"}, {"restricciones", "temas"}),
    ("esa notebook tiene lector de huella digital?",
     {"atributos"}, {"restricciones", "temas"}),
    ("que trae la caja?", {"atributos"}, {"restricciones", "temas"}),
    ("y cuanto pesa ese mouse?", {"atributos"}, {"restricciones", "temas"}),
    ("cuantos dpi tiene y cuantos botones?",
     {"atributos"}, {"restricciones", "temas"}),
    ("de donde viene, es chino?", {"atributos"}, {"temas"}),

    # ── STOCK
    ("hola tenes celulares samsung o iphone?", {"stock"}, {"atributos"}),
    ("y una play 5 tenes?", {"stock"}, {"atributos", "temas"}),
    ("hola, tenes memoria ram de 16gb? cuanto sale, cuanto tarda a rosario y "
     "aceptan transferencia?",
     {"stock", "pide_precio", "destinos", "temas"}, set()),

    # ── COMPATIBILIDAD
    ("y ese sirve para jugar?", {"compatibilidad"}, {"restricciones"}),
    ("Tengo una notebook Lenovo IdeaPad 3, que memoria RAM le sirve?",
     {"compatibilidad"}, {"temas"}),

    # ── PRECIO Y CANTIDADES
    ("quiero 2 mouse genius dx-110 negro y 1 teclado, cuanto sale?",
     {"items", "pide_precio"}, {"atributos", "restricciones"}),
    ("no, el teclado sacalo, dejame solo los mouse",
     {"items"}, {"atributos", "restricciones"}),
    # SACADO EL 10-SEP, Y ERA UN DEFECTO DE LA VARA. "los dos juntos, cuanto me
    # sale con envio a rosario" pedia `items`, y esta vara corre SIN HISTORIAL:
    # sin los turnos anteriores no hay forma de saber cuales son los dos, asi
    # que el caso medía la falta de contexto y se la cobraba al modelo. Un caso
    # que no se puede acertar no mide nada. Los turnos que dependen del
    # historial son un banco aparte y hay que hacerlo con historial de verdad.
    ("los dos juntos, cuanto me sale con envio a rosario?",
     {"pide_precio", "destinos"}, {"atributos"}),

    # ── POLITICA DE LA CASA: `temas`, y tiene que ser una CLAVE de la FAQ.
    ("me lo mandas hoy?", {"temas"}, {"atributos", "items"}),
    ("bueno, y si te llevo dos me haces precio?",
     {"temas"}, {"atributos"}),

    # ── CONTRADICCION
    ("Hola, quiero comprar el iPhone 15 Pro, pero la version que viene con "
     "Android",
     {"contradicciones"}, set()),
    ("quiero 2 teclados y 1 mouse a rosario, y 1 auricular a cordoba. cuanto "
     "me sale todo junto?",
     {"destinos"}, set()),

    # ── PRECIO SIN PRODUCTO NUEVO: el turno de WhatsApp del 9-sep.
    ("Precio", {"pide_precio"}, {"temas", "atributos"}),
]


def _declarado(pedidos: list) -> dict | None:
    for p in (pedidos or []):
        if p.get("nombre") == "registrar_pedido":
            return p.get("args") or {}
    return None


def _llenas(d: dict) -> set:
    """Las casillas que el modelo lleno de verdad. `pide_precio` es booleano;
    las demas cuentan solo si traen al menos un renglon."""
    fuera = set()
    for c in CASILLAS:
        v = d.get(c)
        if c == "pide_precio":
            if v is True:
                fuera.add(c)
        elif v:
            fuera.add(c)
    return fuera


def _campos(d: dict) -> list:
    return [str((a or {}).get("campo") or "") for a in (d.get("atributos") or [])
            if isinstance(a, dict) and (a or {}).get("campo")]


def _resumen(d: dict | None) -> str:
    if d is None:
        return "NO DECLARO"
    partes = []
    for it in (d.get("items") or []):
        if isinstance(it, dict) and it.get("que"):
            partes.append(f"item={str(it.get('que'))[:26]}")
    for r in (d.get("restricciones") or []):
        partes.append(f"rest={str(r)[:26]!r}")
    for a in (d.get("atributos") or []):
        if isinstance(a, dict):
            partes.append(f"attr={a.get('de')}.{a.get('campo')}")
    for c in (d.get("compatibilidad") or []):
        if isinstance(c, dict):
            partes.append(f"compat={c.get('que')}->{c.get('para')}")
    for s in (d.get("stock") or []):
        partes.append(f"stock={str(s)[:22]}")
    for t in (d.get("temas") or []):
        partes.append(f"tema={str(t)[:26]}")
    for x in (d.get("destinos") or []):
        partes.append(f"dest={x}")
    if d.get("pide_precio"):
        partes.append("pide_precio")
    for c in (d.get("contradicciones") or []):
        partes.append(f"contra={str(c)[:26]}")
    return " | ".join(partes) or "(declaro vacio)"


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    ap.add_argument("--pausa", type=float,
                    default=float(os.getenv("BANCO_PAUSA_S", "2")))
    args = ap.parse_args()

    print(f"clave: {DETALLE.get('clave')} | modelo: {DETALLE.get('solver_model')}")
    print(f"decisor reasoning: {os.getenv('DECISOR_REASONING', 'low')}")
    print("=" * 78)

    exactos = 0
    declararon = 0
    de_mas = Counter()      # casilla llenada cuando tenia que estar vacia
    de_menos = Counter()    # casilla vacia cuando tenia que estar llena
    en_juego = Counter()    # cuantos casos ponen esa casilla en juego
    campos_vistos = Counter()
    temas_vistos = Counter()
    registro = []

    for mensaje, deben, no_deben in CASOS:
        pedidos, texto = await T._pedir_herramientas(
            "Verifika Tech", "", [], mensaje, TIENDA, "vara1")
        d = _declarado(pedidos)
        if d is not None:
            declararon += 1
        llenas = _llenas(d or {})
        faltan = deben - llenas
        sobran = no_deben & llenas
        ok = not faltan and not sobran
        exactos += 1 if ok else 0
        for c in deben | no_deben:
            en_juego[c] += 1
        for c in faltan:
            de_menos[c] += 1
        for c in sobran:
            de_mas[c] += 1
        for c in _campos(d or {}):
            campos_vistos[c] += 1
        for t in ((d or {}).get("temas") or []):
            if str(t or "").strip():
                temas_vistos[str(t).strip()] += 1

        print(f"\n[{'OK ' if ok else 'MAL'}] {mensaje[:66]}")
        print(f"   declaro: {_resumen(d)}")
        if faltan:
            print(f"   falta llenar : {sorted(faltan)}")
        if sobran:
            print(f"   lleno de mas : {sorted(sobran)}")
        registro.append({"mensaje": mensaje, "ok": ok,
                         "declaro": d, "llenas": sorted(llenas),
                         "falta": sorted(faltan), "sobra": sorted(sobran)})
        await asyncio.sleep(args.pausa)

    print("\n" + "=" * 78)
    print(f"TURNOS EXACTOS: {exactos} de {len(CASOS)}   "
          f"({100 * exactos // max(1, len(CASOS))} por ciento)")
    print(f"control: {declararon} de {len(CASOS)} llamaron a registrar_pedido")
    print("\nACIERTO POR CASILLA, sobre los casos que la ponen en juego:")
    for c in CASILLAS:
        if not en_juego[c]:
            continue
        mal = de_mas[c] + de_menos[c]
        print(f"  {c:16} {en_juego[c] - mal:3} de {en_juego[c]:3} bien"
              f"   de mas {de_mas[c]:2}   de menos {de_menos[c]:2}")

    # ── LAS DOS ATADURAS QUE YA EXISTEN, MEDIDAS ───────────────────────────
    #
    # El molde NO tiene el vocabulario abierto: `esquemas()` ya inyecta el enum
    # de `campo` desde el catalogo vivo, con `sin_campo_en_la_fuente` como
    # escapatoria, y los temas se nombran libres a proposito y los certifica
    # `certificar_temas` contra las señas de la fuente. O sea que las dos
    # ataduras estan puestas. Lo que nunca se midio es si SE RESPETAN, y sin
    # ese numero no se sabe si hay que cerrar algo o solo hacerlo cumplir.
    print("\nNOMBRES DE CAMPO QUE DECLARO, contra el enum real del molde:")
    try:
        from app.core.filtros_catalogo import campos_filtrables, SIN_CAMPO
        # OJO CON EL NOMBRE: `registro` ya es la lista del detalle de arriba.
        # Reusarlo aca pisaba el detalle y el JSON salia con un set adentro.
        del_enum = set(campos_filtrables(TIENDA) or {})
    except Exception as e:  # noqa: BLE001
        del_enum, SIN_CAMPO = set(), "sin_campo_en_la_fuente"
        print(f"  no se pudo leer el registro de campos: {e!r}")
    fuera_del_enum = 0
    for campo, n in campos_vistos.most_common():
        if not del_enum:
            marca = "?"
        elif campo == SIN_CAMPO:
            marca = "escapatoria"
        elif campo in del_enum:
            marca = "en el enum"
        else:
            marca = "FUERA DEL ENUM"
            fuera_del_enum += n
        print(f"  {n:3}  {campo:32} {marca}")
    if del_enum:
        print(f"  campos del enum en la fuente: {len(del_enum)}")
        print(f"  declaraciones fuera del enum: {fuera_del_enum}")
        print("  Si esto es cero, el vocabulario cerrado se respeta y no hay "
              "nada que cerrar. Si no, la atadura existe y no se cumple: la "
              "arregla el codigo, no una instruccion.")

    print("\nTEMAS QUE DECLARO, contra la certificacion de la fuente:")
    try:
        from app.core.herramientas import certificar_tema
    except Exception as e:  # noqa: BLE001
        certificar_tema = None
        print(f"  no se pudo importar certificar_tema: {e!r}")
    perdidos = 0
    for tema, n in temas_vistos.most_common():
        v = "?"
        if certificar_tema is not None:
            try:
                v = certificar_tema(tema, TIENDA).get("veredicto", "?")
            except Exception as e:  # noqa: BLE001
                v = f"error {type(e).__name__}"
        if v == "not_found":
            perdidos += n
        print(f"  {n:3}  {str(tema)[:44]:44} {v}")
    print(f"  temas que no certifican: {perdidos}")
    print("  Un tema que no certifica es una pregunta que el sistema abrio y "
          "no puede contestar con la voz de la casa.")

    if args.json:
        Path(args.json).write_text(json.dumps(
            {"exactos": exactos, "casos": len(CASOS),
             "de_mas": dict(de_mas), "de_menos": dict(de_menos),
             "en_juego": dict(en_juego), "campos": dict(campos_vistos),
             "temas": dict(temas_vistos),
             "detalle": registro}, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8")
        print(f"\ncapturado en {args.json}")

    return 0 if exactos == len(CASOS) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

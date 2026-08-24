"""
LA PUERTA DETERMINISTA — cuanto del mensaje del cliente entiende el codigo SOLO.

POR QUE EXISTE (Martin, 14-ago-2026): quiere saber si el sistema puede
interpretar y contestar con el LLM APAGADO, aunque salga robotico, porque esa
prueba es gratis y se puede repetir todas las veces que haga falta. La pregunta
es correcta y hasta hoy no habia con que contestarla.

LO QUE HAY QUE SACARSE DE ENCIMA PRIMERO, porque yo mismo estuve por citarlo
mal: el intérprete que se mato el 1-ago **tambien era un LLM** —importa `openai`,
esta en `banco_pruebas/interprete_viejo/`—. O sea que el duelo del 31-jul, 69
contra 91, fue modelo contra modelo. **De un sistema sin LLM adelante no hay ni
un numero en este repo.** Este banco es ese numero.

QUE MIDE, y no mide otra cosa: de lo que el modelo DECLARO en `registrar_pedido`
sobre cada mensaje real, cuanto puede reconstruir el codigo determinista SOLO,
leyendo el mensaje crudo. Ni la prosa, ni la venta, ni el tono: la
INTERPRETACION, que es la pieza que falta para que el turno corra sin modelo.

LA VERDAD DE REFERENCIA YA ESTABA GRABADA, y por eso esto no cuesta un peso:
los casetes tienen el mensaje del cliente y, al lado, el `registrar_pedido` que
el modelo produjo, ya verificados contra el piso de las charlas. Entrada y
salida esperada, sin escribir un caso a mano y sin llamar a nadie.

LA REGLA QUE LO MANTIENE HONESTO: **aca no se escribe interprete nuevo.** Se
usan las piezas deterministas que YA existen en el camino vivo y que YA tienen
barrido. Donde no hay pieza, el banco lo dice y no lo disimula: ese hueco es
justamente el resultado. Si este archivo empieza a tener logica de
interpretacion adentro, deja de medir el sistema y pasa a medirse a si mismo,
que es el error mas caro que tiene escrito este repo.

CORRE OFFLINE Y GRATIS: doble local de Firestore, catalogo y FAQ reales, cero
llamadas al modelo.
"""
import json
import re
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

TIENDA = "verifika_prod"
CASETES = Path(__file__).resolve().parent / "casetes"

# LOS CAMPOS DE `registrar_pedido`, con la pieza determinista que hoy los puede
# reconstruir. `None` significa que NO HAY PIEZA, y no es una omision de este
# banco: es el hueco que hay que llenar para que el turno corra sin modelo.
PIEZAS = {
    "items": "guia_pedido.cantidades_por_categoria",
    "destinos": "geo_cp.resolver / _localidades_en_texto",
    "reparto_pago": "pedido.reparto_ambiguo",
    "restricciones": "filtros_catalogo: exclusion / inclusion / orden",
    "pide_precio": None,
    "contradicciones": None,
}


# ── LA VERDAD DE REFERENCIA, leida de los casetes ───────────────────────────
def verdad() -> list:
    """(guion, turno, mensaje, declarado) de cada turno grabado donde el modelo
    declaro un pedido. No se escribe ningun caso: se lee lo que ya se grabo."""
    fuera = []
    for f in sorted(CASETES.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        for i, t in enumerate(d.get("turnos") or []):
            msg = str(t.get("mensaje") or "").strip()
            dec = _declarado_del_turno(t)
            if msg and dec is not None:
                fuera.append((d.get("guion", f.stem), i, msg, dec))
    return fuera


def _declarado_del_turno(turno: dict):
    """El `registrar_pedido` que el modelo emitio en ese turno, si lo emitio."""
    for ll in (turno.get("llamadas") or []):
        salida = ll.get("salida")
        if not isinstance(salida, str) or "registrar_pedido" not in salida:
            continue
        try:
            cuerpo = json.loads(salida)
        except (TypeError, ValueError):
            continue
        for tc in (cuerpo.get("tool_calls") or []):
            if tc.get("name") != "registrar_pedido":
                continue
            try:
                return json.loads(tc.get("arguments") or "{}")
            except (TypeError, ValueError):
                return {}
    return None


# ── LA RECONSTRUCCION, con piezas que YA existen ────────────────────────────
def reconstruir(mensaje: str) -> dict:
    """Lo que el codigo determinista saca del mensaje crudo, sin modelo."""
    from app.core.guia_pedido import cantidades_por_categoria
    from app.core.pedido import reparto_ambiguo
    from app.core import geo_cp

    # DOS PIEZAS Y NO UNA, y la diferencia se vio midiendo: la primera version
    # de este banco usaba solo `cantidades_por_categoria` y daba 17,6%, pero
    # esa funcion devuelve el rubro que viene CON UN NUMERO adelante. Sobre
    # "cuanto sale el mouse mas barato que tengas" devolvia vacio teniendo la
    # palabra mouse escrita. Detectar el rubro es `categorias_nombradas`;
    # contarlo es `cantidades_por_categoria`. Medir con la pieza equivocada
    # subestima al codigo, que es tan mentira como sobrestimarlo.
    fuera = {}
    try:
        cantidades = {c: n for n, c in cantidades_por_categoria(mensaje, TIENDA)}
    except Exception:  # noqa: BLE001 — una pieza que levanta se cuenta como cero
        cantidades = {}
    try:
        fuera["items"] = [(c, cantidades.get(c, 1))
                          for c in _categorias_de(mensaje)]
    except Exception:  # noqa: BLE001
        fuera["items"] = []
    try:
        fuera["reparto_pago"] = bool(reparto_ambiguo([mensaje]))
    except Exception:  # noqa: BLE001
        fuera["reparto_pago"] = False
    try:
        prov, cp = geo_cp.resolver(mensaje)
        fuera["destinos"] = bool(prov or cp)
    except Exception:  # noqa: BLE001
        fuera["destinos"] = False
    return fuera


def _nombrado_en(que: str, mensaje: str) -> bool:
    """Si el item que el modelo declaro esta NOMBRADO en este mensaje. Es un
    chequeo mecanico sobre las palabras, no interpretacion: alcanza con que una
    palabra de tres letras o mas del item aparezca en el texto del cliente."""
    m = re.sub(r"[^a-z0-9áéíóúñ ]", " ", (mensaje or "").lower())
    palabras = set(m.split())
    for p in re.sub(r"[^a-z0-9áéíóúñ ]", " ", (que or "").lower()).split():
        if len(p) >= 3 and (p in palabras
                            or any(w.startswith(p[:4]) for w in palabras
                                   if len(p) >= 4)):
            return True
    return False


def _categorias_de(texto: str) -> set:
    """Las categorias reales que nombra un texto. Se usa para comparar peras
    con peras: el modelo declara 'mouse inalambrico para jugar' y el codigo
    devuelve 'mouse', asi que los dos lados se pasan por la misma funcion."""
    from app.core.guia_pedido import categorias_nombradas
    try:
        return set(categorias_nombradas(texto, TIENDA))
    except Exception:  # noqa: BLE001
        return set()


# ── LA MEDICION ─────────────────────────────────────────────────────────────
def medir() -> dict:
    casos = verdad()
    r = {"turnos": len(casos), "campos": {}, "fallas": []}

    # ITEMS: el corazon del asunto. Se mide por CATEGORIA y por CANTIDAD, por
    # separado, porque son dos cosas distintas: acertar que pidio mouse y
    # errarle a cuantos no es lo mismo que no ver el mouse.
    dec_items = cod_items = coinciden = cant_ok = cant_total = extra = 0
    turnos_con_items = turnos_item_completo = 0
    arrastrados = arrastrados_turnos = 0
    for guion, i, msg, dec in casos:
        esperados, de_memoria = {}, {}
        for it in (dec.get("items") or []):
            # EL SEGUNDO SESGO, y es el mas grande: el modelo declara el pedido
            # ACUMULADO, o sea que en el turno 3 vuelve a declarar el mouse del
            # turno 1 aunque el cliente no lo haya nombrado. El codigo aca solo
            # ve el mensaje de hoy. Compararlos de frente le cobra al codigo
            # una memoria que no le dimos. Se separan: lo NOMBRADO en este
            # mensaje se le exige, lo ARRASTRADO se cuenta aparte —y en un turno
            # sin modelo lo pondria `construir_estado`, que es determinista y ya
            # tiene su barrido—.
            que = str(it.get("que") or "")
            nombrado = _nombrado_en(que, msg)
            for c in _categorias_de(que):
                destino = esperados if nombrado else de_memoria
                destino[c] = destino.get(c, 0) + int(it.get("cantidad") or 1)
        if de_memoria:
            arrastrados += len(de_memoria)
            arrastrados_turnos += 1
        obtenidos = {}
        for c, n in reconstruir(msg)["items"]:
            obtenidos[c] = obtenidos.get(c, 0) + int(n or 1)
        if not esperados:
            continue
        turnos_con_items += 1
        dec_items += len(esperados)
        cod_items += len(obtenidos)
        pegados = set(esperados) & set(obtenidos)
        coinciden += len(pegados)
        extra += len(set(obtenidos) - set(esperados))
        for c in pegados:
            cant_total += 1
            if esperados[c] == obtenidos[c]:
                cant_ok += 1
        if set(esperados) == set(obtenidos):
            turnos_item_completo += 1
        else:
            r["fallas"].append({
                "campo": "items", "guion": guion, "turno": i,
                "mensaje": msg[:90],
                "modelo": sorted(esperados), "codigo": sorted(obtenidos)})

    r["campos"]["items"] = {
        "pieza": PIEZAS["items"], "turnos": turnos_con_items,
        "declarados": dec_items, "reconstruidos": coinciden,
        "de_mas": extra,
        "recall": round(100.0 * coinciden / max(1, dec_items), 1),
        "turnos_exactos": turnos_item_completo,
        "turnos_exactos_pct": round(
            100.0 * turnos_item_completo / max(1, turnos_con_items), 1),
        "cantidad_ok": cant_ok, "cantidad_medidas": cant_total,
        "cantidad_pct": round(100.0 * cant_ok / max(1, cant_total), 1),
        "arrastrados": arrastrados, "arrastrados_turnos": arrastrados_turnos}

    # Los campos de SI o NO: el codigo lo ve o no lo ve.
    for campo in ("destinos", "reparto_pago"):
        con = aciertos = falsos = 0
        for guion, i, msg, dec in casos:
            tiene = bool(dec.get(campo) or
                         (campo == "destinos" and
                          any(it.get("destino") for it in (dec.get("items") or []))))
            visto = reconstruir(msg)[campo]
            if tiene:
                con += 1
                if visto:
                    aciertos += 1
                else:
                    r["fallas"].append({"campo": campo, "guion": guion,
                                        "turno": i, "mensaje": msg[:90],
                                        "modelo": dec.get(campo), "codigo": False})
            elif visto:
                falsos += 1
        r["campos"][campo] = {
            "pieza": PIEZAS[campo], "turnos": con, "reconstruidos": aciertos,
            "recall": round(100.0 * aciertos / max(1, con), 1),
            "falsos_positivos": falsos}

    # RESTRICCIONES: dos numeros distintos y hay que no mezclarlos. Uno es si el
    # codigo sabe TRADUCIR la restriccion a un filtro real de la ficha; el otro
    # es si sabe ENCONTRARLA en el mensaje crudo, que es lo que haria falta sin
    # modelo. La segunda pieza no existe.
    #
    # SON TRES PUERTAS Y NO UNA (FICHA 06, 23-ago-2026). Este banco preguntaba
    # solo por `resolver_exclusion` y por eso daba de menos: una condicion
    # positiva -"marcas de estados unidos"- y un extremo -"el mas barato"- los
    # traduce el codigo igual de bien, por `resolver_inclusion` y por
    # `resolver_orden`, y contaban como no traducidos. Es la misma falla que el
    # reconciliador ya pago dos veces: **un instrumento que no conoce el
    # argumento nuevo no mide de menos por prudencia, mide MAL.** Se le pregunta
    # al mecanismo entero, que es el que corre en el turno.
    from app.core.filtros_catalogo import (resolver_exclusion,
                                           resolver_inclusion, resolver_orden)
    total_r = traducidas = 0
    for guion, i, msg, dec in casos:
        for restr in (dec.get("restricciones") or []):
            total_r += 1
            try:
                if (resolver_orden(str(restr), TIENDA)
                        or resolver_exclusion(str(restr), TIENDA)
                        or resolver_inclusion(str(restr), TIENDA)):
                    traducidas += 1
            except Exception:  # noqa: BLE001
                pass
    r["campos"]["restricciones"] = {
        "pieza": PIEZAS["restricciones"], "turnos": total_r,
        "reconstruidos": traducidas,
        "recall": round(100.0 * traducidas / max(1, total_r), 1),
        "nota": "mide TRADUCIR la restriccion ya aislada a un filtro. "
                "ENCONTRARLA en el mensaje crudo no tiene pieza."}

    # Los que no tienen pieza. Se cuentan igual, para que se vea el tamaño del
    # hueco y no quede como una nota al pie.
    for campo in ("pide_precio", "contradicciones"):
        con = sum(1 for _, _, _, dec in casos if dec.get(campo))
        r["campos"][campo] = {"pieza": None, "turnos": con,
                              "reconstruidos": 0, "recall": 0.0}
    return r


PISO = Path(__file__).resolve().parent / "puerta_piso.json"


def piso() -> dict:
    """La vara de hoy. Igual que el piso de los casetes y el techo del peso: el
    numero puede SUBIR, y si baja el CI lo grita. Se fija con `--fijar`."""
    try:
        return json.loads(PISO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def fijar(r: dict) -> None:
    campos = {k: v["recall"] for k, v in r["campos"].items()}
    campos["_turnos"] = r["turnos"]
    campos["_items_turnos_exactos_pct"] = r["campos"]["items"]["turnos_exactos_pct"]
    PISO.write_text(json.dumps(campos, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")


def main() -> int:
    from banco_pruebas.sim_firestore import install
    from app.core.contexto_turno import set_current_tienda
    install()
    set_current_tienda(TIENDA)

    r = medir()
    if "--fijar" in sys.argv:
        fijar(r)
        print(f"piso fijado en {PISO.name}")
        return 0
    print("=" * 74)
    print("LA PUERTA DETERMINISTA — cuanto entiende el codigo sin el modelo")
    print("=" * 74)
    print(f"  turnos reales medidos: {r['turnos']}, con su `registrar_pedido` "
          f"grabado al lado\n")
    it = r["campos"]["items"]
    print(f"  ITEMS — {it['pieza']}")
    print(f"    rubros que el modelo declaro ..... {it['declarados']}")
    print(f"    los que el codigo saca solo ...... {it['reconstruidos']}  "
          f"= {it['recall']}%")
    print(f"    rubros de mas que saca el codigo . {it['de_mas']}")
    print(f"    turnos con el pedido ENTERO bien . {it['turnos_exactos']}/"
          f"{it['turnos']} = {it['turnos_exactos_pct']}%")
    print(f"    cantidades bien, de los que pego . {it['cantidad_ok']}/"
          f"{it['cantidad_medidas']} = {it['cantidad_pct']}%")
    print(f"    aparte: rubros que el modelo arrastro de turnos anteriores y "
          f"el cliente NO nombro hoy: {it['arrastrados']} en "
          f"{it['arrastrados_turnos']} turnos. Sin modelo los pondria "
          f"`construir_estado`, no la puerta.\n")
    for campo in ("destinos", "reparto_pago", "restricciones",
                  "pide_precio", "contradicciones"):
        c = r["campos"][campo]
        pieza = c["pieza"] or "SIN PIEZA DETERMINISTA"
        print(f"  {campo.upper()} — {pieza}")
        print(f"    turnos donde aparece ..... {c['turnos']}")
        print(f"    los que el codigo saca ... {c['reconstruidos']}  "
              f"= {c['recall']}%")
        if c.get("falsos_positivos"):
            print(f"    falsos positivos ......... {c['falsos_positivos']}")
        if c.get("nota"):
            print(f"    ojo: {c['nota']}")
        print()
    if r["fallas"]:
        print(f"  DONDE FALLA, con el mensaje real ({len(r['fallas'])} casos, "
              f"primeros 12):")
        for f in r["fallas"][:12]:
            print(f"    [{f['campo']}] {f['guion']} t{f['turno']}")
            print(f"      cliente: {f['mensaje']}")
            print(f"      modelo:  {f['modelo']}")
            print(f"      codigo:  {f['codigo']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

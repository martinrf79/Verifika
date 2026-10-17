"""EL MOTOR — la UNICA puerta por la que el modelo busca en la fuente."""
import json

from app.logger import get_logger

log = get_logger(__name__)

# Tope duro de filas por consulta. El modelo puede pedir menos, nunca mas: una busqueda que devuelve cuarenta
# fichas inunda el prompt y ademas no sirve, que es la leccion del catalogo entero que no entra.
TOPE_FILAS = 8

# La salida del orden: la respuesta cuando el cliente no pidio ninguno.
SIN_ORDEN = "ninguno"


FILAS_POR_DEFECTO = 5

# Cuantas consultas entran en una llamada.
TOPE_CONSULTAS = 6

# Hasta cuantos empatados siguen siendo UNA COSA con variantes -el mismo teclado en negro, blanco, gris y
# azul- y no un termino generico.
TOPE_AMBIGUO = 4

# Cuantas cosas escritas por la casa vuelven en una llamada.
TOPE_TEMAS = 6

# LOS TEMAS QUE EL ENVIO APAGA, y viven ACA desde el 13-sep.
TEMAS_DEL_ENVIO = ("costo_envio", "envios")


# Cuantos pares de compatibilidad se evaluan en una llamada.
TOPE_COMPAT = 4

# Cuantas entradas de criterio vuelven en una llamada.
TOPE_CRITERIO = 3


class _Cond:
    """La condicion como la espera `filtros_catalogo.aplicar`, que lee por atributo."""

    __slots__ = ("campo", "operador", "valor")

    def __init__(self, d: dict):
        self.campo = str((d or {}).get("campo") or "")
        self.operador = str((d or {}).get("operador") or "")
        self.valor = (d or {}).get("valor", "")


def _equipos(tienda_id: str) -> str:
    """Los equipos que el vocabulario de compatibilidad conoce, con la etiqueta que lee un cliente."""
    try:
        from app.core.compatibilidad import vocabulario
        v = vocabulario(tienda_id)
        etq = [str((d or {}).get("etiqueta") or pid)
               for pid, d in (v.get("plataformas") or {}).items()]
        return ", ".join(etq)
    except Exception as e:  # noqa: BLE001 — sin vocabulario se pide en prosa
        log.warning("motor_equipos_error", tienda_id=tienda_id,
                    error=f"{type(e).__name__}: {str(e)[:120]}")
        return "una notebook, una PC, una consola, un celular"


# ── LA BUSQUEDA ─────────────────────────────────────────────────────────────


def _universo(catalogo: list, categoria: str, tienda_id: str) -> tuple:
    """El catalogo acotado al rubro que pidio el modelo."""
    from app.core.filtros_catalogo import _norm
    cat = _norm(categoria)
    if not cat:
        return catalogo, ""
    dentro = [p for p in catalogo if _norm(p.get("categoria")) == cat]
    if dentro:
        return dentro, ""
    return catalogo, f"la categoria '{categoria}' no existe en el catalogo"


def _por_ids(catalogo: list, ids: list) -> list:
    pedidos = [str(i).strip() for i in (ids or []) if str(i).strip()]
    if not pedidos:
        return []
    porid = {str(p.get("id")): p for p in catalogo}
    return [porid[i] for i in pedidos if i in porid]


def _con_la_cuenta(filas: list, unidades: int, trace_id: str = "") -> None:
    """EL SUBTOTAL DE CADA LINEA, HECHO POR `calculadora` (13-sep-2026)."""
    if unidades <= 1 or not filas:
        return
    from app.core.fuente import _plata
    try:
        from app.core.calculadora import calculate_total
        # SIN VALIDAR STOCK: esto es una LISTA de opciones, no un pedido.
        r = calculate_total(items=[{"product_id": f.get("id"),
                                    "cantidad": unidades}
                                   for f in filas if f.get("id")],
                            validar_stock=False)
        if not r.get("ok"):
            log.warning("motor_cuenta_sin_ok", trace_id=trace_id,
                        motivo=str(r.get("mensaje_para_llm"))[:120])
            return
        por_id = {str(d.get("id")): d for d in (r.get("detalle") or [])}
    except Exception as e:  # noqa: BLE001 — una cuenta rota no tumba la busqueda
        log.warning("motor_cuenta_error", trace_id=trace_id,
                    error=f"{type(e).__name__}: {str(e)[:120]}")
        return
    for f in filas:
        d = por_id.get(str(f.get("id")))
        if not d or d.get("subtotal") in (None, ""):
            continue
        f["subtotal_ars"] = d["subtotal"]
        # Ya escrito, igual que el precio: una cadena se copia, un numero
        # pelado invita a redondearlo o a sumarle el envio de memoria.
        f["subtotal"] = _plata(d["subtotal"])


def _la_cuenta(pedido: dict, envios: dict, tienda_id: str,
               trace_id: str = "", catalogo: list | None = None) -> dict:
    """LA CUENTA DEL RETORNO — lo que CRUZA bocas, calculado ANTES de redactar."""
    porid = {str(p.get("id")): p for p in (catalogo or [])}
    items, pedidos_como = [], []
    for x in (pedido or {}).get("items") or []:
        pid = str((x or {}).get("id") or "").strip()
        if not pid:
            continue
        try:
            cant = max(1, int((x or {}).get("cantidad") or 1))
        except (TypeError, ValueError):
            cant = 1
        if catalogo and pid not in porid:
            cert = _certificar_id(pid, catalogo, tienda_id)
            if cert.get("sin_total"):
                return cert
            pedidos_como.append({"pedido_como": pid, "id": cert["id"],
                                 "nombre": cert.get("nombre")})
            pid = cert["id"]
        items.append({"product_id": pid, "cantidad": cant})
    if not items:
        return {}

    from app.core.calculadora import calculate_total, cotizar_envio

    # EL ENVIO ENTRA POR LA CALCULADORA, con el concepto que ella deriva de la provincia.
    extras = []
    for fila in (envios or {}).get("filas") or []:
        destino = str(fila.get("destino") or "").strip()
        if not destino or not fila.get("monto_ars"):
            continue
        try:
            q = cotizar_envio(destino)
        except Exception as e:  # noqa: BLE001 — sin concepto no se suma envio
            log.warning("motor_cuenta_envio_error", trace_id=trace_id,
                        error=f"{type(e).__name__}: {str(e)[:120]}")
            continue
        if q.get("ok") and q.get("concepto"):
            extras.append({"faq_tema": "costo_envio",
                           "concepto": q["concepto"]})

    reparto = [x for x in ((pedido or {}).get("reparto_pago") or [])
               if isinstance(x, dict) and x.get("medio")]
    # UN MEDIO QUE LA TIENDA NO TOMA NO ENTRA A LA CUENTA, Y SE DICE.
    from app.core.filtros_catalogo import _norm
    no_disp = [x for x in reparto
               if _norm(x.get("medio")) == "medio_no_disponible"]
    if no_disp:
        reparto = [x for x in reparto if x not in no_disp]

    try:
        # UN ENVIO POR DESTINO (1-oct): la calculadora cobra cada destino con su tarifa si sabe cuantos son.
        r = calculate_total(items=items, items_extra=extras or None,
                            pago=reparto or None, destinos=max(1, len(extras)))
    except Exception as e:  # noqa: BLE001 — una cuenta rota no tumba el turno
        log.warning("motor_cuenta_total_error", trace_id=trace_id,
                    error=f"{type(e).__name__}: {str(e)[:150]}")
        return {}
    if not r.get("ok"):
        # EL MOTIVO VIAJA. Un total que no se pudo hacer y vuelve mudo se lee como un total de cero; con el
        # motivo escrito el modelo dice que le falta para poder darlo, que es la respuesta 5 de las seis.
        return {"sin_total": str(r.get("mensaje_para_llm") or
                                 "no se pudo armar la cuenta")}

    from app.core.fuente import _plata
    fuera = {"total_ars": r.get("total_ars"),
             "total": _plata(r.get("total_ars")),
             # LA PRESENTACION YA VIENE ESCRITA POR LA CALCULADORA, renglon por renglon, con el subtotal, el
             # envio y el reparto.
             "detalle": r.get("presentacion") or ""}
    if r.get("total_final_ars") is not None:
        fuera["total_final_ars"] = r["total_final_ars"]
        fuera["total_final"] = _plata(r["total_final_ars"])
    # EL ID CERTIFICADO VUELVE ESCRITO, por lo mismo que en `_un_compat`: el
    # modelo pidio por un nombre y tiene que saber de que ficha salio la plata.
    if pedidos_como:
        fuera["certificados"] = pedidos_como
    if no_disp:
        # EL MOTIVO VIAJA ESCRITO Y EL MODELO LO COPIA, que es como este repo
        # resuelve las negaciones: el dato es del codigo, la prosa del modelo.
        fuera["medio_no_disponible"] = (
            "el cliente nombro un medio de pago que la tienda no toma. Se "
            "cobra por transferencia, Mercado Pago o tarjeta. Decilo y no "
            "lo cuentes en el total.")
    # QUE HAY ADENTRO DEL TOTAL, y no es adorno: es lo que el turno guarda como carrito para que el turno
    # SIGUIENTE no lo rearme de cero.
    fuera["items"] = [
        {"id": i["product_id"], "cantidad": i["cantidad"],
         "nombre": (porid.get(i["product_id"]) or {}).get("nombre") or ""}
        for i in items]
    return fuera


def _certificar_id(nombre: str, catalogo: list, tienda_id: str) -> dict:
    """EL NOMBRE QUE USO EL CLIENTE, RESUELTO A UN ID."""
    from app.core.filtros_catalogo import los_que_lo_nombran_entero
    exactos = los_que_lo_nombran_entero(catalogo, nombre)
    if len(exactos) == 1:
        return {"id": str(exactos[0].get("id")),
                "nombre": exactos[0].get("nombre")}
    cert = _una({"texto": nombre, "busco": "uno", "cuantos": TOPE_AMBIGUO},
                catalogo, tienda_id)
    filas = cert.get("filas") or []
    if not exactos and (not filas or cert.get("veredicto") == "no_existe"):
        return {"sin_total": f"no vendemos '{nombre}', asi que no puedo "
                             f"ponerlo en la cuenta: "
                             + (cert.get("motivo") or "no esta en el catalogo")}
    candidatos = (exactos or
                  [{"id": f.get("id"), "nombre": f.get("nombre")}
                   for f in filas])[:TOPE_AMBIGUO]
    # CON SU PRECIO (2-oct, guion 28): "el HyperX Cloud II" en dos colores volvia sin un solo monto, y el
    # cliente que pidio sumarlo no leia cuanto sale.
    precios = {str(p.get("id")): p.get("precio_ars") for p in catalogo}
    lista = [f"{c.get('nombre')} ({c.get('id')}"
             + (f", ${precios[str(c.get('id'))]:,}".replace(",", ".") if precios.get(str(c.get("id"))) else "")
             + ")" for c in candidatos]
    # EL MISMO PRECIO NO ES "CADA UNO SALE DISTINTO" (16-oct): la Galaxy Tab A9 en tres colores vale lo mismo,
    # y el motivo le decia al redactor que no.
    mismos = {precios.get(str(c.get("id"))) for c in candidatos}
    if exactos and len(candidatos) > 1 and len(mismos) == 1 and None not in mismos:
        return {"sin_total": f"'{nombre}' es uno de estos y todos salen lo "
                             f"mismo, asi que el precio es ese pero no lo "
                             f"cuento sin saber cual: no elijas, pregunta cual "
                             f"de estos y volve a pedirme la cuenta con ese id. "
                             + " | ".join(lista)}
    return {"sin_total": f"'{nombre}' puede ser mas de uno y cada uno sale "
                         f"distinto, asi que no lo cuento: no elijas, "
                         f"pregunta cual de estos y volve a pedirme la cuenta "
                         f"con ese id. " + " | ".join(lista)}


def _no_vendemos(texto: str, categoria: str, tienda_id: str):
    """Si lo que se pidio es una categoria que la tienda NO vende, decirlo con la alternativa REAL al lado."""
    from app.core.guia_compra import categoria_no_vendida
    for frase in (f"{texto} {categoria}".strip(), texto, categoria):
        if not frase:
            continue
        try:
            r = categoria_no_vendida(frase, tienda_id)
        except Exception as e:  # noqa: BLE001 — sin fuente no se niega nada
            log.warning("motor_no_vendidas_error", tienda_id=tienda_id,
                        error=f"{type(e).__name__}: {str(e)[:120]}")
            return None
        if r:
            pedida, alt = r
            return {"pedido": pedida,
                    "en_su_lugar": alt or "",
                    "motivo": f"la tienda no vende {pedida}"
                              + (f"; lo mas cercano que si hay es {alt}"
                                 if alt else "; no hay nada equivalente")}
    return None


def _una(consulta: dict, catalogo: list, tienda_id: str) -> dict:
    """UNA consulta del modelo contra el catalogo."""
    from app.core.fuente import _ficha_corta
    from app.core.filtros_catalogo import (alguno_lo_nombra, aplicar,
                                           dato_que_falla, ordenar,
                                           orden_tiene_sentido,
                                           pesos_por_rareza,
                                           rankear_por_cercania, relevancia)
    c = consulta or {}
    texto = str(c.get("texto") or "").strip()
    tope = c.get("cuantos")
    try:
        tope = int(tope)
    except (TypeError, ValueError):
        tope = FILAS_POR_DEFECTO
    tope = max(1, min(TOPE_FILAS, tope))
    try:
        unidades = max(1, int(c.get("cantidad") or 1))
    except (TypeError, ValueError):
        unidades = 1
    # EL DETALLE LO DECIDE `busco`, Y NADA MAS (14-sep-2026).
    detalle = str(c.get("busco") or "") == "uno"
    specs_pedidas = None

    no_aplicado, notas = [], []

    # 1. POR ID PRIMERO. Es como resuelve la memoria —"el que me mostraste
    #    antes"— y no necesita ni parecido ni condiciones.
    if c.get("ids"):
        filas_id = _por_ids(catalogo, c["ids"])
        filas = filas_id
        # "DE ESOS, EL MAS BARATO" (22-sep-2026). Los ids son el universo y el orden se aplica ADENTRO: hasta
        # hoy el orden se ignoraba con ids, asi que el extremo "de esos" solo se podia pedir buscando en el
        # catalogo entero, y medido en la tanda de charlas —CH10— el bot contesto "de los que te mencione, el
        # mas barato es el KB-110X" con un teclado que nunca habia mencionado.
        _o = c.get("ordenar_por") or {}
        if (_o.get("campo") and len(filas) > 1
                and orden_tiene_sentido(filas, str(_o["campo"]), tienda_id)):
            filas = ordenar(filas, str(_o["campo"]),
                            str(_o.get("direccion") or "min"), tienda_id)
        faltan = [str(i) for i in c["ids"] if str(i) not in
                  {str(p.get("id")) for p in filas}]
        fichas_id = [_ficha_corta(p, unidades, specs_pedidas, detalle)
                     for p in filas[:tope]]
        _con_la_cuenta(fichas_id, unidades)
        return {"veredicto": "existe" if filas else "no_existe",
                "cuantos_habia": len(filas),
                "filas": fichas_id,
                "no_aplicado": ([{"campo": "ids", "motivo":
                                  f"no existen estos ids: {', '.join(faltan)}"}]
                                if faltan else []),
                "sin_dato": 0, "empatados": 0,
                "motivo": "" if filas else "ninguno de esos ids esta en el catalogo"}

    # EL "NO LO VENDEMOS" VA PRIMERO, Y ESE ES EL PUNTO (13-sep-2026).
    no_lo_vendemos = _no_vendemos(texto, str(c.get("categoria") or ""),
                                  tienda_id)
    if no_lo_vendemos:
        # LAS FILAS SON LAS DE LA ALTERNATIVA REAL, no las del parecido.
        alt = no_lo_vendemos.get("en_su_lugar") or ""
        de_la_alt, _ = _universo(catalogo, alt, tienda_id) if alt else ([], "")
        filas_alt = [_ficha_corta(p, unidades, specs_pedidas, detalle)
                     for p in (de_la_alt if alt else [])[:tope]]
        _con_la_cuenta(filas_alt, unidades)
        return {"veredicto": "no_existe",
                "cuantos_habia": 0,
                "de_cuantos_se_miro": len(catalogo),
                "filas": filas_alt,
                "no_aplicado": [],
                "sin_dato": 0,
                "empatados": 0,
                "no_lo_vendemos": no_lo_vendemos,
                "motivo": no_lo_vendemos["motivo"]}

    universo, aviso = _universo(catalogo, str(c.get("categoria") or ""),
                                tienda_id)
    if aviso:
        no_aplicado.append({"campo": "categoria", "motivo": aviso})
    de_cuantos = len(universo)
    # LO YA MOSTRADO QUEDA AFUERA cuando el cliente pide otras opciones (16-oct, C35).
    fuera = {str(i) for i in c.get("fuera") or []}
    sacados = 0
    if fuera:
        vistos = {(p.get("marca"), p.get("modelo")) for p in catalogo
                  if str(p.get("id")) in fuera and p.get("modelo")}
        quedan_u = [p for p in universo if str(p.get("id")) not in fuera
                    and (p.get("marca"), p.get("modelo")) not in vistos]
        sacados = len(universo) - len(quedan_u)
        universo = quedan_u

    # 2. LAS CONDICIONES. `aplicar` ya informa el tercer balde —los que no tienen el dato— y los filtros que
    # no se pudieron aplicar con su motivo.
    from app.core.filtros_catalogo import condicion_sin_vocabulario
    crudas = []
    for x in (c.get("condiciones") or []):
        campo = str((x or {}).get("campo") or "")
        reales = condicion_sin_vocabulario(campo, str((x or {}).get("operador")
                                                      or ""),
                                           (x or {}).get("valor", ""),
                                           tienda_id)
        if reales is None:
            crudas.append(x)
            continue
        no_aplicado.append({
            "campo": campo,
            "motivo": f"la fuente no escribe '{(x or {}).get('valor')}' en "
                      f"{campo}; lo que dice es: {' | '.join(reales)}. No se "
                      f"filtro por eso: volve a pedir con una de esas"})
    conds = [_Cond(x) for x in crudas]
    r = aplicar(universo, conds, tienda_id) if conds else {
        "productos": universo, "aplicados": [], "descartados": [],
        "sin_dato": 0, "preferencias": []}
    no_aplicado.extend(r["descartados"])
    quedan = r["productos"]

    # LA PREFERENCIA SE DICE, Y ESE ES MEDIO ARREGLO (20-sep-2026).
    for pref in r.get("preferencias") or []:
        donde = "primero" if pref["operador"] == "prefiere" else "al final"
        if pref.get("por") == "cercania":
            # SOBRE UN NUMERO NO SE CUMPLE, SE ESTA CERCA.
            cerca = "mas cerca" if pref["operador"] == "prefiere" else "mas lejos"
            notas.append(
                f"{pref['campo']} NO se filtro, se ORDENO por cercania a "
                f"{pref['valor']}: primero los que estan {cerca}. Estan "
                f"TODOS, y ninguno 'cumple' ese numero: es un orden")
            continue
        notas.append(
            f"{pref['campo']} '{pref['valor']}' NO se filtro, se ORDENO: "
            f"{pref['cumplen']} de {pref['evaluados']} lo cumplen y van "
            f"{donde}. Estan TODOS, tambien los que no lo cumplen: no digas "
            f"que la lista entera lo cumple")
    cumplieron = len(quedan)
    empatados = 0
    veredicto = "existe"

    # 3. EL RESCATE. Si ninguna cumple todo, se trae lo mas parecido y se dice cual condicion falla.
    from app.core.filtros_catalogo import ORDENAN
    duras = [x for x in conds if x.operador not in ORDENAN]
    rescate = False
    if duras and not quedan:
        quedan, empatados, incumple = rankear_por_cercania(
            universo, duras, tienda_id)
        veredicto = "no_existe"
        rescate = True
        notas.append(f"ninguno cumple todo; esto es lo mas parecido, "
                     f"incumple {incumple} de {len(duras)}")
        if empatados > 1:
            notas.append(f"{empatados} estan igual de lejos y se desempato "
                         f"por precio")

    # 4. EL ORDEN. Solo si ordenar por ese campo ordena por ALGO: sobre valores que son etiquetas —"China",
    # "Negro"— el orden es alfabetico y no contesta ninguna pregunta que un cliente pueda hacer.
    orden = c.get("ordenar_por") or {}
    campo_orden = str(orden.get("campo") or "")
    orden_aplicado = False
    if campo_orden:
        if quedan and orden_tiene_sentido(quedan, campo_orden, tienda_id):
            quedan = ordenar(quedan, campo_orden,
                             str(orden.get("direccion") or "min"), tienda_id)
            orden_aplicado = True
        else:
            no_aplicado.append({
                "campo": campo_orden,
                "motivo": "ordenar por ese campo no ordena por nada: sus "
                          "valores son etiquetas, no magnitudes"})
    # EL PARECIDO SE CALCULA SIEMPRE QUE HAYA TEXTO, Y ANTES COLGABA DEL ORDEN (13-sep-2026).
    puntos = {}
    if texto and quedan:
        raras = pesos_por_rareza(quedan, texto)
        puntos = {id(p): relevancia(p, texto, raras) for p in quedan}
        if not campo_orden:
            quedan = sorted(quedan, key=lambda p: (-puntos[id(p)],
                                                   p.get("precio_ars") or 0))
        # AMBIGUO ES DE IDENTIDAD, Y SOLO DE IDENTIDAD.
        sin_identidad = (not r.get("aplicados")
                         and de_cuantos == len(catalogo)
                         and not alguno_lo_nombra(quedan, texto))
        if sin_identidad:
            veredicto = "no_existe"
            if max(puntos.values()) <= 0 and not orden_aplicado:
                # NI NOMBRADO NI MENCIONADO. Mostrar "lo mas parecido" aca seria mostrar los cinco mas
                # baratos, que no se parecen a nada: es ruido adentro de la caja donde todo lo demas es dato
                # certificado.
                quedan = []
                # EL MOTIVO DICE EL HECHO Y NO CONCLUYE DE MAS.
                notas.append(f"ninguna ficha del catalogo dice '{texto}': ni "
                             f"en el nombre, ni en la marca, ni en el modelo, "
                             f"ni en los tags, ni en la categoria, ni en la "
                             f"prosa. Si asi es como lo dice el cliente y no "
                             f"como lo escribe la tienda, volve a buscar con "
                             f"una categoria")
            elif orden_aplicado:
                # EL ORDEN EXPLICITO PIDE UN EXTREMO, Y EL EXTREMO EXISTE AUNQUE LAS PALABRAS NO NOMBREN NADA.
                notas.append(f"ninguna ficha se llama '{texto}'; estas son las "
                             f"del orden que pediste, no las que nombraste")
            else:
                notas.append(f"ninguna ficha se llama '{texto}'; estas lo "
                             f"mencionan y es lo mas parecido que hay")

        if (not sin_identidad and str(c.get("busco") or "") == "uno"
                and len(quedan) > 1):
            mejor = max(puntos.values())
            iguales = [p for p in quedan if puntos[id(p)] == mejor]
            if 1 < len(iguales) <= TOPE_AMBIGUO and mejor > 0:
                veredicto = "ambiguo"
                empatados = len(iguales)
                notas.append(f"hay {empatados} que pegan igual con lo que "
                             f"pidio: no elijas, pregunta cual")
                # SE SIRVEN TODOS LOS CANDIDATOS, no el primero.
                quedan = iguales
                tope = min(TOPE_FILAS, max(tope, empatados))

    if not quedan:
        veredicto = "no_existe"
        notas.append("ya le mostraste todo lo que hay de eso: no hay otras opciones" if sacados
                     else "el catalogo no tiene nada de eso")

    # LA FILA DEL RESCATE DICE POR QUE NO CUMPLE, Y ES EL DATO REAL.
    from app.core.filtros_catalogo import SIN_CAMPO as _SIN, _valor_crudo
    campos_pedidos = [c.campo for c in conds if c.campo != _SIN]
    if campo_orden:
        campos_pedidos.append(campo_orden)
    campos_pedidos = sorted(set(campos_pedidos))

    filas = []
    for p in quedan[:tope]:
        f = _ficha_corta(p, unidades, specs_pedidas, detalle)
        for campo in campos_pedidos:
            if campo in f:
                continue
            crudo = _valor_crudo(p, campo)
            if crudo not in (None, "", [], {}):
                f[campo] = crudo
        if rescate:
            motivo_fila = dato_que_falla(p, duras, tienda_id)
            if motivo_fila:
                f["no_cumple"] = motivo_fila
        filas.append(f)
    _con_la_cuenta(filas, unidades)

    return {"veredicto": veredicto,
            "cuantos_habia": cumplieron if conds else de_cuantos,
            "de_cuantos_se_miro": de_cuantos,
            "filas": filas,
            "no_aplicado": no_aplicado,
            "sin_dato": r.get("sin_dato", 0),
            "empatados": empatados,
            "motivo": "; ".join(notas)}


def _salida(resultados, temas, sin_resolver, compat, envios, criterio,
            sin_criterio, cuenta=None, afirma=None) -> dict:
    """El retorno, con UNA sola forma. Las cajas que nadie pidio no viajan: una clave vacia en cada turno es
    ruido adentro de la caja donde todo lo demas es dato certificado."""
    fuera = {"resultados": resultados, "politicas": temas,
             "temas_sin_resolver": sin_resolver}
    if compat:
        fuera["compatibilidad"] = compat
    if envios:
        fuera["envios"] = envios
    if criterio:
        fuera["criterio"] = criterio
    if sin_criterio:
        fuera["criterio_sin_resolver"] = sin_criterio
    if cuenta:
        fuera["cuenta"] = cuenta
    if afirma:
        fuera["afirma"] = afirma
    return fuera


# ── LO QUE EL CLIENTE AFIRMA ────────────────────────────────────────────────

# Cuantas afirmaciones se verifican en una llamada.
TOPE_AFIRMA = 4


def _una_afirmacion(pedido: dict, catalogo: list, tienda_id: str) -> dict:
    """UNA afirmacion del cliente, verificada contra la fuente."""
    from app.core.filtros_catalogo import (_valor_crudo, campos_con_el_valor,
                                           campos_filtrables, evaluar,
                                           los_que_lo_nombran_entero)
    sobre = str((pedido or {}).get("sobre") or "").strip()
    dice = str((pedido or {}).get("dice") or "").strip()
    base = {"sobre": sobre, "dice": dice}
    if not dice:
        return {**base, "veredicto": "no_consta",
                "motivo": "la afirmacion vino sin contenido"}
    # 1 · ¿DE QUE HABLA? La identidad la decide el certificador de siempre.
    fichas = los_que_lo_nombran_entero(catalogo, sobre) if sobre else []
    # NOMBRAR UN RUBRO NO ES NOMBRAR UNA FICHA, y es lo que cazo el primer test de "mi notebook":
    # `los_que_lo_nombran_entero` devuelve 191, porque "mi" no es una palabra util y "notebook" lo dicen
    # todas.
    if len(fichas) > TOPE_AMBIGUO:
        fichas = []
    if not fichas:
        return {**base, "veredicto": "del_cliente",
                "motivo": "no es de un producto nuestro, asi que es un dato "
                          "que aporta el cliente: tomalo como cierto y usalo "
                          "en el resto de la charla"}
    # 2 · ¿DONDE VIVIRIA ESO? Es el aterrizaje, el mismo del 22-sep.
    campos = campos_con_el_valor(catalogo, dice, tienda_id)
    if not campos:
        return {**base, "veredicto": "no_consta",
                "motivo": f"ningun producto del catalogo dice '{dice}', asi "
                          f"que no puedo confirmarlo NI negarlo"}
    registro = campos_filtrables(tienda_id)
    # 3 · CONTRA CADA FICHA CANDIDATA, con `evaluar` y sus tres respuestas.
    porficha = []
    for f in fichas[:TOPE_AMBIGUO]:
        visto, real = None, ""
        for campo in campos:
            r = evaluar(f, campo, "contiene", dice, registro.get(campo, ""))
            if r is True:
                visto = "confirma"
                break
            if r is False and visto is None:
                # CON `_valor_crudo` Y NO CON `get`: `conexion` y varios mas los DERIVA
                # `fuente_producto.enriquecer` y no estan en el dict del catalogo.
                visto = "contradice"
                real = f"{campo}: {_valor_crudo(f, campo)}"
        porficha.append((visto or "no_consta", real, f))
    veredictos = {v for v, _, _ in porficha}
    # UNA AMBIGUEDAD DE IDENTIDAD NO IMPIDE VERIFICAR, y es el caso medido: "el K120" son dos fichas —negra y
    # blanca— y las dos contestan lo mismo sobre si es inalambrico.
    if len(veredictos) > 1:
        return {**base, "veredicto": "ambiguo",
                "motivo": "'" + sobre + "' puede ser mas de uno y no todos "
                          "dicen lo mismo de eso: pregunta cual. "
                          + " | ".join(f"{f.get('nombre')} ({f.get('id')})"
                                       for _, _, f in porficha)}
    v, real, f = porficha[0]
    if v == "confirma":
        return {**base, "veredicto": "confirma", "id": str(f.get("id")),
                "motivo": f"la ficha de {f.get('nombre')} lo dice"}
    if v == "contradice":
        return {**base, "veredicto": "contradice", "id": str(f.get("id")),
                "dato_real": real,
                "motivo": f"{f.get('nombre')} NO es asi. El dato real es "
                          f"{real}. Deciselo con esas palabras antes de "
                          f"seguir: no le repitas la suya"}
    return {**base, "veredicto": "no_consta", "id": str(f.get("id")),
            "motivo": f"la ficha de {f.get('nombre')} no trae ese dato, asi "
                      f"que no lo puedo confirmar ni negar"}


def _un_compat(pedido: dict, catalogo: list, tienda_id: str) -> dict:
    """UN par de compatibilidad, certificado. Devuelve {producto, con, veredicto, motivo} con veredicto en
    compatible / incompatible / ambiguo / sin_dato."""
    pid = str((pedido or {}).get("producto") or "").strip()
    con = str((pedido or {}).get("con") or "").strip()
    base = {"producto": pid, "con": con}
    porid = {str(p.get("id")): p for p in catalogo}
    # UN PEDIDO VACIO NO ES UN NOMBRE, y se corta antes de resolver nada: sin
    # producto no hay identidad que certificar, y mandarlo a la busqueda
    # devolveria el catalogo entero como si el cliente hubiera nombrado algo.
    if not pid or not con:
        return {**base, "veredicto": "sin_dato",
                "motivo": "el par vino incompleto: necesito el producto y con "
                          "que lo quiere usar"}
    prod = porid.get(pid)
    if not prod:
        # ── EL DOS PASOS SE RESUELVE ADENTRO (15-sep-2026, FICHA 54, 3.2) ──
        cert = _una({"texto": pid, "busco": "uno", "cuantos": TOPE_AMBIGUO},
                    catalogo, tienda_id)
        filas = cert.get("filas") or []
        if cert.get("veredicto") == "ambiguo" or len(filas) > 1:
            # AMBIGUO DE IDENTIDAD. No se elige nunca: eso es la regla 10.0.
            candidatos = [porid.get(str(f.get("id"))) for f in
                          filas[:TOPE_AMBIGUO]]
            candidatos = [c for c in candidatos if c]
            juicios = [_evaluar(c, con, porid, tienda_id) for c in candidatos]
            distintos = {j["veredicto"] for j in juicios}
            # SI EL VEREDICTO COMUN ES `ambiguo` LA REPREGUNTA ES OTRA: esa ambiguedad es del OTRO lado del
            # par -"de apple" son macOS e iOS- y su motivo ya dice que hay que preguntar cual equipo tiene.
            if distintos == {"ambiguo"}:
                return {**base, **juicios[0], "pedido_como": pid}
            if len(distintos) == 1 and juicios:
                nombres = [str(c.get("nombre")) for c in candidatos]
                return {**base, **juicios[0],
                        "nombre": " / ".join(nombres),
                        "pedido_como": pid,
                        "vale_para_todos": nombres,
                        "motivo": f"para los {len(nombres)} que pegan con "
                                  f"'{pid}' la respuesta es la misma, asi que "
                                  f"no hace falta que preguntes cual: "
                                  + juicios[0]["motivo"]}
            lista = [{"id": c.get("id"), "nombre": c.get("nombre")}
                     for c in candidatos]
            return {**base, "veredicto": "ambiguo", "candidatos": lista,
                    "motivo": f"'{pid}' puede ser mas de uno y la respuesta "
                              f"cambia segun cual: no elijas, pregunta cual y "
                              f"volve a pedirme el par con ese id"}
        if not filas or cert.get("veredicto") == "no_existe":
            # NO EXISTE NO ES UN ERROR: es la respuesta 3 de la FICHA 52.
            return {**base, "veredicto": "sin_dato",
                    "motivo": f"no vendemos '{pid}', asi que no puedo decirte "
                              f"con que anda: " + (cert.get("motivo") or
                                                   "no esta en el catalogo")}
        prod = porid.get(str(filas[0].get("id")))
        if not prod:
            return {**base, "veredicto": "sin_dato",
                    "motivo": f"no tengo ningun producto con el id '{pid}': "
                              f"buscalo primero y usa el id que te devuelvo"}
        # EL ID CERTIFICADO VUELVE ESCRITO, y no es cosmetico: el modelo pidio
        # por un nombre y tiene que saber de que ficha salio el veredicto.
        base["producto"] = str(prod.get("id"))
        base["pedido_como"] = pid
    base["nombre"] = prod.get("nombre")
    return {**base, **_evaluar(prod, con, porid, tienda_id)}


def _evaluar(prod: dict, con: str, porid: dict, tienda_id: str) -> dict:
    """EL EJE DE COMPATIBILIDAD, CON LA IDENTIDAD YA RESUELTA."""
    from app.core.compatibilidad import (etiqueta_plataforma, evaluar,
                                         evaluar_par, plataformas_del_mensaje)
    # EL OTRO PRODUCTO PRIMERO. Un id del catalogo es identidad certificada; un
    # alias de plataforma es una lectura del texto. Ante los dos, manda el dato.
    otro = porid.get(con)
    if otro:
        veredicto, motivo = evaluar_par(prod, otro, tienda_id)
        return {"con_nombre": otro.get("nombre"), "veredicto": veredicto,
                "motivo": motivo or "la tabla de la casa no dice si estos dos "
                                    "van juntos"}

    equipos = plataformas_del_mensaje(con, tienda_id)
    if not equipos:
        return {"veredicto": "sin_dato",
                "motivo": f"no reconozco '{con}' como un equipo ni como un id "
                          f"del catalogo; los equipos que conozco son: "
                          + _equipos(tienda_id)}
    if len(equipos) > 1:
        etqs = [etiqueta_plataforma(e, tienda_id) for e in equipos]
        return {"veredicto": "ambiguo", "candidatos": etqs,
                "motivo": f"'{con}' puede ser {' o '.join(etqs)}: no elijas, "
                          f"pregunta cual tiene"}
    veredicto, motivo = evaluar(prod, equipos[0], tienda_id)
    return {"con_equipo": etiqueta_plataforma(equipos[0], tienda_id),
            "veredicto": veredicto,
            "motivo": motivo or (
                f"la tabla de la casa no dice si {prod.get('nombre')} anda con "
                f"{etiqueta_plataforma(equipos[0], tienda_id)}")}


def buscar(consultas: list, tienda_id: str, trace_id: str = "",
           temas: list | None = None, compat: list | None = None,
           afirma: list | None = None,
           envios: list | None = None, localidad_previa: str = "",
           criterio: list | None = None, cuenta: dict | None = None,
           reparto_pago: list | None = None) -> dict:
    """LA PUERTA. Catalogo, politicas, compatibilidad, envio y el criterio de la casa, en una llamada."""
    from app.core.fuente import cotizar_destinos, criterio_de, politicas_de

    # EL ENVIO PRIMERO, PORQUE APAGA UNA POLITICA.
    nombres, el_va = [], {}
    for e in (envios or []):
        if isinstance(e, dict):
            d = str(e.get("destino") or "").strip()
            if not d:
                continue
            nombres.append(d)
            if str(e.get("va") or "").strip():
                el_va[d] = str(e["va"]).strip()
        elif str(e or "").strip():
            nombres.append(str(e).strip())

    fuera_envios: dict = {}
    if nombres:
        try:
            fuera_envios = cotizar_destinos(nombres, tienda_id,
                                            localidad_previa) or {}
            # EL VINCULO VUELVE PEGADO A SU TARIFA. Separados, el modelo tiene tres montos y tres frases y los
            # aparea de memoria, que es la junta blanda que este repo ya tiene numerada cuatro veces.
            for fila in fuera_envios.get("filas") or []:
                if fila.get("destino") in el_va:
                    fila["va"] = el_va[fila["destino"]]
        except Exception as e:  # noqa: BLE001 — sin tarifa no se inventa una
            log.warning("motor_envio_error", trace_id=trace_id,
                        error=f"{type(e).__name__}: {str(e)[:120]}")
    cotizado = any(f.get("monto_ars") for f in fuera_envios.get("filas") or [])

    # LA VALVULA DE ESCAPE NO SE CERTIFICA, SE CONTESTA.
    from app.core.fuente import SIN_TEMA
    pedidos = [t for t in (temas or []) if t != SIN_TEMA]
    fuera_temas, sin_resolver = [], []
    criterios, sin_criterio = [], []
    if len(pedidos) != len(temas or []):
        sin_resolver.append(SIN_TEMA)
    if pedidos:
        try:
            r = politicas_de(pedidos[:TOPE_TEMAS], tienda_id)
            fuera_temas = list(r["politicas"])
            sin_resolver += r["sin_resolver"]
            # EL TEMA QUE LA FAQ NO CONTESTA VUELVE POR SU BOCA, no rotulado como politica: el reparto por
            # area lo hace `fuente`, que es la que sabe de que archivo salio cada texto.
            criterios = list(r.get("criterio") or [])
        except Exception as e:  # noqa: BLE001 — sin politica no se inventa una
            log.warning("motor_temas_error", trace_id=trace_id,
                        error=f"{type(e).__name__}: {str(e)[:120]}")

    # EL RAMAL A CRITERIO. La boca no necesita el catalogo -su fuente es `base_conocimiento.json`- asi que se
    # resuelve antes de leerlo, igual que las politicas: preguntar para que sirve un mouse no tiene por que
    # costar una lectura de 880 fichas.
    if criterio:
        try:
            rc = criterio_de(list(criterio)[:TOPE_CRITERIO], tienda_id)
            # SIN REPETIR: el mismo tema puede llegar por los dos campos, y
            # mandarle dos veces la misma prosa es el gasto que no se hace.
            ya = {c["tema"] for c in criterios}
            criterios += [c for c in rc["criterio"] if c["tema"] not in ya]
            ya_pol = {p["tema"] for p in fuera_temas}
            fuera_temas += [p for p in rc["politicas"]
                            if p["tema"] not in ya_pol]
            sin_criterio = rc["sin_resolver"]
        except Exception as e:  # noqa: BLE001 — sin criterio no se opina
            log.warning("motor_criterio_error", trace_id=trace_id,
                        error=f"{type(e).__name__}: {str(e)[:120]}")

    # EL APAGADO DEL ENVIO SE APLICA A LAS DOS ENTRADAS, y esto es lo que hay que cuidar al sumar un campo que
    # tambien puede devolver politicas: con la tarifa exacta cotizada, la politica del RANGO no se sirve, y
    # filtrando solo lo que entro por `temas` el mismo numero flojo volvia a entrar por `criterio`, que es la
    # regla 2 rota por la puerta de atras.
    if cotizado:
        fuera_temas = [p for p in fuera_temas
                       if p["tema"] not in TEMAS_DEL_ENVIO]

    if (not consultas and not compat and not afirma
            and not (cuenta or {}).get("items")):
        # SOLO POLITICAS, SOLO ENVIO O SOLO CRITERIO ES UNA LLAMADA VALIDA.
        return _salida([], fuera_temas, sin_resolver, [], fuera_envios,
                       criterios, sin_criterio)

    # LA COMPATIBILIDAD TAMBIEN NECESITA EL CATALOGO, y por eso la lectura no cuelga mas de `consultas`: el
    # par se evalua sobre las fichas reales, que son las que traen la tabla estampada.
    from app.storage.firestore_client import get_all_products
    try:
        catalogo = get_all_products(tienda_id=tienda_id) or []
    except Exception as e:  # noqa: BLE001 — sin catalogo se contesta sin fichas
        log.warning("motor_catalogo_error", trace_id=trace_id,
                    error=f"{type(e).__name__}: {e}")
        catalogo = []
    if not catalogo:
        r = _salida([], fuera_temas, sin_resolver, [], fuera_envios,
                    criterios, sin_criterio)
        r["motivo"] = "no se pudo leer el catalogo"
        return r

    # EL RAMAL DE LO QUE EL CLIENTE AFIRMA. Una afirmacion rota no tumba el resto: vuelve `no_consta`, que es
    # la salida honesta de esta boca y no una negacion.
    afirmaciones = []
    for pedido in (afirma or [])[:TOPE_AFIRMA]:
        try:
            afirmaciones.append(_una_afirmacion(pedido, catalogo, tienda_id))
        except Exception as e:  # noqa: BLE001 — por ausencia no se niega nada
            log.warning("motor_afirma_error", trace_id=trace_id,
                        error=f"{type(e).__name__}: {str(e)[:120]}")
            afirmaciones.append(
                {"sobre": str((pedido or {}).get("sobre") or ""),
                 "dice": str((pedido or {}).get("dice") or ""),
                 "veredicto": "no_consta",
                 "motivo": "eso no se pudo verificar"})

    # EL RAMAL A COMPATIBILIDAD. Un par roto no tumba el resto, igual que una
    # consulta rota: vuelve `sin_dato`, que es la salida honesta de esta boca.
    compatibilidades = []
    for pedido in (compat or [])[:TOPE_COMPAT]:
        try:
            compatibilidades.append(_un_compat(pedido, catalogo, tienda_id))
        except Exception as e:  # noqa: BLE001 — sin dato no se afirma nada
            log.warning("motor_compat_error", trace_id=trace_id,
                        error=f"{type(e).__name__}: {str(e)[:120]}")
            compatibilidades.append(
                {"producto": str((pedido or {}).get("producto") or ""),
                 "con": str((pedido or {}).get("con") or ""),
                 "veredicto": "sin_dato",
                 "motivo": "eso no se pudo verificar"})

    # LA CONSULTA REPETIDA SE EJECUTA UNA SOLA VEZ (13-sep-2026).
    vistas: dict = {}
    fuera = []
    for c in (consultas or [])[:TOPE_CONSULTAS]:
        seña = json.dumps(c, ensure_ascii=False, sort_keys=True, default=str)
        if seña in vistas:
            # SIN LAS FILAS, y ahi esta el ahorro de verdad.
            fuera.append({
                "veredicto": vistas[seña][0]["veredicto"],
                "filas": [], "cuantos_habia": vistas[seña][0]["cuantos_habia"],
                "no_aplicado": [], "sin_dato": 0, "empatados": 0,
                "repetida": (f"identica a tu consulta numero "
                             f"{vistas[seña][1]} de esta misma llamada. Se "
                             f"busco una sola vez y el resultado esta ahi"),
                "motivo": ""})
            continue
        try:
            r_una = _una(c, catalogo, tienda_id)
            vistas[seña] = (r_una, len(fuera) + 1)
            fuera.append(r_una)
        except Exception as e:  # noqa: BLE001 — una consulta rota no tumba el resto
            log.warning("motor_consulta_error", trace_id=trace_id,
                        error=f"{type(e).__name__}: {str(e)[:120]}")
            fuera.append({"veredicto": "no_existe", "filas": [],
                          "cuantos_habia": 0, "no_aplicado": [], "sin_dato": 0,
                          "empatados": 0,
                          "motivo": "esa consulta no se pudo ejecutar"})
    # LA CUENTA VA ULTIMA, Y ESE ES SU LUGAR: es lo unico que cruza bocas, asi que necesita que las otras ya
    # hayan contestado.
    la_cuenta = {}
    if cuenta:
        try:
            # EL REPARTO ENTRA POR ARRIBA Y SE APLICA ADENTRO.
            if reparto_pago and not (cuenta or {}).get("reparto_pago"):
                cuenta = dict(cuenta or {})
                cuenta["reparto_pago"] = reparto_pago
            la_cuenta = _la_cuenta(cuenta, fuera_envios, tienda_id, trace_id,
                                   catalogo)
        except Exception as e:  # noqa: BLE001 — sin total no se inventa uno
            log.warning("motor_cuenta_error", trace_id=trace_id,
                        error=f"{type(e).__name__}: {str(e)[:150]}")

    repetidas = sum(1 for f in fuera if f.get("repetida"))
    log.info("motor_buscar", trace_id=trace_id, consultas=len(fuera),
             repetidas=repetidas,
             veredictos=[f["veredicto"] for f in fuera],
             filas=[len(f["filas"]) for f in fuera],
             temas=[p["tema"] for p in fuera_temas],
             compat=[c["veredicto"] for c in compatibilidades],
             afirma=[a["veredicto"] for a in afirmaciones],
             envios=[f["destino"] for f in fuera_envios.get("filas") or []],
             criterio=[c["tema"] for c in criterios],
             cuenta=la_cuenta.get("total_ars") or la_cuenta.get("sin_total"))
    return _salida(fuera, fuera_temas, sin_resolver, compatibilidades,
                   fuera_envios, criterios, sin_criterio, la_cuenta,
                   afirmaciones)


def fichas_de(resultado: dict) -> list[dict]:
    """Las fichas de todas las consultas, sin repetir."""
    fuera, vistos = [], set()
    for r in (resultado or {}).get("resultados") or []:
        for f in r.get("filas") or []:
            i = str(f.get("id"))
            if i not in vistos:
                vistos.add(i)
                fuera.append(f)
    return fuera

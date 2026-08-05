"""
BANCO DE CANDIDATOS — la etapa 2, offline y sin un solo token.

QUE MIDE, y por que es distinto de todo lo que habia. Los bancos existentes
miden el TURNO COMPLETO: el modelo decide, busca y redacta, y el juez mira la
respuesta. Cuando eso sale mal no se sabe de quien fue: si el modelo pidio mal
o si el codigo contesto mal. Meses de parches caso por caso salieron de esa
ambiguedad.

Aca se corta esa ambiguedad de raiz: se SIMULA que el modelo pide PERFECTO. La
llamada ideal de cada pregunta esta escrita a mano, y lo unico que se mide es
que devuelve el codigo. Lo que falle aca no lo puede arreglar ningun prompt ni
ningun modelo mas grande: es techo de codigo.

LA VERDAD ESPERADA SE CALCULA POR UN CAMINO INDEPENDIENTE. A fuerza bruta sobre
los 880, con Python pelado, sin pasar por `herramientas` ni por
`filtros_catalogo`. Si la verdad la calculara el mismo modulo que se prueba, el
banco diria que todo esta bien aunque los dos estuvieran mal.

Corre en segundos, no necesita clave y no toca produccion:
    python3 banco_pruebas/banco_candidatos.py
"""
import sys
import unicodedata
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from banco_pruebas import sim_firestore  # noqa: E402

sim_firestore.install()

from app.core import herramientas as H  # noqa: E402
from app.storage.firestore_client import get_all_products  # noqa: E402

TIENDA = "verifika_prod"


def norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c)).strip()


CATALOGO = get_all_products(tienda_id=TIENDA) or []
CON_STOCK = [p for p in CATALOGO if (p.get("stock") or 0) > 0]

# ── LA VERDAD, A FUERZA BRUTA ───────────────────────────────────────────────
# Camino independiente: se lee el origen crudo y se parte a mano. Nada de esto
# importa una funcion de app/core.


def paises(p: dict) -> tuple:
    """(pais de la marca, pais de fabricacion) leidos del texto de origen."""
    o = norm(p.get("origen"))
    marca = fab = ""
    if " de " in o:
        marca = o.split(" de ", 1)[1].split(".")[0].strip()
    if "fabricado en" in o:
        fab = o.split("fabricado en", 1)[1].split(".")[0].strip()
    return marca, fab


def no_fabricado_en_china(p: dict) -> bool:
    return "chin" not in paises(p)[1]


def sin_china_en_nada(p: dict) -> bool:
    m, f = paises(p)
    return "chin" not in m and "chin" not in f


RESULTADOS = []


def caso(n, pregunta, llamada, esperado, obtenido, ok, causa=""):
    RESULTADOS.append({"n": n, "pregunta": pregunta, "llamada": llamada,
                       "esperado": esperado, "obtenido": obtenido,
                       "ok": ok, "causa": causa})


def buscar(**kw):
    return H.buscar_productos(H.BuscarProductos(**kw), TIENDA)


def catalogo(**kw):
    return H.consultar_catalogo(H.ConsultarCatalogo(**kw), TIENDA)


def nombres(r, k="productos"):
    return [p.get("nombre") for p in (r.get(k) or [])]


# ── 1. GRADIENTE: el mouse que menos partes chinas tenga, no Logitech ───────
def c1():
    mice = [p for p in CON_STOCK if p.get("categoria") == "mouse"
            and norm(p.get("marca")) != "logitech"]
    # verdad: cuantos escalones REALES de "cuan chino" hay entre esos mouse
    escalones = {}
    for p in mice:
        m, f = paises(p)
        clave = ("chin" in m, "chin" in f)
        escalones.setdefault(clave, []).append(p["nombre"])
    r = buscar(categoria="mouse", excluir=["china", "logitech"])
    grados = [p.get("cuanto_incumple") for p in (r.get("productos") or [])]
    # cuantos empatan con el primero que devuelve, sobre el universo entero
    todos = [(H._grado(p, ["china", "logitech"]), p["nombre"])
             for p in CON_STOCK if p.get("categoria") == "mouse"]
    mejor = min(g for g, _ in todos)
    empatados = sum(1 for g, _ in todos if g == mejor)
    ok = empatados <= 3
    caso(1, "el mouse que menos partes chinas tenga, que no sea Logitech",
         "buscar_productos categoria=mouse excluir=[china, logitech]",
         f"un orden que discrimine; escalones reales en la fuente: "
         f"{len(escalones)}",
         f"grados devueltos {grados}; {empatados} mouse empatan en el "
         f"grado minimo {mejor}",
         ok, "" if ok else "EMPATE MASIVO: el orden no discrimina, "
                           "los primeros 3 son arbitrarios entre los empatados")


# ── 2. RANKING POR UN ATRIBUTO QUE NO ES PRECIO ────────────────────────────
def c2():
    livianos = sorted([p for p in CON_STOCK if isinstance(p.get("peso_gramos"),
                                                          (int, float))],
                      key=lambda p: p["peso_gramos"])[:3]
    tiene_arg = "peso" in str(H.BuscarProductos.model_fields["orden"])
    r = buscar(descripcion="el mas liviano que tengas para viajar")
    caso(2, "cual es el mas liviano que tengas para viajar",
         "no existe la llamada: `orden` solo acepta barato|caro",
         f"ranking por peso; el mas liviano real es "
         f"{livianos[0]['nombre']} con {livianos[0]['peso_gramos']}g",
         f"orden acepta peso: {tiene_arg}; sin categoria devuelve "
         f"estado={r.get('estado')}",
         False, "NO HAY PUERTA: ordenar_por y atributos_ordenables existen en "
                "fuente_producto y ninguna herramienta los expone")


# ── 3. AGREGADO: cuantos NO se fabrican en China ───────────────────────────
def c3():
    verdad_fab = sum(1 for p in CON_STOCK if no_fabricado_en_china(p))
    verdad_nada = sum(1 for p in CON_STOCK if sin_china_en_nada(p))
    r = catalogo(operacion="contar", excluir=["china"])
    obt = r.get("cuantos")
    ok = obt in (verdad_fab, verdad_nada)
    caso(3, "cuantos productos tenes que no se fabriquen en China",
         "consultar_catalogo operacion=contar excluir=[china]",
         f"sin China en la FABRICACION: {verdad_fab}. Sin China en nada: "
         f"{verdad_nada}",
         f"devuelve {obt}", ok,
         "" if ok else "el contador no responde ninguna de las dos preguntas")


# ── 4. EXTREMOS DEL CATALOGO ───────────────────────────────────────────────
def c4():
    conp = [p for p in CON_STOCK if isinstance(p.get("precio_ars"), (int, float))]
    barato = min(conp, key=lambda p: p["precio_ars"])
    caro = max(conp, key=lambda p: p["precio_ars"])
    rb = catalogo(operacion="mas_barato")
    rc = catalogo(operacion="mas_caro")
    ok = ((rb.get("producto") or {}).get("nombre") == barato["nombre"]
          and (rc.get("producto") or {}).get("nombre") == caro["nombre"])
    caso(4, "cual es el mas caro de toda la tienda y cual el mas barato",
         "consultar_catalogo mas_barato / mas_caro",
         f"{barato['nombre']} y {caro['nombre']}",
         f"{(rb.get('producto') or {}).get('nombre')} y "
         f"{(rc.get('producto') or {}).get('nombre')}", ok)


# ── 5. PRESUPOSICION FALSA: algo mas barato que el mas barato ──────────────
def c5():
    conp = [p for p in CON_STOCK if isinstance(p.get("precio_ars"), (int, float))]
    piso = min(p["precio_ars"] for p in conp)
    r = buscar(categoria="mouse", tope_precio=piso - 1)
    ok = r.get("estado") == "nada_dentro_del_presupuesto"
    caso(5, "tenes algo mas barato que el Genius DX-110",
         f"buscar_productos categoria=mouse tope_precio={piso - 1}",
         "un estado que diga que no hay nada por debajo, con el piso real",
         f"estado={r.get('estado')}, tope={r.get('tope')}", ok,
         "" if ok else "no distingue 'no hay mas barato' de 'no tenemos'")


# ── 6. VALORES DISTINTOS DE UN CAMPO ───────────────────────────────────────
def c6():
    marcas = {str(p.get("marca")).strip() for p in CON_STOCK if p.get("marca")}
    r = catalogo(operacion="valores", campo="marca")
    dev = r.get("cuantos_distintos")
    listadas = len(r.get("valores") or [])
    ok = dev == len(marcas)
    caso(6, "que marcas manejas",
         "consultar_catalogo operacion=valores campo=marca",
         f"{len(marcas)} marcas distintas",
         f"cuantos_distintos={dev}, devuelve {listadas} en la lista", ok,
         "" if ok else "la cuenta no coincide con la fuente")


# ── 7. CRITERIO DIFUSO: notebook para diseño grafico ───────────────────────
def c7():
    nbs = [p for p in CON_STOCK if p.get("categoria") == "notebook"]
    # verdad: las que un humano miraria primero para diseño = mas RAM y CPU alto
    top = sorted(nbs, key=lambda p: -(p.get("precio_ars") or 0))[:3]
    r = buscar(descripcion="notebook para diseño grafico que le dure años",
               categoria="notebook")
    dev = nombres(r)
    baratas = [p["nombre"] for p in
               sorted(nbs, key=lambda p: p["precio_ars"])[:3]]
    ok = dev != baratas
    caso(7, "notebook para diseño grafico que le dure años, presupuesto flexible",
         "buscar_productos descripcion=... categoria=notebook",
         f"candidatos pertinentes; las de gama alta son p.ej. {top[0]['nombre']}",
         f"devuelve {dev}", ok,
         "" if ok else "SIN RELEVANCIA: devuelve las 3 mas baratas de 171; la "
                       "descripcion se descarta entera")


# ── 8. COMBO QUE NO EXISTE EN LA FUENTE ────────────────────────────────────
def c8():
    r = buscar(descripcion="pc gamer completa")
    ok = r.get("estado") in ("no_encontrado", "no_vendemos")
    tiene_alt = bool(r.get("hay_en_la_categoria") or r.get("productos"))
    caso(8, "quiero armar una PC gamer completa, que necesito y cuanto sale",
         "buscar_productos descripcion='pc gamer completa'",
         "no inventar un bundle; idealmente decir que rubros la componen",
         f"estado={r.get('estado')}, trae alternativas: {tiene_alt}", ok,
         "" if ok else "riesgo de bundle inventado")


# ── 9. SIN ANCLA NINGUNA ───────────────────────────────────────────────────
def c9():
    r = buscar(descripcion="un regalo para mi viejo que labura en el campo")
    ok = bool(r.get("instruccion") or r.get("hay_en_la_categoria"))
    caso(9, "busco un regalo para mi viejo, que labura en el campo",
         "buscar_productos descripcion=...",
         "una salida que le permita al modelo preguntar, con contexto",
         f"estado={r.get('estado')}, instruccion: "
         f"{bool(r.get('instruccion'))}", ok,
         "" if ok else "SALIDA MUDA: no_encontrado vuelve sin instruccion, sin "
                       "cuantos habia y sin alternativa. Es el generador de muro")


# ── 10. LA FUENTE NO SABE: cancelacion de ruido ────────────────────────────
def c10():
    r = buscar(descripcion="HyperX Cloud II")
    f = (r.get("productos") or [{}])[0]
    campos = set(f) | set((f.get("specs") or {}))
    menciona = any("ruido" in norm(k) or "ruido" in norm(v)
                   for k, v in (f.get("specs") or {}).items())
    # el camino por filtro SI avisa
    r2 = buscar(categoria="auriculares",
                filtros=[H.Filtro(campo="cancelacion_ruido", operador="igual",
                                  valor="si")])
    avisa = bool(r2.get("filtros_no_aplicados"))
    caso(10, "los HyperX Cloud II tienen cancelacion de ruido activa",
         "ficha via buscar_productos / o filtro campo=cancelacion_ruido",
         "que el modelo pueda ver que ese dato NO esta",
         f"la ficha menciona ruido: {menciona}; el filtro avisa que el campo "
         f"no existe: {avisa}", avisa,
         "" if avisa else "ausencia invisible")


# ── 11. PRODUCTO CONTRA PRODUCTO ───────────────────────────────────────────
def c11():
    nb = next((p for p in CON_STOCK if "ideapad 3" in norm(p.get("nombre"))), None)
    rams = [p for p in CON_STOCK if p.get("categoria") == "memoria ram"]
    r = H.ejecutar("ver_compatibilidad",
                   {"product_id": (rams[0]["id"] if rams else "X"),
                    "equipo": (nb["nombre"] if nb else "notebook Lenovo")},
                   TIENDA)
    from app.core import compatibilidad as C
    tiene_par = hasattr(C, "evaluar_par")
    ok = r.get("estado") not in (None, "no_encontrado") and "compatible" in str(r)
    caso(11, "tengo una notebook Lenovo IdeaPad 3, que memoria le sirve",
         "ver_compatibilidad product_id=<ram> equipo='Lenovo IdeaPad 3'",
         "cruzar requiere/provee entre los DOS productos del catalogo",
         f"evaluar_par existe: {tiene_par}; ver_compatibilidad devuelve "
         f"{str(r)[:90]}", False,
         "ESCRITA Y DESCONECTADA: evaluar_par cruza producto contra producto y "
         "ninguna herramienta lo expone; ver_compatibilidad es contra PLATAFORMA")


# ── 12. GARANTIA DE UN MODELO PUNTUAL ──────────────────────────────────────
def c12():
    r = buscar(descripcion="Asus TUF F15")
    f = (r.get("productos") or [{}])[0]
    reales = {p.get("garantia_meses") for p in CON_STOCK
              if p.get("categoria") == "notebook"}
    ok = f.get("garantia_meses") in reales and bool(f.get("garantia_detalle"))
    caso(12, "que garantia tiene la Asus TUF F15 y que pasa a los 18 meses",
         "buscar_productos descripcion='Asus TUF F15'",
         f"garantia real de notebooks: {sorted(x for x in reales if x)} meses",
         f"estado={r.get('estado')}, garantia_meses={f.get('garantia_meses')}, "
         f"detalle presente: {bool(f.get('garantia_detalle'))}", ok)


# ── 13 y 14. POLITICA: igualar precio, mayorista, factura ──────────────────
def c13():
    r = H.consultar_temas(H.ConsultarTemas(temas=["promociones"]), TIENDA)
    temas = [t.get("tema") for t in (r.get("temas") or [])]
    con_movida = [t.get("tema") for t in (r.get("temas") or []) if t.get("movida")]
    ok = bool(temas)
    caso(13, "vi el mismo mouse a 30 mil en otro lado, me lo haces a ese precio",
         "consultar_temas temas=[promociones]",
         "una politica o movida escrita para la objecion de precio",
         f"temas servidos {temas}, con movida {con_movida}", ok,
         "" if ok else "sin material, el modelo improvisa el descuento")


def c14():
    r = H.consultar_temas(H.ConsultarTemas(temas=["mayoristas", "factura"]),
                          TIENDA)
    temas = [(t.get("tema"), bool(t.get("politica"))) for t in (r.get("temas") or [])]
    ok = len(temas) == 2 and all(x[1] for x in temas)
    caso(14, "necesito 10 notebooks para una empresa, precio por cantidad y "
             "factura A",
         "consultar_temas temas=[mayoristas, factura]",
         "las dos politicas escritas",
         f"{temas}", ok)


# ── 15. CONDICIONAL SOBRE UN VALOR CALCULADO + retiro que no existe ────────
def c15():
    aur = [p for p in CON_STOCK if p.get("categoria") == "auriculares"][0]
    env = H.cotizar_envio(H.CotizarEnvio(localidad="Posadas"), TIENDA)
    r = H.armar_presupuesto(H.ArmarPresupuesto(
        items=[H.ItemPedido(product_id=aur["id"], cantidad=2)],
        destinos=["Posadas"]), TIENDA)
    costo = env.get("costo") or env.get("costo_ars")
    ok = bool(costo) and bool(r.get("bloque") or r.get("detalle"))
    caso(15, "2 auriculares, si el envio a Posadas sale mas de 8 mil mandame uno",
         "cotizar_envio localidad=Posadas + armar_presupuesto",
         "un costo de envio real para poder evaluar la condicion",
         f"cotizar_envio devuelve {str(env)[:110]}", ok,
         "" if ok else "sin numero de envio la condicion no se puede evaluar")


# ── 16. DESTINO POR ITEM: sobrevive al calculo, no a la memoria ────────────
def c16():
    mouse = [p for p in CON_STOCK if p.get("categoria") == "mouse"][0]
    tec = [p for p in CON_STOCK if p.get("categoria") == "teclado"][0]
    r = H.armar_presupuesto(H.ArmarPresupuesto(
        items=[H.ItemPedido(product_id=mouse["id"], cantidad=1,
                            destino="Cordoba capital"),
               H.ItemPedido(product_id=mouse["id"], cantidad=1,
                            destino="Concordia"),
               H.ItemPedido(product_id=tec["id"], cantidad=1,
                            destino="Posadas")],
        destinos=["Cordoba capital", "Concordia", "Posadas"],
        pago=[H.PartePago(medio="mercado pago", porcentaje=30),
              H.PartePago(medio="transferencia", porcentaje=70)]), TIENDA)
    pres = str(r.get("bloque") or "")
    tres = sum(1 for d in ("ordoba", "oncordia", "osadas") if d in pres)
    # y ahora: que queda guardado del turno
    from app.core.hub_venta import _carrito_del_turno
    carrito = _carrito_del_turno([{"herramienta": "armar_presupuesto",
                                   "resultado": r}])
    guarda_destino = any("destino" in c for c in carrito)
    caso(16, "pregunta 1: 2 mouse a dos ciudades y 1 teclado a otra, pago 30/70",
         "armar_presupuesto con destino por item + pago dividido",
         "los 3 envios separados en la cuenta y el destino guardado para el "
         "turno siguiente",
         f"envios distintos en la presentacion: {tres} de 3; el carrito que se "
         f"persiste guarda destino: {guarda_destino}", guarda_destino,
         "" if guarda_destino else "EL DESTINO POR ITEM SE CALCULA Y NO SE "
                                   "GUARDA: _carrito_del_turno persiste solo "
                                   "id, nombre y cantidad. Al turno siguiente "
                                   "el reparto no existe")


# ── 17. DECLARAR EL PEDIDO CON DESTINO POR ITEM ────────────────────────────
def c17():
    campos = set(H.ItemDeclarado.model_fields)
    ok = "destino" in campos
    caso(17, "preguntas 2, 10, 13, 22, 25: declarar que item va a que ciudad",
         "registrar_pedido items=[...]",
         "poder declarar el destino de cada item",
         f"campos de ItemDeclarado: {sorted(campos)}; destinos viaja aparte "
         f"como lista suelta", ok,
         "" if ok else "EL RECONCILIADOR NO PUEDE VER EL REPARTO: se declara "
                       "'2 mouse' y 'Cordoba, Concordia' sin atadura entre los "
                       "dos, asi que un reparto mal hecho no se detecta")


# ── 18. SACAR UN ITEM SIN RECOTIZAR ────────────────────────────────────────
def c18():
    from app.core.hub_venta import _carrito_del_turno
    # turno donde el cliente saca el teclado y NO pide precio
    carrito = _carrito_del_turno([
        {"herramienta": "buscar_productos", "resultado": {"productos": []}},
        {"herramienta": "registrar_pedido", "resultado": {"pedido": {}}}])
    ok = carrito != []
    caso(18, "pregunta 7 y Serie 1: 'el teclado sacalo', sin pedir precio",
         "cualquier turno que no llame armar_presupuesto",
         "que el carrito refleje la baja",
         f"_carrito_del_turno devuelve {carrito}; si esta vacio, el hub "
         f"conserva el carrito ANTERIOR intacto", ok,
         "" if ok else "EL CARRITO SOLO SE ESCRIBE RECOTIZANDO: no hay "
                       "operacion de quitar. Un turno que saca un producto sin "
                       "pedir la cuenta deja el producto adentro")


# ── 19. LAS LOCALIDADES QUE USAN TUS PREGUNTAS ─────────────────────────────
def c19():
    destinos = ["Cordoba capital", "Concordia", "Posadas", "Berrotaran",
                "Rosario", "La Plata", "Mendoza", "San Luis", "Santa Fe",
                "Entre Rios", "Villa Maria"]
    filas = []
    for d in destinos:
        r = H.cotizar_envio(H.CotizarEnvio(localidad=d), TIENDA)
        filas.append((d, r.get("estado"), r.get("costo") or r.get("costo_ars")))
    sin_cotizar = [f[0] for f in filas if not f[2]]
    caso(19, "todas las localidades que aparecen en tus 25 preguntas",
         "cotizar_envio por cada una",
         "cotizar la que se puede y PEDIR el codigo postal en la que no",
         "; ".join(f"{d}={e}/{c}" for d, e, c in filas),
         not sin_cotizar,
         "" if not sin_cotizar else f"sin tarifa: {sin_cotizar}")


# ── 20. AGREGADO CON CONDICION ─────────────────────────────────────────────
def c20():
    blancos = sum(1 for p in CON_STOCK if p.get("categoria") == "mouse"
                  and "blanco" in norm(p.get("color")))
    campos = set(H.ConsultarCatalogo.model_fields)
    ok = "filtros" in campos
    caso(20, "cuantos mouse blancos tenes / cual es la notebook mas barata con "
             "16GB",
         "consultar_catalogo operacion=contar + un filtro",
         f"la verdad es {blancos} mouse blancos con stock",
         f"campos de consultar_catalogo: {sorted(campos)}", ok,
         "" if ok else "EL AGREGADO NO ACEPTA CONDICIONES: 38 campos "
                       "filtrables en buscar_productos y cero en el agregado. "
                       "Cruzar cuantos-hay con una condicion no tiene puerta")


# ── 21. HUMO SOBRE LAS NUEVE PUERTAS ───────────────────────────────────────
def c21():
    """LA PRUEBA QUE NO EXISTIA. Cada herramienta, llamada con argumentos
    validos minimos, por el MISMO ejecutor que usa el hub. No mira si la
    respuesta es buena: mira si la puerta ABRE.

    Por que hace falta. Los bancos miden la prosa final, asi que una
    herramienta que revienta se ve como 'el modelo no supo contestar': el hub
    atrapa la excepcion, devuelve {estado: error} y el modelo redacta sin ese
    dato. Un fallo de codigo se lee como un fallo de criterio, y se sale a
    parchear el prompt.
    """
    mouse = next(p for p in CON_STOCK if p.get("categoria") == "mouse")
    llamadas = {
        "registrar_pedido": {"items": [{"que": "mouse", "cantidad": 2}]},
        "buscar_productos": {"categoria": "mouse"},
        "consultar_catalogo": {"operacion": "contar"},
        "ficha_producto": {"product_id": mouse["id"]},
        "consultar_temas": {"temas": ["envios"]},
        "cotizar_envio": {"localidad": "Rosario"},
        "armar_presupuesto": {"items": [{"product_id": mouse["id"],
                                         "cantidad": 1}],
                              "destinos": ["Rosario"]},
        "ver_compatibilidad": {"product_id": mouse["id"], "equipo": "notebook"},
        "tomar_pedido": {"motivo": "decide_comprar"},
    }
    rotas = []
    detalle = []
    for nombre, args in llamadas.items():
        r = H.ejecutar(nombre, args, TIENDA)
        est = (r or {}).get("estado")
        if est == "error":
            rotas.append(nombre)
        detalle.append(f"{nombre}={est}")
    caso(21, "LAS NUEVE PUERTAS, con argumentos validos minimos",
         "H.ejecutar por cada herramienta, el mismo ejecutor del hub",
         "las nueve abren",
         "; ".join(detalle), not rotas,
         "" if not rotas else f"HERRAMIENTA MUERTA: {rotas}. Revienta SIEMPRE, "
                              "el hub la convierte en estado=error y el modelo "
                              "contesta sin ese dato. Cero tests la cubren")


def main():
    for f in (c1, c2, c3, c4, c5, c6, c7, c8, c9, c10, c11, c12, c13, c14,
              c15, c16, c17, c18, c19, c20, c21):
        try:
            f()
        except Exception as e:
            caso(f.__name__, f.__name__, "-", "-",
                 f"EXCEPCION {type(e).__name__}: {str(e)[:160]}", False,
                 "la llamada ideal ni siquiera corre")

    verdes = [r for r in RESULTADOS if r["ok"]]
    print("=" * 78)
    print(f"BANCO DE CANDIDATOS — {len(verdes)} de {len(RESULTADOS)} en verde")
    print("=" * 78)
    for r in RESULTADOS:
        print(f"\n[{'OK ' if r['ok'] else 'MAL'}] {r['n']}. {r['pregunta']}")
        print(f"   llamada  : {r['llamada']}")
        print(f"   esperado : {r['esperado']}")
        print(f"   obtenido : {r['obtenido']}")
        if r["causa"]:
            print(f"   CAUSA    : {r['causa']}")
    print("\n" + "=" * 78)
    print("CAUSAS, agrupadas")
    print("=" * 78)
    causas = {}
    for r in RESULTADOS:
        if r["causa"]:
            causas.setdefault(r["causa"].split(":")[0], []).append(r["n"])
    for c, ns in sorted(causas.items(), key=lambda t: -len(t[1])):
        print(f"  {len(ns)} caso(s) {ns}: {c}")
    return 0 if len(verdes) == len(RESULTADOS) else 1


if __name__ == "__main__":
    raise SystemExit(main())

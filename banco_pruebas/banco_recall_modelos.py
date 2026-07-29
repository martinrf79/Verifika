"""
BANCO DE RECALL — el numero de la etapa 1 del interprete.

QUE MIDE. De cada mensaje, si el modelo correcto del catalogo entra en la lista
de candidatos que va al enum de `producto_resuelto`. Lo que no entra ahi, el
interprete NO lo puede nombrar aunque lo haya entendido perfecto. Por eso este
es el techo de toda la interpretacion: ninguna mejora de prompt puede recuperar
un producto que nunca estuvo en la lista.

COMO ARMA LOS CASOS. Dos tandas, las dos sobre el catalogo REAL de 880:

  1. ESCRITOS. Las formas reales que fallaron en produccion (charla del 28-jul)
     mas parafrasis del castellano de todos los dias. Cada falla nueva se suma
     aca y no se saca.
  2. DERIVADOS DEL CATALOGO, uno por modelo, generados de la propia ficha. Es
     lo que hace que el numero valga para los 482 modelos y no para los diez
     que a uno se le ocurrieron. Cuatro maneras de nombrar el mismo producto:
       - nombre sin la marca      "Kumara K552 RGB"
       - marca mas un token       "redragon k552"
       - typo en el modelo        "kumara k55z"
       - por los tags propios     los tags RAROS del producto, los que casi
                                  ningun otro modelo comparte. Es el caso que
                                  el recall viejo no podia ver, porque miraba
                                  solo la etiqueta "Marca Modelo".

COMPARA VIEJO CONTRA NUEVO. Corre las dos versiones sobre los mismos casos: el
recall por etiqueta (lo que habia hasta hoy) y el recall por ficha con peso e
idf (lo que hay ahora). Si el numero no sube, el cambio no sirvio y se vuelve
atras: eso es lo que este banco esta para decir.

Offline: sin LLM, sin credenciales, sin red. Corre en segundos.

Uso:  python3 banco_pruebas/banco_recall_modelos.py
Sale != 0 si el recall@30 de la version nueva queda bajo el PISO.
"""
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from banco_pruebas.sim_firestore import install

PISO = 0.95
TOPE = 30


def _norm(s):
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c)).strip()


# ── Casos ESCRITOS: mensaje -> como lo nombraria el catalogo ────────────────
# El esperado es un fragmento de la etiqueta "Marca Modelo"; se da por bueno si
# algun candidato lo contiene. Asi el caso no se rompe si cambia el sufijo.
ESCRITOS = [
    # charla real 28-jul: la etiqueta es "Asus TUF Gaming F15", el cliente
    # escribio menos palabras y el recall viejo igual lo encontraba.
    ("la asus tuf f15 tiene thunderbolt?", "asus tuf"),
    ("cuanto sale la zenbok 14", "asus zenbook"),          # typo
    ("tenes la zenbook 14?", "asus zenbook"),
    # los que el recall VIEJO no podia: cero palabras en comun con la etiqueta
    ("me interesa el teclado mecanico rgb", "redragon"),
    ("busco un mouse optico barato", "logitech"),
    ("tenes algun mause inalambrico?", "logitech"),
    # letras sueltas del nombre real: el tokenizador viejo las borraba enteras
    ("tenes los auriculares g pro x negro?", "logitech g pro x"),
]

# NOTA sobre lo que este banco NO mide, a proposito: un mensaje que nombra SOLO
# una categoria ("queria un raton para la compu") no tiene modelo correcto, y
# exigirle uno seria premiar que el recall adivine. Ese caso lo resuelve el
# universo por categoria en generador_v2, no el enum del interprete.


def _recall_viejo(mensaje, modelos, tope):
    """El recall tal cual estaba hasta hoy: palabras del mensaje contra la
    etiqueta 'Marca Modelo', con su tokenizador y su pase de typo. Se reproduce
    aca entero para que la comparacion sea honesta y no dependa del modulo
    nuevo."""
    from difflib import get_close_matches
    from app.core.pedido_helpers import _tokens_producto
    toks = _tokens_producto(mensaje)
    if not toks:
        return []
    porton = {}
    for m in modelos:
        comunes = toks & _tokens_producto(m)
        if comunes:
            porton[m] = len(comunes)
    if len(porton) < tope:
        vocab = {t for m in modelos for t in _tokens_producto(m)}
        for t in toks:
            if t in vocab or len(t) < 4:
                continue
            for parecida in get_close_matches(t, vocab, n=2, cutoff=0.8):
                for m in modelos:
                    if parecida in _tokens_producto(m):
                        porton.setdefault(m, 0.5)
    return [m for m, _s in sorted(porton.items(), key=lambda x: -x[1])][:tope]


def _derivados(productos, por_etiqueta):
    """Un caso por MODELO, generado de su propia ficha. Devuelve
    [(mensaje, etiqueta_esperada, tipo)]."""
    from app.core.recall_modelos import etiqueta_modelo
    # frecuencia de cada tag en el catalogo: los tags RAROS son los que
    # identifican; "mouse" o "gaming" lo tiene medio catalogo y no sirve.
    df = {}
    for p in productos:
        for t in {x.strip() for x in _norm(p.get("tags")).split(",") if x.strip()}:
            df[t] = df.get(t, 0) + 1

    casos, vistas = [], set()
    for p in productos:
        et = etiqueta_modelo(p)
        if not et or et.lower() in vistas:
            continue
        vistas.add(et.lower())
        marca = _norm(p.get("marca"))
        modelo = _norm(p.get("modelo"))
        nombre = _norm(p.get("nombre"))
        if not modelo:
            continue

        # 1) el nombre completo SIN la marca
        sin_marca = " ".join(w for w in nombre.split() if w != marca)
        if sin_marca and sin_marca != nombre:
            casos.append((f"tenes {sin_marca}?", et, "nombre_sin_marca"))

        # 2) marca mas UN token del modelo
        toks_mod = [t for t in modelo.split() if len(t) > 2]
        if marca and toks_mod:
            casos.append((f"quiero el {marca} {toks_mod[-1]}", et, "marca_mas_token"))

        # 3) typo: se le cambia una letra al token mas largo del modelo
        largo = max(toks_mod, key=len) if toks_mod else ""
        if len(largo) >= 5:
            i = len(largo) // 2
            typo = largo[:i] + ("z" if largo[i] != "z" else "x") + largo[i + 1:]
            casos.append((f"cuanto sale la {marca} {typo}", et, "typo"))

        # 4) por los tags PROPIOS: los tres menos frecuentes del producto, sin
        # los que ya son la marca o el modelo (esos no prueban nada).
        propios = {x.strip() for x in _norm(p.get("tags")).split(",") if x.strip()}
        propios = [t for t in propios
                   if t not in marca and t not in modelo and df.get(t, 0) <= 40]
        propios.sort(key=lambda t: df.get(t, 0))
        if len(propios) >= 2:
            casos.append((f"busco {' '.join(propios[:3])}", et, "tags_propios"))
    return casos


def _rango(candidatos, esperado):
    """En que POSICION quedo el correcto, 1 es el primero. None si no esta.

    El recall@30 solo no alcanza para decir que esto anda: traer el correcto en
    el puesto 28 de 30 igual le deja al interprete una lista larga de parecidos
    donde equivocarse, y son mas tokens por turno. Lo que importa es que el
    correcto quede ARRIBA y que la lista sea corta."""
    esp = _norm(esperado)
    for i, c in enumerate(candidatos, 1):
        if esp in _norm(c):
            return i
    return None


def main():
    install()
    from app.storage.firestore_client import get_all_products
    from app.core.interpretador import modelos_del_catalogo
    from app.core import recall_modelos

    productos = get_all_products(tienda_id="verifika_prod")
    modelos = modelos_del_catalogo("verifika_prod")
    por_etiqueta = {m.lower(): m for m in modelos}
    print(f"catalogo: {len(productos)} productos, {len(modelos)} modelos\n")

    idx = recall_modelos.indice("verifika_prod")
    if not idx:
        print("SIN INDICE: el doble de Firestore no cargo. Abortando.")
        return 2

    casos = [(m, e, "escrito") for m, e in ESCRITOS]
    casos += _derivados(productos, por_etiqueta)

    m = {}   # tipo -> acumuladores
    fallas = []
    for mensaje, esperado, tipo in casos:
        nuevos = recall_modelos.candidatos(mensaje, modelos, tope=TOPE,
                                           tienda_id="verifika_prod")
        viejos = _recall_viejo(mensaje, modelos, TOPE)
        a = m.setdefault(tipo, {"n": 0, "v30": 0, "n30": 0, "v1": 0, "n1": 0,
                                "v5": 0, "n5": 0, "largo": 0})
        a["n"] += 1
        a["largo"] += len(nuevos)
        rn, rv = _rango(nuevos, esperado), _rango(viejos, esperado)
        for clave, r in (("n", rn), ("v", rv)):
            if r:
                a[clave + "30"] += 1
                if r <= 5:
                    a[clave + "5"] += 1
                if r == 1:
                    a[clave + "1"] += 1
        if not rn and len(fallas) < 20:
            fallas.append((tipo, mensaje, esperado, nuevos[:4]))

    def _fila(nombre, a):
        n = a["n"]
        print(f"{nombre:<18} {n:>5} "
              f"{a['v30'] / n:>7.1%} {a['n30'] / n:>7.1%} | "
              f"{a['v5'] / n:>7.1%} {a['n5'] / n:>7.1%} | "
              f"{a['n1'] / n:>7.1%} {a['largo'] / n:>6.1f}")

    print(f"{'':<18} {'':>5} {'--- recall@30 ---':^15} | "
          f"{'--- recall@5 ---':^15} | {'NUEVO':>7} {'lista':>6}")
    print(f"{'tipo':<18} {'casos':>5} {'viejo':>7} {'nuevo':>7} | "
          f"{'viejo':>7} {'nuevo':>7} | {'top-1':>7} {'largo':>6}")
    print("-" * 74)
    for tipo in sorted(m):
        _fila(tipo, m[tipo])
    tot = {k: sum(a[k] for a in m.values()) for k in next(iter(m.values()))}
    print("-" * 74)
    _fila("TOTAL", tot)

    if fallas:
        print(f"\nFALLAS del recall nuevo (primeras {len(fallas)}):")
        for tipo, mensaje, esperado, muestra in fallas:
            print(f"  [{tipo}] {mensaje!r}")
            print(f"      esperaba: {esperado} | trajo: {muestra}")

    r30 = tot["n30"] / tot["n"]
    r5 = tot["n5"] / tot["n"]
    print()
    if r30 < PISO:
        print(f"BAJO EL PISO: recall@30 {r30:.1%} < {PISO:.0%}")
        return 1
    print(f"OK: recall@30 = {r30:.1%} | recall@5 = {r5:.1%} | "
          f"lista promedio {tot['largo'] / tot['n']:.1f} de {len(modelos)} "
          f"modelos (piso {PISO:.0%})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

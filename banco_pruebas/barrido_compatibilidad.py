"""
EL BARRIDO DE LA COMPATIBILIDAD — la fuente mas grande que nadie pasaba por el
camino que la responde.

POR QUE EXISTE (Martin, 13-ago-2026): "hay respuestas juradas de compatibilidad
que me imagino que, al ser muy importantes, tambien tienen que estar dentro de
estos barridos".

Tenia razon y el numero lo confirmaba: `compatibilidad.csv` tiene 482 filas con
dato cargado, y lo unico que las tocaba era el barrido de COHERENCIA, que
verifica que el dato no se contradiga con las specs y este en el vocabulario.
Eso mira el DATO. Lo que NUNCA se barrio es la RESPUESTA: pasar los pares por
`evaluar_par`, que es la funcion que contesta "¿esto le sirve a mi equipo?".
Solo la tocaban unos pocos casos escritos a mano.

Y contestar mal ahi no es una respuesta fea: es una devolucion. El cliente
compra una memoria que no le entra en la notebook.

QUE GENERA. Los pares que la fuente hace posibles, por familia de conexion —
socket, generacion de memoria, conector, plataforma— mas los pares que NO
comparten ninguna familia, que son los que tienen que dar `sin_dato` y no un
"si" de compromiso. No se escribe un solo par a mano: salen del cruce de la
tabla real.

LAS PROPIEDADES SON DE NEGOCIO, NO DE IMPLEMENTACION, que es lo unico que hace
que un barrido encuentre lo que el codigo no vio:
  - el veredicto es simetrico: si A va con B, B va con A;
  - un "no compatible" explicito manda sobre cualquier cruce de familias;
  - nunca se afirma compatible sin evidencia en la fuente;
  - la funcion nunca levanta, con cualquier producto.

CORRE OFFLINE Y GRATIS.
"""
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

TIENDA = "verifika_prod"

VEREDICTOS = ("compatible", "incompatible", "sin_dato")


def filas_con_compat(tienda_id: str = TIENDA) -> list:
    """Los productos del catalogo que tienen alguna arista de compatibilidad
    cargada. Son el universo del barrido y salen de la fuente."""
    from app.core.compatibilidad import compat_de
    from app.storage.firestore_client import get_all_products
    fuera = []
    for p in (get_all_products(tienda_id=tienda_id) or []):
        c = compat_de(p, tienda_id)
        if c:
            fuera.append((p, c))
    return fuera


def familias(tienda_id: str = TIENDA) -> list:
    """Las familias de conexion que declara el vocabulario de la fuente: socket,
    generacion de memoria, conector, plataforma. Son las que `evaluar_par`
    cruza."""
    from app.core.compatibilidad import vocabulario
    v = vocabulario(tienda_id) or {}
    fam = v.get("familias") or {}
    return sorted(fam) if isinstance(fam, dict) else sorted(fam)


def _aristas(compat: dict) -> dict:
    """Lo que un producto REQUIERE y lo que PROVEE, como conjuntos de familias.

    En la fuente la familia ES el valor: `requiere: ["puerto_usb_a"]`. Se lee
    solo para ELEGIR pares interesantes, nunca para juzgar el veredicto: eso lo
    decide `evaluar_par`, y si el barrido lo re-implementara estaria comparando
    el codigo contra una copia suya."""
    return {
        "requiere": {str(x).strip().lower()
                     for x in (compat.get("requiere") or []) if str(x).strip()},
        "provee": {str(x).strip().lower()
                   for x in (compat.get("provee") or []) if str(x).strip()},
        "no": {str(x).strip().lower()
               for x in (compat.get("no_compatible") or []) if str(x).strip()},
        "plataformas": {str(x).strip().lower()
                        for x in (compat.get("plataformas") or [])
                        if str(x).strip()},
    }


def pares(tienda_id: str = TIENDA, tope_por_clase: int = 60) -> list:
    """Los pares a barrer: {a, b, clase}.

    TRES CLASES, y las tres hacen falta:
      cruzan    los dos declaran la misma familia -> el veredicto tiene que ser
                compatible o incompatible, nunca sin_dato
      ajenos    ninguna familia en comun -> tiene que ser sin_dato, y no un "si"
                de compromiso, que es la forma en que este eje miente
      mismo     un producto contra si mismo, que es el borde
      negados   uno declara al otro NO compatible -> el no explicito tiene que
                mandar sobre cualquier cruce de familias
    """
    universo = filas_con_compat(tienda_id)
    por_prod = [(p, _aristas(c)) for p, c in universo]
    cruzan, ajenos, mismo, negados = [], [], [], []
    for i, (pa, va) in enumerate(por_prod):
        if len(mismo) < tope_por_clase:
            mismo.append({"a": pa, "b": pa, "clase": "mismo"})
        for pb, vb in por_prod[i + 1:]:
            cruce = (va["requiere"] & vb["provee"]) | (vb["requiere"] & va["provee"])
            # NEGADO es que uno declare NO COMPATIBLE lo que el otro ES, no lo
            # que el otro soporta. La primera version cruzaba `no_compatible`
            # contra las plataformas que el otro ADMITE, y marcaba como negado
            # un mouse contra una placa de video: la placa dice que no anda en
            # notebook y el mouse dice que si anda en notebook, y eso no los
            # enfrenta entre si. Daba 60 falsos negados, y `sin_dato` era el
            # veredicto correcto. Un generador laxo inventa defectos que no
            # existen, que es tan caro como no encontrar los que si.
            niega = (va["no"] & {str(pb.get("categoria") or "").lower()}) \
                or (vb["no"] & {str(pa.get("categoria") or "").lower()})
            if niega and len(negados) < tope_por_clase:
                negados.append({"a": pa, "b": pb, "clase": "negados"})
            elif cruce and len(cruzan) < tope_por_clase:
                cruzan.append({"a": pa, "b": pb, "clase": "cruzan",
                               "familias": sorted(cruce)})
            elif not cruce and not niega and len(ajenos) < tope_por_clase:
                ajenos.append({"a": pa, "b": pb, "clase": "ajenos"})
            if all(len(x) >= tope_por_clase for x in (cruzan, ajenos, negados)):
                break
        if all(len(x) >= tope_por_clase
               for x in (cruzan, ajenos, mismo, negados)):
            break
    return cruzan + ajenos + mismo + negados


def contra_plataforma(tienda_id: str = TIENDA, tope: int = 80) -> list:
    """El otro eje, y es el que el cliente usa mas: producto contra PLATAFORMA
    generica —"¿sirve para la Play 5?", "¿anda con Mac?"—. Cada producto con
    compatibilidad cargada, contra cada plataforma del vocabulario."""
    from app.core.compatibilidad import vocabulario
    v = vocabulario(tienda_id) or {}
    plats = sorted((v.get("plataformas") or {}))
    universo = filas_con_compat(tienda_id)
    fuera = []
    for p, _c in universo:
        for pl in plats:
            fuera.append({"producto": p, "plataforma": pl})
            if len(fuera) >= tope:
                return fuera
    return fuera


def cobertura(tienda_id: str = TIENDA) -> dict:
    """Cuanto de la fuente de compatibilidad toca el barrido. El denominador
    sale de la fuente: los productos con arista cargada y las plataformas del
    vocabulario."""
    from app.core.compatibilidad import vocabulario
    universo = filas_con_compat(tienda_id)
    v = vocabulario(tienda_id) or {}
    plats = sorted((v.get("plataformas") or {}))
    ps = pares(tienda_id)
    cp = contra_plataforma(tienda_id)
    tocados = {id(x["a"]) for x in ps} | {id(x["b"]) for x in ps} \
        | {id(x["producto"]) for x in cp}
    plats_tocadas = {x["plataforma"] for x in cp}
    return {
        "productos_con_compat": len(universo),
        "plataformas": len(plats),
        "familias": len(familias(tienda_id)),
        "pares": len(ps), "contra_plataforma": len(cp),
        "plataformas_cubiertas": len(plats_tocadas),
        "clases": sorted({x["clase"] for x in ps}),
    }

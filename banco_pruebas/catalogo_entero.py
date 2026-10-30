"""EL CATALOGO ENTERO EN CONTEXTO — el techo del modelo cuando ve toda la tienda (30-oct-2026, FICHA 83).

Pregunta de Martin del 30-oct: los errores se repiten, ¿son del modelo o de lo que le acercamos? En el buscador, K04
fallo porque la fila cortada dejo el peso afuera, y K19 y C41 contestaron sin buscar. Aca el modelo tiene el catalogo
entero, una linea por modelo, ordenado por precio dentro de cada rubro, en cada turno, mas las mismas herramientas y el
mismo verificador del buscador. Si con todo a la vista igual falla, el error es de la consigna o del modelo; si acierta,
es de lo que le acerca el buscador.

No es para el bot: pesa unos 39.500 tokens por llamada, unas veinte veces lo del buscador, y no escala a una tienda
grande. Mide el techo, para saber cuanto le falta al buscador.

    python3 banco_pruebas/catalogo_entero.py --llamar [--hasta 10] [C27 K20 ...]    con la gratis
    python3 banco_pruebas/catalogo_entero.py [--ver]                               sin modelo, lo grabado
    ... --charlas [--llamar] [--ver]                                                las charlas enteras
"""
import collections
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import buscador_agente as B  # noqa: E402


def catalogo() -> str:
    """Toda la tienda, por rubro y de menor a mayor precio, una linea por modelo con sus colores con stock y su ficha."""
    from app.core.flujo import catalogo as K
    from app.core.flujo import interprete
    todos = K.productos(B.TID)
    modelos = collections.OrderedDict()
    for p in sorted(todos, key=lambda x: (str(x.get("categoria")), not K.con_stock(x), K.entero(x.get("precio_ars")))):
        modelos.setdefault((p.get("categoria"), p.get("marca"), p.get("modelo")), []).append(p)
    rubros = collections.OrderedDict()
    for (rubro, _, _), ps in modelos.items():
        rubros.setdefault(rubro, []).append(ps)
    for fam in rubros.values():
        fam.sort(key=lambda ps: K.entero(ps[0].get("precio_ars")))

    def linea(ps: list) -> str:
        # LAS VARIANTES QUE DIFIEREN: la fuente trae el peso o el precio distinto por color —el G Pro Wireless pesa
        # 99 g en negro y 70 g en blanco—, y una linea por modelo sola los esconde.
        base = interprete.datos(ps[0], todos)
        propios = set(base.split("; ")[2:])
        otras = []
        for v in ps[1:]:
            precio = K.entero(v.get("precio_ars")) != K.entero(ps[0].get("precio_ars"))
            difiere = [x for x in interprete.datos(v, todos).split("; ")[2:] if x not in propios]
            if difiere or precio:
                otras.append(f"{v.get('color')}" + (f" ${K.entero(v.get('precio_ars')):,}".replace(",", ".")
                                                   if precio else "") + (", " + ", ".join(difiere) if difiere else ""))
        return base + (" | otra variante: " + " | ".join(otras) if otras else "")
    return "EL CATALOGO ENTERO DE LA TIENDA, por rubro y de menor a mayor precio, una linea por modelo:\n" + "\n".join(
        f"{str(r).upper()}:\n  " + "\n  ".join(linea(ps) for ps in fam) for r, fam in rubros.items())


B.CONSIGNA += """

Tenes el catalogo entero de la tienda en el mensaje: podes elegir productos de ahi sin buscarlos. El buscador sigue
sirviendo para las reglas de la tienda y el envio a un lugar."""
B.GRABADO = os.path.join(AQUI, "catalogo_entero.jsonl")
B.CHARLAS = os.path.join(AQUI, "catalogo_entero_charlas.jsonl")

if __name__ == "__main__":
    B.HM.C58.instalar()
    B.EXTRA = catalogo()
    B.charlas() if "--charlas" in B.ARGS else B.main()

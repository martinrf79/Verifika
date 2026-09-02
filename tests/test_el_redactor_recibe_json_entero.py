"""LO QUE EL REDACTOR RECIBE ES JSON, Y ES JSON ENTERO.

`contexto_json` arma lo UNICO que la llamada dos ve del mundo real. Hasta hoy
terminaba en `json.dumps(...)[:14000]`: un rebanado por CARACTER.

Medido el 2-sep-2026 con el catalogo real de `verifika_prod`:

    1 herramienta    3.620 caracteres   entra entero
    2 herramientas   7.328              entra entero
    3 herramientas  11.643              entra entero
    4 herramientas  11.787              entra entero
    5 herramientas  17.061 ->  14.000   CORTADO A MITAD DE PALABRA

Con cinco herramientas el modelo recibia `... por defectos de fabricacion,` y
ahi se terminaba el archivo: JSON invalido, una llave sin cerrar, y un producto
entero desaparecido sin que nada lo dijera. Cinco herramientas es exactamente lo
que dispara una pregunta de dificultad media-alta, que es la que nunca contesto
bien. La conclusion de esos dias fue que el modelo chico no daba; el modelo
recibia un archivo partido al medio.

Lo que esta vara fija, y vale para cualquier carga:

  1. Lo que sale es JSON valido. Siempre.
  2. Ninguna herramienta desaparece del payload.
  3. Si hubo que recortar, el payload lo DICE, en un campo que el modelo lee.
     Un dato que falta y se declara termina en una pregunta al cliente; un dato
     que falta en silencio termina en una invencion. Es la prioridad uno.

Cada test dice sobre cuantos casos corrio (regla 10.6 de CLAUDE.md).
"""
import json

import pytest

from app.core import herramientas as H

TIENDA = "verifika_prod"

# Las cinco categorias de la medicion del 2-sep. Son las que rompian el corte.
CATEGORIAS = ["mouse", "teclado", "monitor", "auricular", "notebook"]


def _llamadas_reales(cats, firestore_doble):
    llamadas = []
    for c in cats:
        llamadas.append({"herramienta": "consultar_productos",
                         "pedido": {"categoria": c},
                         "resultado": H.ejecutar("consultar_productos",
                                                 {"categoria": c}, TIENDA)})
    return llamadas


def test_el_json_que_ve_el_redactor_siempre_parsea(firestore_doble):
    """De una a cinco herramientas del catalogo real, y el sintetico enorme."""
    casos = 0
    for n in range(1, len(CATEGORIAS) + 1):
        ctx = H.contexto_json(_llamadas_reales(CATEGORIAS[:n], firestore_doble))
        json.loads(ctx)          # revienta si el corte partio una cadena
        assert len(ctx) <= 14000, f"{n} herramientas: {len(ctx)} caracteres"
        casos += 1
    assert casos == 5, f"corrio sobre {casos} casos, esperaba 5"


def test_ninguna_herramienta_desaparece_del_payload(firestore_doble):
    """El corte por caracter se comia la ultima herramienta entera. Cada
    herramienta que se ejecuto tiene que estar nombrada en lo que el modelo ve,
    aunque su lista venga recortada: si no esta, el modelo no sabe que se
    consulto y contesta como si no existiera."""
    llamadas = _llamadas_reales(CATEGORIAS, firestore_doble)
    datos = json.loads(H.contexto_json(llamadas))
    assert len(datos) == len(llamadas), \
        f"entraron {len(llamadas)} herramientas, llegaron {len(datos)}"
    for pedida, llegada in zip(llamadas, datos):
        assert llegada["pedido"] == pedida["pedido"]
        assert llegada["resultado"].get("estado") == \
            pedida["resultado"].get("estado")
    assert len(llamadas) == 5, f"corrio sobre {len(llamadas)} herramientas"


def test_lo_recortado_se_declara_y_no_se_pierde_en_silencio(firestore_doble):
    """La regla de oro del proyecto aplicada al payload: lo que no esta, se
    dice. El modelo tiene que poder leer que la lista vino incompleta."""
    llamadas = _llamadas_reales(CATEGORIAS, firestore_doble)
    crudo = json.dumps(llamadas, ensure_ascii=False, default=str)
    assert len(crudo) > 14000, \
        f"el caso ya no desborda ({len(crudo)}), la vara mide otra cosa"

    datos = json.loads(H.contexto_json(llamadas))
    recortados = [r for r in datos if r["resultado"].get("recortado")]
    assert recortados, "se recorto y ningun resultado lo declara"
    for r in recortados:
        marca = r["resultado"]["recortado"]
        assert marca["campo"], "la marca no dice que lista se recorto"
        assert marca["de"] > marca["mostrados"] >= 0, \
            f"la marca no cierra: {marca}"


def test_lo_que_entra_entero_no_se_toca(firestore_doble):
    """Un payload que entra en el tope sale byte por byte igual. El arreglo no
    puede cambiar lo que el modelo ya venia recibiendo bien: los turnos de una
    a cuatro herramientas tienen que seguir midiendo lo mismo."""
    casos = 0
    for n in range(1, 5):
        llamadas = _llamadas_reales(CATEGORIAS[:n], firestore_doble)
        crudo = json.dumps(llamadas, ensure_ascii=False, default=str)
        assert len(crudo) <= 14000, f"{n} herramientas ya desborda"
        assert H.contexto_json(llamadas) == crudo, \
            f"{n} herramientas: el payload cambio sin necesidad"
        casos += 1
    assert casos == 4, f"corrio sobre {casos} casos, esperaba 4"


@pytest.mark.parametrize("cuantos", [10, 40])
def test_un_desborde_bestial_tampoco_rompe_el_json(cuantos):
    """Sin catalogo: cuarenta herramientas con listas largas. El peor caso
    posible tiene que salir igual como JSON valido y con las cuarenta
    nombradas."""
    llamadas = [{"herramienta": f"consultar_productos_{i}",
                 "pedido": {"categoria": f"cat{i}"},
                 "resultado": {"estado": "encontrado", "hay_en_total": 200,
                               "productos": [{"id": f"X{i}{j:04d}",
                                              "nombre": "n" * 300}
                                             for j in range(30)]}}
                for i in range(cuantos)]
    ctx = H.contexto_json(llamadas)
    datos = json.loads(ctx)
    assert len(ctx) <= 14000
    assert len(datos) == cuantos, \
        f"entraron {cuantos} herramientas, llegaron {len(datos)}"


def test_una_herramienta_sola_gigante_se_recorta_pero_contesta():
    """Una sola herramienta que por si sola desborda. No puede quedar en nada:
    tiene que llegar con algunos items y la marca de lo que falta."""
    llamadas = [{"herramienta": "consultar_productos",
                 "pedido": {"categoria": "todo"},
                 "resultado": {"estado": "encontrado", "hay_en_total": 880,
                               "productos": [{"id": f"P{j:04d}",
                                              "nombre": "z" * 400}
                                             for j in range(100)]}}]
    datos = json.loads(H.contexto_json(llamadas))
    prods = datos[0]["resultado"]["productos"]
    assert prods, "se recorto hasta dejar la herramienta sin un solo producto"
    marca = datos[0]["resultado"]["recortado"]
    assert marca["mostrados"] == len(prods) and marca["de"] == 100


def test_el_contexto_va_por_herramienta_y_no_se_pisa():
    """La propiedad vieja sigue valiendo: un dict plano pisaria las claves
    entre herramientas y el no_encontrado de una taparia el resultado de la
    otra."""
    ctx = H.contexto_json([
        {"herramienta": "buscar_productos", "pedido": {}, "resultado":
            {"estado": "no_encontrado"}},
        {"herramienta": "consultar_temas", "pedido": {}, "resultado":
            {"estado": "encontrado", "politica": "Envio gratis"}}])
    assert "no_encontrado" in ctx and "Envio gratis" in ctx
    json.loads(ctx)

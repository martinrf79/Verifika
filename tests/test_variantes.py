"""LA VARA DE LAS VARIANTES — un cambio de la consigna entra medido con el modelo real (20-oct-2026, pieza 3 del plan).

La bateria no llama al modelo. Lo que controla es que la consigna que va a produccion tenga su corrida de
`banco_pruebas/variantes.py` anotada, y que en cada familia salgan bien al menos las formas del piso. Cambiar la consigna
sin correr las variantes frena el deploy: se corre `python3 -m banco_pruebas.variantes`, con la clave gratis, y se suben
las corridas con el cambio. El piso de `variantes_piso.json` solo sube.
"""
import json

from banco_pruebas import variantes as V

PISO = json.load(open("banco_pruebas/variantes_piso.json", encoding="utf-8"))


def test_la_consigna_de_hoy_esta_medida_y_no_baja_del_piso():
    from banco_pruebas import clon_produccion as C
    from app.core import llm_reintento
    puerta = llm_reintento._cliente
    C.preparar_entorno()
    C.instalar()
    try:
        huella, hechas = V._huella(), V._leidas()
    finally:
        llm_reintento._cliente = puerta
    for familia, f in V.FAMILIAS.items():
        corridas = [hechas[(huella, familia, forma)] for forma in f["formas"] if (huella, familia, forma) in hechas]
        assert len(corridas) == len(f["formas"]), (
            f"{familia}: la consigna {huella} tiene {len(corridas)} de {len(f['formas'])} formas corridas. "
            "Correr python3 -m banco_pruebas.variantes con la clave gratis y subir variantes_corridas.jsonl")
        bien = sum(f["nota"](x["respuesta"]) == "bien" for x in corridas)
        assert bien >= PISO[familia], f"{familia}: {bien} bien contra un piso de {PISO[familia]}"
        print(f"\nVARIANTES {familia}: {bien} de {len(corridas)} bien, piso {PISO[familia]}")

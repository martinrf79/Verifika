"""
CARGAR TARIFAS DE ENVIO POR PROVINCIA — dato de tienda en config/tarifas_envio.

La FAQ publica interior como RANGO ($5.000-$12.000). Esta tabla da el monto
EXACTO por provincia, escalonado por distancia desde el deposito (estilo
tarifario de correo). TODOS los montos caen dentro del rango publicado, asi
la tarifa exacta nunca contradice la politica de la FAQ.

cotizar_envio la usa con el flag TARIFA_PROVINCIA: provincia cierta -> monto
fijo; provincia incierta -> rango de siempre.

Uso:
    .\\correr_local.ps1 py scripts\\cargar_tarifas_envio.py                # dry-run
    .\\correr_local.ps1 py scripts\\cargar_tarifas_envio.py --aplicar     # escribe
    .\\correr_local.ps1 py scripts\\cargar_tarifas_envio.py otra_tienda --aplicar
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.storage.firestore_client import get_config, set_config

TIENDA = next((a for a in sys.argv[1:] if not a.startswith("-")), "verifika_prod")
APLICAR = "--aplicar" in sys.argv

# Escalones por distancia desde Buenos Aires (deposito). Dentro de 5000-12000.
TARIFAS = {
    "provincias": {
        # Cercano (hasta ~500 km)
        "buenos_aires": 6000,        # interior bonaerense
        "entre rios": 6500,
        "santa fe": 7000,
        "la pampa": 7500,
        # Medio (~500-900 km)
        "cordoba": 7500,
        "san luis": 8000,
        "corrientes": 8500,
        # Lejano (~900-1300 km)
        "mendoza": 9000,
        "san juan": 9000,
        "chaco": 9000,
        "santiago del estero": 9000,
        "neuquen": 9500,
        "la rioja": 9500,
        "tucuman": 9500,
        "catamarca": 9500,
        # Muy lejano (1300 km o mas)
        "rio negro": 10000,
        "misiones": 10000,
        "salta": 10500,
        "formosa": 10500,
        "jujuy": 11000,
        "chubut": 11000,
        "santa cruz": 11500,
        "tierra del fuego": 12000,
    },
}


def main():
    previa = get_config("tarifas_envio", tienda_id=TIENDA)
    print(f"Tienda {TIENDA}. Tabla previa: "
          f"{'SI, ' + str(len((previa or {}).get('provincias', {}))) + ' provincias' if previa else 'no hay'}")
    print(f"Tabla nueva: {len(TARIFAS['provincias'])} provincias")
    for prov, monto in sorted(TARIFAS["provincias"].items(), key=lambda x: x[1]):
        print(f"  {prov:22s} ${monto:,}".replace(",", "."))

    if not APLICAR:
        print("\nDRY-RUN: no se escribio nada. Para aplicar: --aplicar")
        return
    set_config("tarifas_envio", TARIFAS, tienda_id=TIENDA)
    print(f"\nLISTO: config/tarifas_envio cargada en {TIENDA}.")


if __name__ == "__main__":
    main()

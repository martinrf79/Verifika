"""
ENRIQUECER TECLADOS — marca el TIPO de switch de cada teclado (mecanico /
membrana / tijera / mecha-membrana), POR CODIGO y sin LLM.

Por que: el catalogo tiene los 48 teclados como "Gaming" sin distinguir el tipo
de switch. Por eso un teclado de tijera como el Logitech K380 caia en la bolsa
de "teclado mecanico" y se ofrecia como tal (visto 16-jun en la columna simple).

Que escribe (dos campos, los dos que ya consume el bot sin tocar codigo):
- `tipo`: etiqueta clara que aparece en la ficha y en los resultados de busqueda
  (_resumir devuelve todos los campos). Ej "tijera (no mecanico)".
- `descripcion`: se le AGREGA una frase discriminadora. La descripcion pesa en la
  busqueda (_texto_buscable). Clave: la palabra "mecanico" se agrega SOLO a los
  mecanicos, asi una busqueda de "teclado mecanico" rankea los mecanicos arriba y
  el K380 ni aparece en el top. Los no-mecanicos NO llevan el token "mecanico" en
  la descripcion (la aclaracion "no mecanico" va en el campo `tipo`, que no se
  busca), para no contaminar el match.

La clasificacion es por modelo REAL (dato publico y estable), no inventada.
Idempotente: la frase se agrega una sola vez; correrlo de nuevo no duplica.

Uso (PowerShell, con el venv y las env de .secrets6.env cargadas):
    python scripts/enriquecer_teclados.py                 # dry-run, no escribe
    python scripts/enriquecer_teclados.py --aplicar        # escribe en Firestore
    python scripts/enriquecer_teclados.py otra_tienda --aplicar
"""
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.storage.firestore_client import get_all_products, upsert_product

TIENDA = next((a for a in sys.argv[1:] if not a.startswith("-")), "verifika_prod")
APLICAR = "--aplicar" in sys.argv


# Clasificacion por modelo real. Clave = fragmento distintivo del nombre
# (normalizado); valor = clase de switch. Las claves son lo bastante especificas
# para no chocar entre si (ej "alloy origins core" vs "alloy core rgb").
#   mecanico       -> switches mecanicos de verdad
#   membrana       -> goma/domo, NO mecanico
#   tijera         -> scissor (slim/portatil/productividad), NO mecanico
#   mecha-membrana -> hibrido Razer, NO es mecanico puro
TIPO_POR_MODELO = {
    # Mecanicos
    "redragon kumara k552": "mecanico",
    "redragon k617 fizz": "mecanico",
    "redragon vara k551": "mecanico",
    "logitech g413 tkl se": "mecanico",
    "redragon vata k580": "mecanico",
    "hyperx alloy origins 60": "mecanico",
    "hyperx alloy origins core": "mecanico",
    "keychron v3": "mecanico",
    "razer huntsman mini": "mecanico",
    "keychron k2": "mecanico",
    "razer blackwidow v4": "mecanico",
    "asus rog strix scope ii": "mecanico",
    "corsair k70 rgb pro": "mecanico",
    "razer huntsman v3 pro": "mecanico",
    "logitech g915 tkl": "mecanico",
    # Membrana
    "genius kb-110x": "membrana",
    "logitech k120": "membrana",
    "genius slimstar 130": "membrana",
    "logitech g213 prodigy": "membrana",
    "hyperx alloy core rgb": "membrana",
    "corsair k55 rgb pro": "membrana",
    # Tijera (scissor), no mecanico
    "logitech k380": "tijera",
    "logitech mx keys s": "tijera",
    # Hibrido mecha-membrana, no mecanico puro
    "razer ornata v3": "mecha-membrana",
}

# Etiqueta que va al campo `tipo` (se muestra en ficha/resultados; NO se busca,
# asi que aca SI podemos aclarar "no mecanico" sin contaminar el match).
ETIQUETA_TIPO = {
    "mecanico": "mecanico",
    "membrana": "membrana (no mecanico)",
    "tijera": "tijera / scissor (no mecanico)",
    "mecha-membrana": "mecha-membrana (no es mecanico puro)",
}

# Frase que se AGREGA a la descripcion (SI se busca). Token "mecanico" SOLO en la
# clase mecanico; las demas describen su tipo sin esa palabra.
FRASE_DESC = {
    "mecanico": "Es un teclado mecanico.",
    "membrana": "Es un teclado de membrana.",
    "tijera": "Es un teclado de switches tipo tijera, ideal portatil y oficina.",
    "mecha-membrana": "Es un teclado hibrido mecha-membrana.",
}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s).lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def _clasificar(nombre: str) -> tuple[str | None, str | None]:
    """Devuelve (clave_modelo, clase) o (None, None) si no matchea. Matchea la
    clave mas larga primero para evitar solapes."""
    n = _norm(nombre)
    for clave in sorted(TIPO_POR_MODELO, key=len, reverse=True):
        if clave in n:
            return clave, TIPO_POR_MODELO[clave]
    return None, None


def main():
    productos = get_all_products(force_refresh=True, tienda_id=TIENDA)
    teclados = [p for p in productos if _norm(p.get("categoria", "")) == "teclado"]
    print(f"Tienda {TIENDA}: {len(teclados)} teclados de {len(productos)} productos.")
    if not teclados:
        sys.exit(1)

    cambios = []
    sin_clasificar = []
    conteo = {}
    for p in teclados:
        nombre = p.get("nombre", "")
        clave, clase = _clasificar(nombre)
        if not clase:
            sin_clasificar.append((p.get("id"), nombre))
            continue
        conteo[clase] = conteo.get(clase, 0) + 1

        nuevos = {}
        etiqueta = ETIQUETA_TIPO[clase]
        if _norm(p.get("tipo") or "") != _norm(etiqueta):
            nuevos["tipo"] = etiqueta
        frase = FRASE_DESC[clase]
        desc = str(p.get("descripcion") or "").strip()
        if _norm(frase) not in _norm(desc):
            nuevos["descripcion"] = (desc + " " + frase).strip()
        if nuevos:
            cambios.append((p.get("id"), nombre, clase, nuevos))

    print(f"\nClasificacion: " + ", ".join(f"{k}={v}" for k, v in sorted(conteo.items())))
    print(f"A actualizar: {len(cambios)} de {len(teclados)}")
    if sin_clasificar:
        print(f"\n!! SIN CLASIFICAR ({len(sin_clasificar)}) — revisar:")
        for pid, nom in sin_clasificar:
            print(f"   {pid} | {nom}")

    print("\nEjemplos:")
    for pid, nombre, clase, nuevos in cambios[:6]:
        print(f"- {nombre} ({pid}) -> {clase}")
        for k, v in nuevos.items():
            print(f"    {k}: {v}")

    if not APLICAR:
        print("\nDRY-RUN: no se escribio nada. Para aplicar: --aplicar")
        return

    ok = 0
    for pid, _, _, nuevos in cambios:
        if not pid:
            continue
        upsert_product(pid, nuevos, tienda_id=TIENDA)
        ok += 1
    print(f"\nLISTO: {ok} teclados actualizados en {TIENDA}.")


if __name__ == "__main__":
    main()

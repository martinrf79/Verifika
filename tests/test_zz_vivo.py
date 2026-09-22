import asyncio
from app.core.respuesta import procesar_turno
TIENDA = "verifika_prod"

MENSAJES = [
    ("M13 premisa falsa", "hola el teclado K120 inalambrico ese cuanto sale? creo que se llama asi"),
    ("dato del cliente",  "tengo una PS5 y mi tele es 4k, que auriculares me recomendas?"),
    ("campo muerto",      "tenes algun procesador negro?"),
]

def test_vivo(firestore_doble):
    from app.core.contexto_turno import set_current_tienda
    from app.core.filtros_catalogo import limpiar_cache
    set_current_tienda(TIENDA); limpiar_cache()
    import time
    for nombre, texto in MENSAJES:
        print("\n" + "=" * 70)
        print(f"{nombre}\n  CLIENTE: {texto}")
        try:
            r = asyncio.run(procesar_turno(f"zz_{nombre[:6]}", texto,
                                           TIENDA, "test", f"zz{nombre[:4]}"))
            print(f"  BOT: {r}")
        except Exception as e:
            print(f"  ERROR: {type(e).__name__}: {str(e)[:200]}")
        time.sleep(12)

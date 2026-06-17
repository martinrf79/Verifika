"""
PING MERCADO PAGO — verifica en segundos si el token sirve para crear links.

Crea una preferencia de prueba de $100 con el MISMO codigo que usa el bot
(app/core/pago.py) y muestra el link. Si sale el link, el flag LINK_PAGO va a
funcionar en prod con ese token.

Uso:
    .\\correr_local.ps1 py scripts\\ping_mercadopago.py             # token de MP_ACCESS_TOKEN
    .\\correr_local.ps1 py scripts\\ping_mercadopago.py TOKEN      # token explicito
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

if len(sys.argv) > 1:
    os.environ["MP_ACCESS_TOKEN"] = sys.argv[1]

from app.core.pago import crear_link_pago  # noqa: E402


async def main():
    token = os.getenv("MP_ACCESS_TOKEN", "").strip()
    if not token:
        print("Sin token: pasalo como argumento o seteá MP_ACCESS_TOKEN en .secrets6.env")
        sys.exit(1)
    print(f"Token: {token[:12]}... ({'TEST' if 'TEST' in token else 'produccion u otro'})")
    url = await crear_link_pago(100, "Ping de prueba Verifika")
    if url:
        print(f"\nOK, el token FUNCIONA. Link de prueba ($100):\n{url}")
    else:
        print("\nFALLO: el token no genero link. Revisa que sea el Access Token "
              "de la aplicacion (panel de desarrolladores de Mercado Pago, "
              "credenciales de prueba o produccion).")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

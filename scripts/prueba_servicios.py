"""
Prueba del verificador de servicios. Sin Firestore ni credenciales.

Carga la FAQ real de verifika_demo, arma la evidencia igual que el orchestrator
(toda la FAQ como fuente de verdad) y corre escenarios: promesas inventadas que
deben bloquear, servicios reales y negaciones que deben pasar.

Correr:
    winvenv\\Scripts\\python.exe scripts\\prueba_servicios.py
"""
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from app.core.verificador_servicios import verificar_servicios  # noqa: E402

FAQ_PATH = RAIZ / "data" / "clientes" / "verifika_demo" / "faq.json"


def cargar_evidencia():
    """Evidencia tipo FAQ, igual forma que la que arma el orchestrator con
    VERIFIKA_FULL_FAQ_EVIDENCE=true."""
    faqs = json.loads(FAQ_PATH.read_text(encoding="utf-8"))
    # El json es una lista de temas; el loader real lo indexa por tema.
    evidence = []
    for data in faqs:
        evidence.append({
            "tipo": "faq",
            "id": data.get("tema"),
            "tema": data.get("tema"),
            "respuesta": data.get("respuesta", ""),
            "keywords": data.get("keywords", []),
            "valores": data.get("valores", []),
        })
    # Un par de productos para el corpus, como los que ve el verificador.
    evidence.append({
        "tipo": "producto", "nombre": "Auricular JBL 510",
        "categoria": "auriculares", "descripcion": "Bluetooth, plegable",
        "precio_ars": 45000,
    })
    return evidence


# (texto de respuesta, debe_bloquear, nota)
CASOS = [
    ("Perfecto, te lo envolvemos para regalo sin cargo y te lo mandamos.",
     True, "empaque regalo inventado"),
    ("Si queres podemos instalarte el equipo a domicilio.",
     True, "instalacion inventada (te lo instalamos a domicilio)"),
    ("Te lo puedo entregar en mano si estas en zona.",
     True, "entrega en mano inventada"),
    ("Si, podes retirarlo en nuestro local cuando quieras.",
     True, "retiro en local en tienda online"),
    ("Incluye garantia extendida de por vida sobre el producto.",
     True, "garantia extendida inventada"),
    ("Tenemos servicio tecnico propio que te lo repara.",
     True, "servicio tecnico inventado"),
    ("Si, te lo mando armado y listo para usar.",
     True, "armado inventado"),
    ("Si queres te armamos la PC completa: armado y test por 25000, incluye "
     "ensamblado, cableado e instalacion de Windows.",
     True, "servicio de armado de PC inventado (caso r032 real)"),
    ("Viene con los cables necesarios para su instalacion, es modular.",
     False, "instalacion como sustantivo de ficha, no servicio"),
    ("La garantia no cubre danos por instalacion incorrecta del usuario.",
     False, "instalacion en clausula de garantia, no servicio"),
    # No deben bloquear:
    ("Hacemos envios a todo el pais por Andreani y OCA.",
     False, "envio real de la FAQ"),
    ("No hacemos envoltorio para regalo, va en su caja original.",
     False, "negacion de empaque regalo"),
    ("No tenemos local fisico, somos solo online y despachamos de Buenos Aires.",
     False, "online only, no promete retiro"),
    ("El producto tiene garantia oficial de 12 meses del fabricante.",
     False, "garantia normal, no extendida"),
    ("Aceptamos transferencia, Mercado Pago y tarjetas. Hasta 6 cuotas sin interes.",
     False, "formas de pago reales"),
    ("El auricular JBL 510 sale 45000 pesos, bluetooth y plegable.",
     False, "respuesta comercial normal"),
]


def main():
    evidence = cargar_evidencia()
    ok_total = 0
    for texto, debe_bloquear, nota in CASOS:
        r = verificar_servicios(texto, evidence)
        bloqueo = not r["ok"]
        bien = bloqueo == debe_bloquear
        ok_total += bien
        estado = "OK " if bien else "FALLA"
        esperado = "BLOQUEA" if debe_bloquear else "PASA   "
        real = "BLOQUEA" if bloqueo else "PASA   "
        inv = ",".join(r["servicios_inventados"]) or "-"
        print(f"[{estado}] esperado={esperado} real={real} inv={inv:<22} | {nota}")
    print(f"\n{ok_total}/{len(CASOS)} OK")
    sys.exit(0 if ok_total == len(CASOS) else 1)


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
Test determinista del verificador de HECHOS. Sin Firestore, sin credenciales.
Casos a CAZAR: las respuestas reales de la charla de Jorge que narraron mal una
regla. Casos que deben PASAR: respuestas que citan la regla correcta o son
neutras. Mide precision (no marcar de mas) y recall (cazar lo que debe).

Correr: winvenv\\Scripts\\python.exe scripts\\prueba_hechos.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.core.verificador_hechos import verificar_hechos, construir_ficha

# FAQ de demo, recortada a lo que importa para hechos.
EVID = [
    {"tipo": "faq", "tema": "plazo_envio",
     "respuesta": "CABA y GBA 2 a 3 dias habiles desde el pago acreditado. "
                  "Interior 4 a 7 dias habiles."},
    {"tipo": "faq", "tema": "envio_urgente",
     "respuesta": "Hacemos envios express en CABA y GBA con costo extra y "
                  "entrega en 24 horas habiles."},
    {"tipo": "faq", "tema": "formas_pago",
     "respuesta": "Aceptamos transferencia bancaria, Mercado Pago, tarjetas de "
                  "credito y debito Visa, Mastercard y American Express."},
    {"tipo": "faq", "tema": "costo_envio",
     "respuesta": "Envio a CABA y GBA 3000 pesos. Interior segun localidad "
                  "entre 5000 y 12000 pesos."},
]

# (texto, debe_marcar, etiqueta)
CASOS = [
    # --- DEBEN MARCAR (los inventos reales de Jorge) ---
    ("Tranqui, los envios los manejamos por Andreani y OCA, que llegan en 24 a "
     "72 horas habiles al interior. Si sale el lunes, el jueves estaria "
     "llegando sin problema.", True, "jorge: horas + dia entrega"),
    ("Si Jorge, American Express la aceptamos directo, sin intermediarios. "
     "Podes pagar con tu tarjeta sin problema.", True, "jorge: pago directo"),
    ("Lo preparamos para que salga a principio de semana y lo recibis el "
     "jueves.", True, "jorge: recibis el jueves"),
    ("El envio al interior tarda 24 horas.", True, "interior en horas"),
    ("Si pagas hoy por transferencia, el pedido sale manana y llega entre jueves "
     "y viernes, justo antes del sabado. No te puedo asegurar un dia exacto "
     "porque el correo no lo garantiza.", True,
     "promete dia + hedge en oracion posterior"),
    ("Con el express, si pagas hoy se acredita en el dia y te lo deja manana "
     "martes sin falta.", True, "molino: te lo deja manana martes (verbo dejar)"),
    # --- DEBEN PASAR (correctos o neutros) ---
    ("Para este jueves no llega, recien la semana que viene.", False,
     "niega el dia en la misma clausula"),
    ("El envio al interior tarda entre 4 y 7 dias habiles por Andreani y OCA. "
     "No te puedo confirmar un dia exacto porque depende del correo.",
     False, "cita el plazo correcto"),
    ("Atendemos de lunes a viernes de 9 a 18 hs y sabados de 10 a 13 hs.",
     False, "horario de atencion, no entrega"),
    ("Aceptamos American Express sin problema, junto con Visa y Mastercard.",
     False, "amex sin inventar 'directo'"),
    ("El Soporte ergonomico notebook esta 25000 pesos, es de aluminio "
     "plegable. Te lo enviamos a tu domicilio.", False, "neutro"),
    ("En CABA tenemos envio express con entrega en 24 horas habiles.",
     False, "express en zona habilitada"),
]


def main():
    print("=== Ficha derivada de la FAQ ===")
    f = construir_ficha(EVID)
    for k, v in f.items():
        if k != "formas_pago_texto":
            print(f"  {k}: {v}")
    print()
    ok = 0
    for texto, debe, etiq in CASOS:
        res = verificar_hechos(texto, EVID, trace_id=etiq)
        marco = not res["ok"]
        bien = marco == debe
        ok += bien
        estado = "OK " if bien else "FALLA"
        signo = "MARCA" if marco else "pasa "
        print(f"[{estado}] {signo} | esperado={'marca' if debe else 'pasa'} | "
              f"{etiq} -> {res['problemas']}")
    print(f"\n{ok}/{len(CASOS)} casos correctos")
    sys.exit(0 if ok == len(CASOS) else 1)


if __name__ == "__main__":
    main()

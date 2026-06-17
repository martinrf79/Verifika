"""
Recalibra los generadores de datasets (100/200 preguntas) al catalogo de
verifika_prod (esqueleto unico desde 10-jun-2026). Reemplaza SOLO las preguntas
que nombran productos inexistentes en prod por equivalentes reales de la misma
categoria, manteniendo la etiqueta de comportamiento. Cero LLM: todo por codigo.

Cada reemplazo se asserta: si el texto original no esta (ya se corrio antes o
cambio el archivo), avisa en vez de fallar silencioso.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPLEJO = ROOT / "pruebas" / "generar_dataset_complejo.py"

# (original, reemplazo) — el reemplazo usa productos VERIFICADOS en prod.
REEMPLAZOS = [
    # mixtos: productos que no existen en prod
    ('"el cable HDMI lo puedo retirar en local"',
     '"el router TP-Link lo puedo retirar en local"'),
    ('"el envio de la lampara Xiaomi a La Plata"',
     '"el envio del cargador Xiaomi a La Plata"'),
    ('"el envio del kit limpieza GoldenTech sale algo"',
     '"el envio del parlante Logitech Z313 sale algo"'),
    ('"el adaptador WiFi TP-Link es nuevo o usado"',
     '"el router TP-Link es nuevo o usado"'),
    ('"puedo pagar el Hub Anker en 3 cuotas"',
     '"puedo pagar el cargador Anker en 3 cuotas"'),
    ('"la bateria Xiaomi viene con factura"',
     '"el cargador Xiaomi viene con factura"'),
    ('"el cooler Watercooling Cooler Master tiene envio express"',
     '"la fuente Cooler Master tiene envio express"'),
    ('"el gamepad Xbox Wireless tiene garantia oficial"',
     '"el microfono HyperX QuadCast tiene garantia oficial"'),
    ('"el SSD Kingston A2000 tiene 12 cuotas"',
     '"el SSD Kingston NV2 tiene 12 cuotas"'),
    ('"puedo retirar el Soporte VESA en buenos aires"',
     '"puedo retirar el gabinete en buenos aires"'),
    ('"el organizador de cables tiene factura A"',
     '"la memoria ram Kingston Fury tiene factura A"'),
    ('"puedo pagar el Razer Goliathus en efectivo"',
     '"puedo pagar los auriculares JBL en efectivo"'),
    ('"el Joystick Logitech F310 viene con manual"',
     '"el parlante Logitech viene con manual"'),
    ('"es nuevo el Soporte ergonomico notebook"',
     '"es nueva la notebook Lenovo IdeaPad"'),
    ('"el envio del pad SteelSeries QcK Mini al sur"',
     '"el envio del mouse Redragon Cobra al sur"'),
    # contradicciones: la afirmacion falsa tiene que seguir siendo FALSA en prod
    ('"el cable HDMI cuesta 25 mil pesos no 9500"',
     '"la memoria Kingston Fury DDR4 cuesta 25 mil no 34500"'),
    ('"el SSD Samsung 980 es de 2TB"',  # en prod el 980 2TB SI existe
     '"el SSD Samsung 980 es de 8TB"'),
    ('"el adaptador TP-Link es wifi 6"',
     '"el router TP-Link Archer C6 es wifi 6"'),
    ('"el Hub Anker tiene 12 puertos"',
     '"la webcam C920 es 4K"'),
    ('"la lampara Xiaomi es de pie"',
     '"el cargador Xiaomi es de 65W"'),
    ('"el Watercooling Cooler Master es de 360mm"',
     '"la fuente Cooler Master es de 850W"'),
    ('"el SSD Kingston tiene 1TB"',  # en prod el NV2 1TB SI existe
     '"el SSD Kingston NV2 es SATA"'),
    # ambiguedades: referencias por precio de la era demo
    ('"cual era el de Samsung de 225"',
     '"cual era el de Samsung de 117"'),
    ('"el mouse Logitech a 38 mil que tenia RGB"',
     '"el mouse Logitech a 37 mil y pico que tenia RGB"'),
    ('"el hub con HDMI"',
     '"el parlante chico para escritorio"'),
]

texto = COMPLEJO.read_text(encoding="utf-8")
hechos, faltantes = 0, []
for orig, nuevo in REEMPLAZOS:
    if orig in texto:
        texto = texto.replace(orig, nuevo)
        hechos += 1
    else:
        faltantes.append(orig)
COMPLEJO.write_text(texto, encoding="utf-8")

print(f"generar_dataset_complejo.py: {hechos}/{len(REEMPLAZOS)} reemplazos")
for f in faltantes:
    print(f"  NO ENCONTRADO (revisar a mano): {f}")
print("generar_dataset_200.py: sin cambios necesarios (logitech, redragon "
      "kumara, hyperx y webcam existen en prod)")

# -*- coding: utf-8 -*-
"""
Test determinista del LIBRO DE ASIENTOS (Fase 2). Sin Firestore, sin LLM.

Cubre las tres piezas:
  1) parsear_libro: extrae el bloque del texto crudo, lo saca de la prosa, arma
     los asientos. Tolera bloque ausente, vacio y abierto sin cerrar.
  2) auditar_libro: cuadra cada asiento contra la evidencia POR fuente; corrige el
     valor mal contra su fuente declarada; marca como problema lo sin respaldo.
  3) aplicar_correcciones: reescribe la cifra mala por la verdadera en la prosa.

Correr: winvenv\\Scripts\\python.exe scripts\\prueba_libro.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.core.libro import (
    parsear_libro, auditar_libro, aplicar_correcciones, libro_aprobado,
    guarda_completitud,
)
from app.core.corrector import _bloque_libro

# Evidencia: dos productos (120k y 130k) y un PROOF con envio fijo 5k.
# Totales validos: subtotal 250.000 y con envio 255.000. Catalogo: 120.000, 130.000.
PROOF = {
    "tipo": "calculo",
    "subtotal_productos": 250000,
    "operandos_productos": [{"monto": 120000}, {"monto": 130000}],
    "operandos_extras": [{"modalidad": "fijo", "monto": 5000, "concepto": "envio"}],
    "resultado": 255000,
}
EVID = [
    {"tipo": "producto", "precio_ars": 120000},
    {"tipo": "producto", "precio_ars": 130000},
    {"tipo": "proof", "tool": "calculate_total", "proof": PROOF},
    {"tipo": "faq", "tema": "costo_envio",
     "respuesta": "Envio a CABA y GBA 5000 pesos.",
     "valores": [{"monto": 5000}]},
]

resultados = []


def check(nombre, cond):
    resultados.append((nombre, bool(cond)))
    estado = "OK " if cond else "FALLA"
    print(f"[{estado}] {nombre}")


# ── 1) PARSER ──
print("=== parser ===")
prosa, asientos, hubo = parsear_libro(
    "Te llevas los dos, total con envio $255.000.\n"
    "[[LIBRO]]\n"
    "255000 | calculo | total con envio\n"
    "120000 | catalogo | precio del mouse\n"
    "[[/LIBRO]]")
check("parser: hubo libro", hubo)
check("parser: 2 asientos", len(asientos) == 2)
check("parser: prosa sin bloque", "[[LIBRO]]" not in prosa and "255.000" in prosa)
check("parser: valores y fuentes",
      asientos[0]["valor"] == 255000 and asientos[0]["fuente"] == "calculo"
      and asientos[1]["fuente"] == "catalogo")

p2, a2, h2 = parsear_libro("Respuesta sin libro, nada que sacar.")
check("parser: sin bloque deja intacto", (not h2) and a2 == [] and p2.startswith("Respuesta"))

p3, a3, h3 = parsear_libro("Hola.\n[[LIBRO]]\n255000 | calculo | total")
check("parser: bloque abierto sin cerrar no se filtra",
      "[[LIBRO]]" not in p3 and "255000" not in p3)

# ── 2) AUDITOR ──
print("\n=== auditor ===")
# total mal (258k declarado como calculo) -> corrige a 255k
aud = auditar_libro([{"valor": 258000, "fuente": "calculo", "afirmacion": "total"}], EVID)
check("auditor: corrige total 258k->255k",
      any(c["de"] == 258000 and c["a"] == 255000 for c in aud["correcciones"])
      and aud["ok"])

# precio mal (118k declarado catalogo) -> corrige a 120k contra catalogo
aud2 = auditar_libro([{"valor": 118000, "fuente": "catalogo", "afirmacion": "mouse"}], EVID)
check("auditor: corrige precio 118k->120k contra catalogo",
      any(c["de"] == 118000 and c["a"] == 120000 for c in aud2["correcciones"]))

# asiento correcto -> no toca, ok
aud3 = auditar_libro([{"valor": 255000, "fuente": "calculo", "afirmacion": "total"}], EVID)
check("auditor: asiento correcto no genera correccion",
      aud3["correcciones"] == [] and aud3["ok"])

# numero inventado lejos -> problema, no ok, sin correccion
aud4 = auditar_libro([{"valor": 400000, "fuente": "calculo", "afirmacion": "total"}], EVID)
check("auditor: inventado lejos queda como problema",
      aud4["correcciones"] == [] and (not aud4["ok"]) and len(aud4["problemas"]) == 1)

# fuente equivocada pero la verdad existe en la fuente declarada:
# 252000 declarado calculo, mas cerca de 250000 (subtotal) -> corrige
aud5 = auditar_libro([{"valor": 252000, "fuente": "calculo", "afirmacion": "total"}], EVID)
check("auditor: 252k->250k (subtotal, calculo)",
      any(c["a"] == 250000 for c in aud5["correcciones"]))

# fix anti-corrupcion (caso Corsair): un precio real de catalogo NO se pisa aunque
# no este en la evidencia del turno (viene citado de un turno anterior).
EVID_corr = [{"tipo": "producto", "precio_ars": 18000}]  # otro producto, cercano
asiento_real = [{"valor": 20000, "fuente": "catalogo", "afirmacion": "teclado"}]
aud_sin = auditar_libro(asiento_real, EVID_corr)
check("auditor: SIN red pisa el precio real (reproduce el bug Corsair)",
      any(c["de"] == 20000 for c in aud_sin["correcciones"]))
aud_con = auditar_libro(asiento_real, EVID_corr, precios_validos={20000})
check("auditor: CON red NO pisa el precio real (fix)",
      aud_con["correcciones"] == [])

# ── 3) APLICADOR ──
print("\n=== aplicador ===")
prosa_mal = "Listo, el total con envio te queda $258.000, un golazo."
ap = aplicar_correcciones(prosa_mal, [{"de": 258000, "a": 255000}])
check("aplicador: reescribe 258.000 -> 255.000",
      ap["cambiada"] and "255.000" in ap["respuesta"] and "258.000" not in ap["respuesta"])

ap2 = aplicar_correcciones("No hay cifras que tocar aca.", [{"de": 258000, "a": 255000}])
check("aplicador: sin match no cambia", not ap2["cambiada"])

# ── 4) LIBRO APROBADO (Fase 3) ──
print("\n=== libro aprobado ===")
asientos_f3 = [
    {"valor": 258000, "fuente": "calculo", "afirmacion": "total"},   # se corrige
    {"valor": 120000, "fuente": "catalogo", "afirmacion": "mouse"},  # ok
    {"valor": 400000, "fuente": "calculo", "afirmacion": "total"},   # fuga
]
aud_f3 = auditar_libro(asientos_f3, EVID)
aprob = libro_aprobado(asientos_f3, aud_f3)
valores_aprob = {a["valor"] for a in aprob}
check("aprobado: aplica correccion (255000 dentro)", 255000 in valores_aprob)
check("aprobado: conserva el ok (120000 dentro)", 120000 in valores_aprob)
check("aprobado: descarta la fuga (400000 fuera)", 400000 not in valores_aprob)

# ── 5) BLOQUE DEL CORRECTOR (Fase 3) ──
print("\n=== bloque corrector ===")
bloque = _bloque_libro(aprob)
check("bloque: lista cifras aprobadas con formato $",
      "$255.000" in bloque and "$120.000" in bloque and "unica verdad" in bloque)
check("bloque: no incluye la fuga", "$400.000" not in bloque)
check("bloque: sin libro devuelve vacio", _bloque_libro(None) == "" and _bloque_libro([]) == "")

# ── 6) GUARDA DE COMPLETITUD (Fase 4) ──
print("\n=== guarda de completitud ===")
LIBRO_OK = [
    {"valor": 120000, "fuente": "catalogo", "afirmacion": "mouse"},
    {"valor": 130000, "fuente": "catalogo", "afirmacion": "teclado"},
    {"valor": 255000, "fuente": "calculo", "afirmacion": "total con envio"},
]
# Toda cifra de la prosa esta en el libro -> sin fugas.
g_ok = guarda_completitud(
    "El mouse sale $120.000 y el teclado $130.000, total con envio $255.000.",
    LIBRO_OK, EVID)
check("guarda: todo en el libro pasa", g_ok["ok"] and g_ok["fugas"] == [])

# Suma de asientos (subtotal 250.000 = 120k+130k) no declarada -> se acepta.
g_suma = guarda_completitud(
    "El subtotal es $250.000 sin contar el envio.", LIBRO_OK, EVID)
check("guarda: suma de asientos se acepta", g_suma["ok"])

# Cifra que existe en la evidencia (5.000 de envio) pero NO en el libro -> fuga
# de contrabando, marcada en_evidencia=True.
g_contra = guarda_completitud(
    "El envio te sale $5.000 aparte.", LIBRO_OK, EVID)
check("guarda: contrabando (real, no declarado) es fuga en_evidencia=True",
      (not g_contra["ok"]) and any(
          f["valor"] == 5000 and f["en_evidencia"] for f in g_contra["fugas"]))

# Cifra inventada lejos de todo -> fuga en_evidencia=False.
g_inv = guarda_completitud(
    "Tenemos una promo de $99.000 en este combo.", LIBRO_OK, EVID)
check("guarda: invento es fuga en_evidencia=False",
      (not g_inv["ok"]) and any(
          f["valor"] == 99000 and not f["en_evidencia"] for f in g_inv["fugas"]))

# Multiplo de catalogo (2x120.000=240.000) no declarado en el libro: es fuga, pero
# en_evidencia=True porque es aritmetica real de catalogo, no un invento.
g_mult = guarda_completitud("Por 2 mouse iguales son $240.000.", LIBRO_OK, EVID)
check("guarda: multiplo de catalogo no declarado es fuga en_evidencia=True",
      (not g_mult["ok"]) and any(
          f["valor"] == 240000 and f["en_evidencia"] for f in g_mult["fugas"]))

# Sin libro (libro vacio) toda cifra es fuga: la guarda no se relaja sola.
g_vacio = guarda_completitud("Total $255.000.", [], EVID)
check("guarda: libro vacio marca la cifra como fuga", not g_vacio["ok"])

# ── RESUMEN ──
ok = sum(1 for _, b in resultados if b)
print(f"\n{ok}/{len(resultados)} chequeos correctos")
sys.exit(0 if ok == len(resultados) else 1)

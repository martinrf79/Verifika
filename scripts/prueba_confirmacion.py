"""
PRUEBA — CONFIRMACION_PROVIDER (la pregunta de confirmacion por codigo), SIN LLM.

Verifica que construir_confirmacion arma la frase desde los candidatos reales del
Provider (A/B de foco, ambiguos de multi), que la señal del interprete es pista y
no veredicto (el codigo decide con el catalogo), y que el campo sale SIEMPRE
completo, nunca null.

Funcion pura: se arma el dict de proveer() a mano.

Correr:
    set PYTHONPATH=.
    .\\venv-win\\Scripts\\python.exe .\\scripts\\prueba_confirmacion.py
"""
from app.core.confirmacion import construir_confirmacion

fallos = []


def chequear(nombre, cond):
    print(f"[{'OK ' if cond else 'FALLA'}] {nombre}")
    if not cond:
        fallos.append(nombre)


CLAVES = ("necesita", "tipo", "texto", "opciones", "hint")


def _cot(pid, nombre, precio, cantidad=1):
    return {"producto_id": pid, "nombre": nombre, "cantidad": cantidad,
            "con_envio": False,
            "calc": {"ok": True, "total_ars": precio * cantidad,
                     "subtotal_productos_ars": precio * cantidad,
                     "detalle": [{"id": pid, "nombre": nombre,
                                  "cantidad": cantidad, "precio_unitario": precio,
                                  "subtotal": precio * cantidad}]}}


# ── 1) A/B: el foco matcheo dos productos del registro ──
prov_ab = {"ab": {"opciones": [
    _cot("MON_LG_27", "Monitor LG UltraGear 27", 410000),
    _cot("MON_SAM_27", "Monitor Samsung Odyssey G5 27", 380000)]}}
c = construir_confirmacion(prov_ab)
chequear("ab: necesita confirmacion", c["necesita"] is True)
chequear("ab: tipo a_o_b", c["tipo"] == "a_o_b")
chequear("ab: nombra las dos opciones reales",
         "LG UltraGear" in c["texto"] and "Odyssey G5" in c["texto"])
chequear("ab: muestra los dos precios", "$410.000" in c["texto"]
         and "$380.000" in c["texto"])
chequear("ab: cierra preguntando", c["texto"].strip().endswith("Cual preferis?"))
chequear("ab: opciones con id real", len(c["opciones"]) == 2
         and c["opciones"][0]["id"] == "MON_LG_27")

# ── 2) MULTI ambiguos: el caso del ejemplo (3 teclados inalambricos) ──
prov_multi = {"multi": {"items": [], "calc": None, "ambiguos": [
    {"termino": "teclado", "cantidad": 3, "candidatos": [
        {"id": "TEC_G915", "nombre": "Teclado inalambrico Logitech G915 TKL",
         "precio_ars": 512500},
        {"id": "TEC_K380", "nombre": "Teclado inalambrico Logitech K380",
         "precio_ars": 55000}]}]}}
c = construir_confirmacion(prov_multi)
chequear("multi: necesita confirmacion", c["necesita"] is True)
chequear("multi: tipo te_referis_a", c["tipo"] == "te_referis_a")
chequear("multi: nombra la cantidad y el termino", "3 teclado" in c["texto"])
chequear("multi: lista los dos modelos con precio",
         "G915" in c["texto"] and "$512.500" in c["texto"]
         and "K380" in c["texto"] and "$55.000" in c["texto"])
chequear("multi: opciones con id y termino",
         len(c["opciones"]) == 2 and c["opciones"][0]["termino"] == "teclado")

# ── 3) MULTI con DOS terminos ambiguos: una frase por cada uno ──
prov_dos = {"multi": {"items": [], "calc": None, "ambiguos": [
    {"termino": "mouse", "cantidad": 2, "candidatos": [
        {"id": "M1", "nombre": "Logitech G203", "precio_ars": 38000},
        {"id": "M2", "nombre": "Razer DeathAdder", "precio_ars": 45000}]},
    {"termino": "auricular", "cantidad": 1, "candidatos": [
        {"id": "A1", "nombre": "HyperX Cloud II", "precio_ars": 60000},
        {"id": "A2", "nombre": "Redragon Zeus", "precio_ars": 48000}]}]}}
c = construir_confirmacion(prov_dos)
chequear("dos terminos: cubre mouse y auricular",
         "mouse" in c["texto"] and "auricular" in c["texto"])
chequear("dos terminos: cierra con 'de cada uno'",
         "de cada uno" in c["texto"])
chequear("dos terminos: junta las cuatro opciones", len(c["opciones"]) == 4)

# ── 4) PISTA del interprete pero el catalogo RESOLVIO: no se pregunta ──
prov_resuelto = {"foco": {"producto_id": "SSD1", "nombre": "SSD Samsung",
                          "cantidad": 1, "calc": {"ok": True,
                          "presentacion": "x", "total_ars": 225000}}}
c = construir_confirmacion(prov_resuelto,
                           interpretacion={"tipo_confirmacion": "a_o_b"})
chequear("pista sin ambiguedad: el codigo NO pregunta", c["necesita"] is False)
chequear("pista sin ambiguedad: guarda la pista informativa",
         c["hint"] == "a_o_b")
chequear("pista sin ambiguedad: texto vacio", c["texto"] == "")

# ── 5) SIN nada: campo vacio pero completo (nunca null) ──
c = construir_confirmacion({})
chequear("vacio: necesita False", c["necesita"] is False)
chequear("vacio: trae todas las claves", all(k in c for k in CLAVES))

# ── 6) INVARIANTE: toda salida comparte el mismo esqueleto ──
salidas = [construir_confirmacion(prov_ab),
           construir_confirmacion(prov_multi),
           construir_confirmacion(prov_resuelto),
           construir_confirmacion({})]
chequear("invariante: todas las salidas comparten claves",
         all(set(s) == set(CLAVES) for s in salidas))

print()
if fallos:
    print(f"RESULTADO: {len(fallos)} FALLAS")
    for f in fallos:
        print(f"  - {f}")
    raise SystemExit(1)
print("RESULTADO: TODO OK")

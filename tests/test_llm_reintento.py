

# ── EL CUPO AGOTADO NO ES UNA NOTA CERO (9-ago-2026) ────────────────────────

def test_el_cupo_agotado_se_anota_solo_cuando_se_agotan_los_reintentos():
    """LA FALLA QUE LO PARIO, y costo una corrida entera de la clave paga. El
    proveedor se quedo sin credito a mitad de `objetivo.py --vivo`: cinco de
    quince turnos nunca le hablaron al modelo, salieron con el fallback, y la
    vara los puntuo CERO. El resultado se leia como una regresion enorme del
    codigo y no habia ninguna.

    Una rafaga que el backoff absorbe NO se anota: esa corrida si probo el
    codigo y su nota vale."""
    import asyncio
    from app.core import llm_reintento as LR

    LR.reiniciar_cupo()
    intentos = {"n": 0}

    def falla_una_vez():
        intentos["n"] += 1
        if intentos["n"] == 1:
            raise RuntimeError("Error code: 429 - rate limit")
        return "salio bien"

    assert asyncio.run(LR.llamar_con_reintento(falla_una_vez, base_s=0)) == "salio bien"
    assert LR.sin_cupo()["veces"] == 0, "una rafaga absorbida no invalida nada"

    def siempre_sin_credito():
        raise RuntimeError("Error code: 429 - Your prepayment credits are depleted.")

    LR.reiniciar_cupo()
    try:
        asyncio.run(LR.llamar_con_reintento(siempre_sin_credito, base_s=0))
    except RuntimeError:
        pass
    assert LR.sin_cupo()["veces"] == 1
    assert "depleted" in LR.sin_cupo()["ultimo"]

    # Un error que NO es de cuota no se cuenta como cupo: es un defecto de
    # verdad y tiene que puntuar.
    LR.reiniciar_cupo()

    def rota_de_verdad():
        raise ValueError("el molde no valida")

    try:
        asyncio.run(LR.llamar_con_reintento(rota_de_verdad, base_s=0))
    except ValueError:
        pass
    assert LR.sin_cupo()["veces"] == 0
    LR.reiniciar_cupo()


def test_la_corrida_sin_medir_no_baja_el_promedio():
    """La vara tiene que decir SIN MEDIR, no cero. Si la corrida negada contara
    como cero, el numero manda a arreglar codigo que ni siquiera corrio."""
    from banco_pruebas.objetivo import _tabla

    res = {"modo": "vivo", "repeticiones": 2, "invalidas": 1,
           "nota": {"nota": 88, "peor": 88},
           "variantes": [{"variante": "1_x", "medidas": 1, "de": 2,
                          "prom": 88, "min": 88, "max": 88, "largo": 900,
                          "corridas": [
                              {"invalida": False, "largo": 900,
                               "nota": {"nota": 88}, "estado": [],
                               "comunicacion": []},
                              {"invalida": True, "largo": 146,
                               "nota": {"nota": None}, "estado": [],
                               "comunicacion": [], "motivo": "credits"}]}]}
    salida = _tabla(res)
    assert "88" in salida
    assert "1 corridas quedaron SIN MEDIR" in salida
    assert "1 de 2 medidas" in salida

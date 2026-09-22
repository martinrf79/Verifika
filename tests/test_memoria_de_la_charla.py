"""LA MEMORIA DE LA CHARLA Y LA PLATA DE LA CASA — lo que midio la tanda de
charlas del 22-sep-2026 (`banco_pruebas/tanda_charlas.py`).

Dos defectos que la vara de mensajes sueltos no podia ver:

  1. "EL SEGUNDO CUANTO PESA?" contesto por el G203 cuando el segundo que el
     bot habia nombrado era el G502. La memoria guardaba todas las fichas que
     volvian de buscar, al final y solo si eran nuevas, y mostraba las OCHO MAS
     VIEJAS diciendo que la ultima era la mas reciente.

  2. "Y CUANTO ME SALE MANDARLO A ROSARIO?" salio como "no tengo esa
     informacion confirmada", 2 de 2. El modelo copio la tarifa y el envio
     gratis desde $250.000 que el motor le devolvio, y la guarda de la plata
     tiro la respuesta entera por el umbral: miraba fichas, envios y cuenta,
     no lo que la casa tiene escrito.
"""
import asyncio

from app.core import respuesta as R

TIENDA = "verifika_prod"


def _ficha(pid: str, nombre: str, precio: str) -> dict:
    return {"id": pid, "nombre": nombre, "precio": precio}


G203 = _ficha("MOU0001", "Mouse Logitech G203 Lightsync Negro", "$37.500")
G502 = _ficha("MOU0003", "Mouse Logitech G502 Hero Negro", "$70.000")
SUPER = _ficha("MOU0005", "Mouse Logitech G Pro X Superlight Negro",
               "$163.000")
M170 = _ficha("MOU0009", "Mouse Logitech M170 Negro", "$12.000")


def test_lo_nombrado_queda_en_el_orden_en_que_el_cliente_lo_leyo(
        firestore_doble):
    """Las fichas vuelven en el orden del motor; el cliente lee el de la
    respuesta. 'El segundo' es el segundo que LEYO."""
    texto = ("Tengo el G502 Hero a $70.000, el G203 Lightsync a $37.500 y "
             "el G Pro X Superlight a $163.000.")
    vistos = R._vistos_al_dia([], [G203, G502, SUPER, M170], texto, 1, TIENDA)
    assert [p["id"] for p in vistos] == ["MOU0003", "MOU0001", "MOU0005"]
    assert all(p["turno"] == 1 for p in vistos)


def test_lo_que_no_se_nombro_no_entra_como_si_se_hubiera_mostrado(
        firestore_doble):
    """Volvio el M170 de la busqueda pero la respuesta no lo nombro: "ese"
    no puede apuntar a algo que el cliente nunca leyo."""
    vistos = R._vistos_al_dia([], [G203, M170], "El G203 sale $37.500.", 1,
                              TIENDA)
    assert [p["id"] for p in vistos] == ["MOU0001"]


def test_lo_que_se_vuelve_a_nombrar_pasa_al_final(firestore_doble):
    previos = [dict(G203, turno=1), dict(G502, turno=1)]
    vistos = R._vistos_al_dia(previos, [G203], "Si, el G203 blanco.", 2,
                              TIENDA)
    assert [p["id"] for p in vistos] == ["MOU0003", "MOU0001"]
    assert vistos[-1]["turno"] == 2


def test_sin_nada_nombrado_se_guardan_las_fichas_para_no_perder_el_id(
        firestore_doble):
    """Olvidar es peor que recordar de mas: si no se pudo aparear nada, se
    guarda como antes, sin turno, y no pisa la lista del turno anterior."""
    vistos = R._vistos_al_dia([], [M170], "Te paso la tarifa.", 1, TIENDA)
    assert [p["id"] for p in vistos] == ["MOU0009"]
    assert vistos[0]["turno"] == 0


def test_la_memoria_numera_lo_ultimo_que_nombro():
    conv = {"productos_vistos": [
        dict(M170, turno=1),
        dict(G502, turno=2), dict(G203, turno=2), dict(SUPER, turno=2)]}
    m = R._memoria_texto(conv)
    assert "1. MOU0003" in m and "2. MOU0001" in m and "3. MOU0005" in m
    assert "el segundo" in m.lower()
    assert "MOU0009" in m, "lo de antes tambien se recuerda"


def test_la_memoria_muestra_lo_MAS_RECIENTE_y_no_lo_mas_viejo():
    """Con doce vistos mostraba los ocho primeros: el reciente no llegaba."""
    vistos = [_ficha(f"X{i:02d}", f"Producto {i}", "$1") for i in range(12)]
    m = R._memoria_texto({"productos_vistos": vistos})
    assert "X11" in m and "X00" not in m


def test_el_umbral_que_la_casa_devolvio_no_tira_la_respuesta(
        firestore_doble, monkeypatch):
    """La tarifa y el 'envio gratis desde $250.000' volvieron del motor: son
    fuente, y copiarlos no es inventar."""
    texto = ("El envio a Rosario sale $7.000. Recorda que es gratis a partir "
             "de $250.000.")
    salida = {"tipo": "costo_envio", "texto": texto,
              "fuente_casa": '{"filas": [{"destino": "Rosario", '
                             '"monto_ars": 7000}], "gratis_desde": 250000}'}
    informe = R._informe_en_blanco()
    informe["llamadas"] = 1
    monkeypatch.setattr(
        R, "_preguntar",
        lambda *a, **k: asyncio.sleep(
            0, result=(salida, [], {"Rosario": 7000}, {}, informe)))
    fuera = asyncio.run(R.procesar_turno(
        "sonda_umbral", "y a Rosario?", TIENDA, "telegram", "trace_umbral"))
    assert "250.000" in fuera, fuera


def test_un_umbral_que_NADIE_devolvio_sigue_cayendo(firestore_doble,
                                                    monkeypatch):
    """El arreglo no abre la puerta: una cifra sin procedencia sigue tirando
    la respuesta."""
    salida = {"tipo": "costo_envio", "fuente_casa": "",
              "texto": "Es gratis a partir de $999.999."}
    informe = R._informe_en_blanco()
    informe["llamadas"] = 1
    monkeypatch.setattr(
        R, "_preguntar",
        lambda *a, **k: asyncio.sleep(0, result=(salida, [], {}, {}, informe)))
    fuera = asyncio.run(R.procesar_turno(
        "sonda_umbral2", "y a Rosario?", TIENDA, "telegram", "trace_u2"))
    assert "999.999" not in fuera


def test_un_modelo_en_dos_colores_es_UN_renglon():
    """'El G203 en negro o blanco' es una opcion para el cliente. Numerados por
    separado, 'el segundo' caia en el G203 blanco y no en el G502."""
    blanco = _ficha("MOU0002", "Mouse Logitech G203 Lightsync Blanco",
                    "$37.500")
    conv = {"productos_vistos": [
        dict(G203, turno=1, modelo="G203 Lightsync"),
        dict(blanco, turno=1, modelo="G203 Lightsync"),
        dict(G502, turno=1, modelo="G502 Hero")]}
    m = R._memoria_texto(conv)
    assert "2. MOU0003" in m, m
    renglon_uno = next(r for r in m.splitlines() if r.startswith("1. "))
    assert "MOU0001" in renglon_uno and "MOU0002" in renglon_uno


def test_un_precio_no_se_confunde_con_un_modelo(firestore_doble):
    """Un modelo que es un numero pelado -'500 W1'- apareaba con cualquier
    precio terminado en 500. La clave de un modelo lleva letra Y numero."""
    assert "500" not in R._claves_modelo("500 W1")
    assert "g203" in R._claves_modelo("G203 Lightsync")


def test_si_la_respuesta_numera_los_colores_cada_color_es_su_renglon(
        firestore_doble):
    """'1. G203 negro, 2. G203 blanco, 3. G502': ahi el segundo ES el blanco,
    porque asi lo leyo el cliente."""
    blanco = _ficha("MOU0002", "Mouse Logitech G203 Lightsync Blanco",
                    "$37.500")
    texto = ("1. Mouse Logitech G203 Lightsync Negro ($37.500), 2. Mouse "
             "Logitech G203 Lightsync Blanco ($37.500), 3. Mouse Logitech "
             "G502 Hero Negro ($70.000)")
    vistos = R._vistos_al_dia([], [G502, blanco, G203], texto, 1, TIENDA)
    assert [p["id"] for p in vistos] == ["MOU0001", "MOU0002", "MOU0003"]
    m = R._memoria_texto({"productos_vistos": vistos})
    assert "2. MOU0002" in m, m


def test_si_la_respuesta_nombra_el_modelo_una_vez_los_colores_van_juntos(
        firestore_doble):
    blanco = _ficha("MOU0002", "Mouse Logitech G203 Lightsync Blanco",
                    "$37.500")
    texto = "el G203 Lightsync (negro o blanco) a $37.500 y el G502 Hero"
    vistos = R._vistos_al_dia([], [G502, blanco, G203], texto, 1, TIENDA)
    m = R._memoria_texto({"productos_vistos": vistos})
    assert "2. MOU0003" in m, m


# ── LO QUE EL CLIENTE EXCLUYO SIGUE VALIENDO EN EL TURNO SIGUIENTE ─────────
#
# CH21 de la tanda: "auriculares que no sean redragon" y al turno siguiente
# "y algo mas barato?" busco auriculares SIN la exclusion.

REDRAGON = {"categoria": "auriculares", "campo": "marca",
            "operador": "no_contiene", "valor": "redragon"}


def test_la_exclusion_se_arrastra_al_turno_siguiente():
    vig = R._vigentes_que_siguen([REDRAGON], "y algo mas barato?")
    assert list(vig) == ["auriculares"]
    (cond,) = vig["auriculares"].values()
    assert cond["valor"] == "redragon"


def test_si_el_cliente_vuelve_a_nombrar_el_valor_manda_lo_que_dice_ahora():
    """'ahora si, mostrame redragon': el codigo no le repone lo que levanto."""
    assert R._vigentes_que_siguen([REDRAGON], "ahora si, mostrame Redragon") \
        == {}


def test_un_filtro_positivo_no_se_arrastra():
    """Una positiva puede vaciar la busqueda; solo excluir o graduar pasa."""
    positiva = dict(REDRAGON, operador="contiene")
    assert R._vigentes_que_siguen([positiva], "otros?") == {}


def test_la_exclusion_se_repone_en_la_busqueda_del_mismo_rubro():
    from app.core import cotejo as CO
    vig = R._vigentes_que_siguen([REDRAGON], "y algo mas barato?")
    consultas = [{"categoria": "auriculares",
                  "ordenar_por": {"campo": "precio_ars", "direccion": "min"}}]
    CO.reponer_condiciones(consultas, vig)
    assert consultas[0]["condiciones"][0]["valor"] == "redragon"


def test_ida_y_vuelta_por_lo_que_se_guarda():
    vig = R._vigentes_que_siguen([REDRAGON], "otros?")
    guardado = R._vigentes_para_guardar(vig)
    assert guardado == [REDRAGON]
    m = R._memoria_texto({"preferencias_cliente": {"vigentes": guardado}})
    assert "redragon" in m.lower()

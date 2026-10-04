"""Las charlas reales de Martin por WhatsApp: el bot de hoy por el clon, o los nexos, con la vara escrita antes.

  LLM_PROVIDER=deepseek python3 banco_pruebas/nexos/correr_reales.py hoy hoy_ds
  python3 banco_pruebas/nexos/correr_reales.py nexos nexos_ds deepseek-chat

Deja banco_pruebas/nexos/reales_<etiqueta>.json y el informe: turnos bien, turnos con un dato falso, charlas enteras.
"""
import json, os, sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(os.path.dirname(AQUI))


def main(argv):
    sys.path.insert(0, AQUI)
    sys.path.insert(0, RAIZ)
    from banco_pruebas import clon_produccion as CP
    CP.preparar_entorno(); CP.instalar()
    from app.core.contexto_turno import set_current_tienda
    set_current_tienda(CP.TIENDA)
    import reales_vara as RV
    camino, etq = argv[0], argv[1]
    modelo = argv[2] if len(argv) > 2 else "deepseek-chat"
    res = {}
    for ch in RV.como_charlas():
        if camino == "hoy":
            from banco_pruebas import sonda_charlas as S
            res[ch["id"]] = [t["respuesta"] for t in S.correr_clon(ch)]
        else:
            import nexos as NX
            s = NX.Sesion()
            res[ch["id"]] = [s.turno_de(modelo, t["texto"])["respuesta"] for t in ch["turnos"]]
        print("listo", ch["id"], flush=True)
    json.dump(res, open(f"{AQUI}/reales_{etq}.json", "w"), ensure_ascii=False, indent=1)
    tot, b, f, chb, det = RV.informe(res)
    print(f"{etq}: turnos bien {b}/{tot}, turnos con dato falso {f}, charlas enteras bien {chb}/{len(RV.CHARLAS)}")
    print("\n".join(det))


if __name__ == "__main__":
    main(sys.argv[1:])

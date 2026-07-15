"""
VERIFICADOR DE CITA (ladrillo 2 del RAG de prosa) — la RED que chequea que la
cita de prosa que declaro el solver sea REAL. Va en la misma linea que los
otros verificadores de salida (plata, stock, faq): corre DESPUES de componer la
respuesta, es deterministico y NO llama al modelo. Su unico trabajo es
garantizar que cada bloque de criterio que el solver dice haber usado exista de
verdad en el corpus jurado (`guia_venta_prosa`), para que la prosa de venta
quede ATADA a la fuente igual que el numero.

La cita nace de las tools: cuando el solver llama `consultar_guia_venta`, el
resultado trae el `id` del chunk; esos ids son la cita, y el solver los declara
en `meta['prosa_citada']` (ladrillo 1). Este verificador los resuelve con
`texto_de(id)`: si un id no existe en el corpus (cita falsa o vacia), lo marca.
Como los ids salen del propio corpus, en el camino sano nunca deberian fallar:
el verificador es el candado que lo garantiza y la sonda que lo mide si algun
dia el contrato se rompe (renombrar un tema, un id colado a mano, otro proveedor
de cita). No reescribe ni inventa: la prosa buena sale igual.
"""
from app.core import guia_venta_prosa


def citas_de_meta(meta) -> list[str]:
    """Extrae los ids de prosa citados en el turno. Prefiere
    meta['prosa_citada'] (lo que declara el citador del solver); si no esta, los
    deriva de las llamadas a consultar_guia_venta en tools_called, para que el
    verificador funcione aunque el meta venga de otro camino. Sin duplicados, en
    orden."""
    if not isinstance(meta, dict):
        return []
    ids: list[str] = []
    declarados = meta.get("prosa_citada")
    if isinstance(declarados, (list, tuple)):
        ids = [str(x).strip() for x in declarados if str(x or "").strip()]
    else:
        for tc in meta.get("tools_called") or []:
            if not isinstance(tc, dict) or tc.get("name") != "consultar_guia_venta":
                continue
            res = tc.get("result")
            cid = res.get("id") if isinstance(res, dict) else None
            cid = str(cid).strip() if cid else ""
            if cid:
                ids.append(cid)
    vistos: set[str] = set()
    return [i for i in ids if not (i in vistos or vistos.add(i))]


def verificar_cita(prosa_citada) -> dict:
    """Chequea que cada id citado exista en el corpus jurado con texto_de(id).
    Devuelve {'ok', 'validas', 'invalidas', 'total'}. ok=True si no hay ninguna
    cita invalida; el caso SIN citas tambien es ok (no hay nada falso que
    marcar). Una cita invalida no rompe el turno: se marca para el log."""
    ids = [str(x).strip() for x in (prosa_citada or []) if str(x or "").strip()]
    validas, invalidas = [], []
    for cid in ids:
        destino = validas if guia_venta_prosa.texto_de(cid) is not None else invalidas
        destino.append(cid)
    return {"ok": not invalidas, "validas": validas,
            "invalidas": invalidas, "total": len(ids)}


def verificar_meta(meta) -> dict:
    """Atajo del camino vivo: extrae la cita del meta y la verifica en un paso.
    Suma 'citas' con los ids evaluados."""
    citas = citas_de_meta(meta)
    res = verificar_cita(citas)
    res["citas"] = citas
    return res

"""EL INDICE DE EMBEDDINGS DE LA TIENDA CUBRE LA FUENTE, Y UN DOCUMENTO QUE FALTA NO TUMBA EL TURNO (17-nov-2026).

Visto en vivo el 17-nov con `produccion.py`: el catalogo de Firestore traia "auriculares, caracteristicas extra: con cable",
que el indice no tenia porque se armo con el catalogo del repo; `vectores._punto` dio KeyError y el mensaje entero de las
menos partes chinas quedo sin nexos.

  cubre     todo documento que arman los nexos desde la fuente del repo esta en el indice. Si se edita el catalogo, los
            alias, la FAQ o lo que la tienda no vende sin rehacerlo con `banco_pruebas/flujo/embeddings.py --indice`,
            falla aca.
  falta     un documento que el indice no tiene se pide en el mismo lote que las consultas, como documento, una sola vez
            por proceso, y puntua igual que uno del indice.
"""
import pytest

from app.core.flujo.nuevo import condicion as NC
from app.core.flujo.nuevo import rubro as NR
from app.core.flujo.nuevo import tema as NT
from app.core.flujo.nuevo import vectores as V

TID = "verifika_prod"


def documentos(tid):
    """Los documentos de los cinco nexos, con los mismos constructores que usa `vectores.puntajes`."""
    _, alias, rubros, modelos = NR.fuente(tid)
    out = [d for _, d in NR.indice_rubros(rubros, alias, tid)]
    out += [NR.doc_producto(k, modelos[k], alias) for k in modelos]
    out += [a for _, a in NT.docs(*NT.fuente(tid))]
    fx = NC.Fuente(tid)
    out += [d for r in fx.campos for _, d in NC.docs_campo(r, fx)]
    return list(dict.fromkeys(out))


def test_el_indice_cubre_la_fuente_del_repo(firestore_doble):
    docs = documentos(TID)
    pos = V.indice(TID)[0]
    faltan = [d for d in docs if d not in pos]
    print(f"\n{len(docs)} documentos de los nexos, {len(docs) - len(faltan)} en el indice")
    assert not faltan, (f"{len(faltan)} documentos fuera del indice, rehacerlo con embeddings.py --indice: "
                        f"{faltan[:5]}")


class _Resp:
    def __init__(self, n, vec):
        self.n, self.vec = n, vec

    def raise_for_status(self):
        pass

    def json(self):
        return {"embeddings": [{"values": list(self.vec)} for _ in range(self.n)]}


def test_un_documento_que_falta_se_pide_una_vez_y_puntua(firestore_doble, monkeypatch):
    import app.config
    pos, v, n = V.indice(TID)
    rubro = sorted(NC.fuente(TID).campos)[0]
    real = NC.docs_campo(rubro, NC.fuente(TID))[0]
    nuevo = ("campo|nuevo", f"{rubro}, un campo que el indice no tiene: algo")
    assert real[1] in pos and nuevo[1] not in pos
    vec = v[pos[real[1]] * n:(pos[real[1]] + 1) * n]
    pedidos = []

    def post(url, headers=None, timeout=None, json=None):
        pedidos.append([(r["content"]["parts"][0]["text"], r["taskType"]) for r in json["requests"]])
        return _Resp(len(json["requests"]), vec)

    monkeypatch.setattr(V.httpx, "post", post)
    monkeypatch.setattr(V, "_FALTAN", {})
    monkeypatch.setattr(NC, "docs_campo", lambda r, fx: [real, nuevo])
    monkeypatch.setattr(app.config, "get_settings", lambda: type("S", (), {"GEMINI_API_KEY": "x"})())
    for _ in range(2):
        pts = dict(V.puntajes_condicion(TID, [(rubro, "una consulta")])[NC.VIVA][rubro]["una consulta"])
        assert pts == {"campo|nuevo": pytest.approx(1.0, abs=1e-3), real[0]: pytest.approx(1.0, abs=1e-3)}
    print(f"\nlotes pedidos: {pedidos}")
    assert pedidos[0] == [("una consulta", V.CONSULTA), (nuevo[1], V.DOCUMENTO)]
    assert pedidos[1] == [("una consulta", V.CONSULTA)], "el documento que falta se pide una sola vez por proceso"

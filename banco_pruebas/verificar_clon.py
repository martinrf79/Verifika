"""
VERIFICADOR DEL CLON: compara el banco contra el Firestore REAL de produccion.

El banco solo sirve si prueba lo mismo que va a pasar en WhatsApp. Este script
lo comprueba en vez de suponerlo. Lee Firestore con la cuenta de servicio de
solo lectura (env GCP_SA_KEY_B64, claude-lector) y compara, uno por uno:

  1. La coleccion `config` de la tienda contra fixtures/config_prod.json.
     Ahi vive la tabla de envios: si en la nube cambia una tarifa y el banco no
     se entera, el banco valida numeros que ya no existen.
  2. Los 880 ids de producto contra el CSV del repo.
  3. Los 50 temas de FAQ, id por id y texto por texto, contra faq.json.

Uso:
    python3 banco_pruebas/verificar_clon.py             # compara y reporta
    python3 banco_pruebas/verificar_clon.py --exportar  # refresca el volcado

Sale 0 si el clon es fiel, 1 si derivo. Correlo ANTES de una tanda viva.

LO QUE ESTE SCRIPT NO PUEDE VER, y hay que mirarlo a mano: las variables de
entorno del servicio en Cloud Run (MODO_CIERRE, PROCESAR_EN_REQUEST, que clave
de Gemini tiene montada). La cuenta lectora no tiene permiso `run.services.get`.
`/health` del servicio las reporta; el banner de cada corrida del banco reporta
las suyas. Si las dos listas no coinciden, el banco no es el clon.
"""
import base64
import json
import os
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_RAIZ))

TIENDA = "verifika_prod"
_DATA = _RAIZ / "data" / "clientes" / TIENDA
_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "config_prod.json"


def _credenciales():
    """La clave de solo lectura viaja en GCP_SA_KEY_B64."""
    b64 = os.environ.get("GCP_SA_KEY_B64", "").strip()
    if not b64:
        print("FALTA GCP_SA_KEY_B64: sin la clave lectora no se puede comparar "
              "contra Firestore real.")
        return None, None
    import google.auth
    from google.oauth2 import service_account
    info = json.loads(base64.b64decode(b64))
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/cloud-platform"])
    return creds, info.get("project_id")


def _sesion(creds):
    import google.auth.transport.requests as gt
    import requests
    os.environ.setdefault("REQUESTS_CA_BUNDLE", "/root/.ccr/ca-bundle.crt")
    creds.refresh(gt.Request())
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {creds.token}"})
    return s


def _valor(v):
    """Un valor de Firestore REST a Python plano."""
    k, val = next(iter(v.items()))
    if k == "mapValue":
        return {kk: _valor(vv) for kk, vv in (val.get("fields") or {}).items()}
    if k == "arrayValue":
        return [_valor(x) for x in (val.get("values") or [])]
    if k == "integerValue":
        return int(val)
    if k == "doubleValue":
        return float(val)
    if k == "booleanValue":
        return bool(val)
    if k == "nullValue":
        return None
    return val


def _leer_coleccion(s, base, col, mask=None):
    docs, token = {}, None
    while True:
        params = {"pageSize": 300}
        if mask:
            params["mask.fieldPaths"] = mask
        if token:
            params["pageToken"] = token
        r = s.get(f"{base}/{col}", params=params, timeout=90)
        r.raise_for_status()
        j = r.json()
        for d in j.get("documents", []):
            docs[d["name"].split("/")[-1]] = {
                k: _valor(v) for k, v in (d.get("fields") or {}).items()}
        token = j.get("nextPageToken")
        if not token:
            return docs


def _config_real(s, base) -> dict:
    """La coleccion config, aplanada: cada doc guarda su valor en `value`."""
    crudo = _leer_coleccion(s, base, "config")
    return {k: (v.get("value") if "value" in v else v) for k, v in crudo.items()}


def _config_local() -> dict:
    return dict(json.loads(_FIXTURE.read_text(encoding="utf-8")).get("docs") or {})


def _productos_repo() -> set:
    import csv
    with open(_DATA / "productos.csv", encoding="utf-8") as f:
        return {(row.get("id") or "").strip() for row in csv.DictReader(f)
                if (row.get("id") or "").strip()}


def _faq_repo() -> dict:
    data = json.loads((_DATA / "faq.json").read_text(encoding="utf-8"))
    return {t["tema"]: t for t in data if t.get("tema")}


def _comparar_config(real: dict, local: dict) -> list:
    difs = []
    for k in sorted(set(real) | set(local)):
        if k not in local:
            difs.append(f"config: la nube tiene '{k}' y el banco no")
        elif k not in real:
            difs.append(f"config: el banco inventa '{k}', en la nube no existe")
        elif real[k] != local[k]:
            difs.append(f"config '{k}': nube {json.dumps(real[k], ensure_ascii=False)[:200]} "
                        f"!= banco {json.dumps(local[k], ensure_ascii=False)[:200]}")
    return difs


def _comparar_faq(real: dict, repo: dict) -> list:
    difs = []
    faltan = set(real) - set(repo)
    sobran = set(repo) - set(real)
    if faltan:
        difs.append(f"FAQ: {len(faltan)} temas en la nube que no estan en el repo: "
                    f"{sorted(faltan)[:6]}")
    if sobran:
        difs.append(f"FAQ: {len(sobran)} temas en el repo que no estan en la nube: "
                    f"{sorted(sobran)[:6]}")
    for tema in sorted(set(real) & set(repo)):
        a = (real[tema].get("respuesta") or "").strip()
        b = (repo[tema].get("respuesta") or "").strip()
        if a != b:
            difs.append(f"FAQ '{tema}': la respuesta difiere entre nube y repo")
    return difs


def main() -> int:
    exportar = "--exportar" in sys.argv
    creds, proj = _credenciales()
    if not creds:
        return 1
    s = _sesion(creds)
    base = (f"https://firestore.googleapis.com/v1/projects/{proj}"
            f"/databases/(default)/documents/tiendas/{TIENDA}")

    real_cfg = _config_real(s, base)
    if exportar:
        _FIXTURE.write_text(json.dumps(
            {"exportado_de": f"Firestore real: tiendas/{TIENDA}/config",
             "exportado_el": __import__("datetime").date.today().isoformat(),
             "como_se_actualiza": "python3 banco_pruebas/verificar_clon.py --exportar",
             "docs": real_cfg}, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
            encoding="utf-8")
        print(f"volcado actualizado: {_FIXTURE} ({len(real_cfg)} docs)")
        return 0

    difs = _comparar_config(real_cfg, _config_local())

    ids_nube = set(_leer_coleccion(s, base, "productos", mask="__name__"))
    ids_repo = _productos_repo()
    print(f"productos: nube {len(ids_nube)}, repo {len(ids_repo)}")
    if ids_nube != ids_repo:
        solo_nube = sorted(ids_nube - ids_repo)[:8]
        solo_repo = sorted(ids_repo - ids_nube)[:8]
        difs.append(f"productos: {len(ids_nube - ids_repo)} solo en la nube "
                    f"{solo_nube}, {len(ids_repo - ids_nube)} solo en el repo "
                    f"{solo_repo}")

    faq_nube = _leer_coleccion(s, base, "faq")
    faq_repo = _faq_repo()
    print(f"FAQ: nube {len(faq_nube)}, repo {len(faq_repo)}")
    difs += _comparar_faq(faq_nube, faq_repo)

    print(f"config: nube {sorted(real_cfg)}, banco {sorted(_config_local())}")
    print()
    if difs:
        print(f"CLON DERIVADO — {len(difs)} diferencia(s):")
        for d in difs:
            print(f"  - {d}")
        print("\nArreglalo antes de correr una tanda: el banco esta probando "
              "una tienda que no existe.")
        return 1
    print("CLON FIEL: config, catalogo y FAQ del banco == produccion.")
    print("NO verificable desde aca (hace falta mirar /health del servicio): "
          "las envs de Cloud Run, MODO_CIERRE y que clave de Gemini corre.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

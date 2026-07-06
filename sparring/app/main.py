"""Sparring — el gimnasio de ventas. API + UI.

Correr local:  uvicorn app.main:app --port 8090  (desde sparring/)
"""
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import cliente, juez
from .personas import PERSONAS, publica

MAX_TURNOS_VENDEDOR = 12

app = FastAPI(title="Sparring")
_sesiones: dict[str, dict] = {}

_STATIC = Path(__file__).resolve().parent.parent / "static"


class NuevaSesion(BaseModel):
    persona_id: str


class Mensaje(BaseModel):
    sesion_id: str
    texto: str


class PedidoReporte(BaseModel):
    sesion_id: str


@app.get("/")
def index():
    return FileResponse(_STATIC / "index.html")


@app.get("/api/personas")
def listar_personas():
    return [publica(p) for p in PERSONAS.values()]


@app.post("/api/sesion")
def crear_sesion(body: NuevaSesion):
    persona = PERSONAS.get(body.persona_id)
    if not persona:
        raise HTTPException(404, "persona inexistente")
    sesion_id = uuid.uuid4().hex[:12]
    _sesiones[sesion_id] = {
        "persona": persona,
        "historial": [{"rol": "cliente", "texto": persona["apertura"]}],
        "estados": [],
        "resultado": "en_curso",
    }
    return {
        "sesion_id": sesion_id,
        "persona": publica(persona),
        "apertura": persona["apertura"],
        "max_turnos": MAX_TURNOS_VENDEDOR,
    }


@app.post("/api/mensaje")
def mensaje(body: Mensaje):
    s = _sesiones.get(body.sesion_id)
    if not s:
        raise HTTPException(404, "sesión inexistente")
    if s["resultado"] != "en_curso":
        raise HTTPException(409, "la partida ya terminó")

    s["historial"].append({"rol": "vendedor", "texto": body.texto.strip()})
    turno = sum(1 for m in s["historial"] if m["rol"] == "vendedor")

    interes_actual = (
        s["estados"][-1]["interes"] if s["estados"] else cliente.INTERES_INICIAL
    )
    r = cliente.responder(s["persona"], s["historial"], interes_actual)
    s["historial"].append({"rol": "cliente", "texto": r["mensaje"]})
    s["estados"].append(
        {"turno": turno, "interes": r["interes"], "nota_interna": r["nota_interna"]}
    )

    if r["decision"] in ("compra", "avanza", "se_va"):
        s["resultado"] = r["decision"]
    elif turno >= MAX_TURNOS_VENDEDOR:
        s["resultado"] = "se_enfrio"

    return {
        "mensaje": r["mensaje"],
        "terminado": s["resultado"] != "en_curso",
        "resultado": s["resultado"],
        "turno": turno,
        "max_turnos": MAX_TURNOS_VENDEDOR,
    }


@app.post("/api/reporte")
def reporte(body: PedidoReporte):
    s = _sesiones.get(body.sesion_id)
    if not s:
        raise HTTPException(404, "sesión inexistente")
    resultado = s["resultado"] if s["resultado"] != "en_curso" else "abandonada"
    rep = juez.evaluar(s["persona"], s["historial"], s["estados"], resultado)
    rep["persona"] = publica(s["persona"])
    rep["historial"] = s["historial"]
    return rep

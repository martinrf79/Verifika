"""EL CATALOGO CONSULTADO CON SQL — 5-nov-2026, decidido con Martin.

Se midio aca, instalado sobre el agente solo en el banco, y desde el 5-nov esta en el bot: `app/core/flujo/tabla.py` y el
`buscar` de `agente.py`. Lo que queda es la entrada para verlo y para correr las 42 charlas reales con el bot de hoy.
Las corridas medidas: `corrida_sql_r1.jsonl`, `corrida_sql_r2.jsonl`, calificadas a mano en la FICHA 87.

    python3 banco_pruebas/examen_real/sql.py --mapa                          lo que lee el modelo
    python3 banco_pruebas/examen_real/sql.py --probar "SELECT ..."           una consulta, sin modelo
    python3 banco_pruebas/examen_real/sql.py --correr <etiqueta> [id ...]    las 42 charlas con la gratis
"""
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(AQUI)))

if __name__ == "__main__":
    a = sys.argv[1:]
    from banco_pruebas import clon_produccion as C
    if a[:1] in (["--mapa"], ["--probar"]):
        C.instalar()
        from app.core.flujo import tabla as T
        print(T.mapa(C.TIENDA) if a[0] == "--mapa" else T.consultar(a[1], C.TIENDA))
    elif a[:1] == ["--correr"]:
        from banco_pruebas.examen_real import examen
        examen.correr(os.path.join(AQUI, f"corrida_sql_{a[1]}.jsonl"), a[2:])

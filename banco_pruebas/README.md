# EL BANCO — cómo se mide Verifika

Si un documento viejo dice otra cosa, manda este. El camino vivo es el
agente: `respuesta.procesar_turno` sobre `agente.turno`.

**Ninguna sesión declara verde sin un número de una charla real**, y el
número se reporta con su control al lado.

## Lo que se corre hoy

| Qué querés | Comando |
| --- | --- |
| Batería offline, sin LLM | `python3 -m pytest -q` |
| Charlas reales de Cloud Run | `python3 banco_pruebas/produccion.py --desde 6h` |
| Una mejora contra la base | `python3 -m banco_pruebas.puerta` |
| La vara de las 58 | `python3 banco_pruebas/vara_58.py` |
| Un turno por dentro | `python3 banco_pruebas/sonda_turno.py` |
| Puntas sueltas del cableado | `python3 banco_pruebas/censo_cableado.py` |

Toda mejora pasa por `puerta.py` (ficha 63): no se toca la vara mientras
se trabaja, un arreglo por vez, tres tandas, y si rompe una charla que
estaba bien se revierte.

## Lo que ya no se corre

`las_40.py`, `mapa.py`, `oro.py` y los tests de casetes se apagaron. Están
en `archivo/`. No se reenchufan.

Esta carpeta no deploya y no entra a la imagen de Cloud Run.

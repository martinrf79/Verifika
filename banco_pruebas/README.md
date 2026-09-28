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

## La interpretación y la respuesta: UN solo banco

Es el único que mide lo que el modelo entiende. No se arma otro: si falta
un caso, se suma a la vara de las 58 y a sus piezas.

- **Las charlas**: `vara_58.json`, con las casillas de la respuesta.
- **Las piezas correctas** de cada charla: `desmenuzar.CASOS`.
- **Quién corre**: `sonda_charlas.py`, por el clon de producción.
- **Quién califica la interpretación**: `pedido_agente.nota_piezas`.
- **Quién juzga una mejora**: `puerta.py`, charla por charla.
- **Lo guardado**: `sonda_charlas_corridas.jsonl`, una etiqueta por corrida.

El procedimiento:

1. Base: tres corridas del código de hoy, con etiquetas `v58_base_1`, `_2`, `_3`.
2. El cambio, con su test offline primero, en su propio commit.
3. Tres corridas del cambio: `v58_cambio_1`, `_2`, `_3`.
4. `python3 -m banco_pruebas.puerta --base v58_base --cambio v58_cambio --busca C56`

```
python3 -m banco_pruebas.sonda_charlas --etiqueta v58_base_1
```

Por el clon va de a una charla; las tres corridas se pueden lanzar en
paralelo como procesos aparte. Con la clave gratis se traba por el límite
por minuto; la paga necesita la orden de Martín en la sesión y la marca
`MARTIN_AUTORIZO_LA_PAGA=<fecha>` en el comando, lo exige el candado.

Lo que se lee de producción, aparte: `leer_interpretacion.py` y
`produccion.py`.

## Lo que ya no se corre

`las_40.py`, `mapa.py`, `oro.py` y los tests de casetes se apagaron. Están
en `archivo/`. No se reenchufan.

Los bancos viejos de interpretación salieron el 28-sep a
`archivo/banco_interpretacion_28sep/`: `interpretacion.py`,
`tanda_charlas.py` con las `vara_charlas*.json`, `puerta_determinista.py` e
`interprete_viejo/`. Cada uno tenía sus propios casos y su propio número.

Esta carpeta no deploya y no entra a la imagen de Cloud Run.

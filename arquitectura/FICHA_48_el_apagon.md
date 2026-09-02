# FICHA 48 — El primer apagón. Las seis puertas y el termómetro.

Una sesión. No se borra. Snapshot en `archivo/`, el vivo deja de
cargarlos como camino. Si el piso de las 15 charlas baja, revert.

## Qué se apaga

**Las seis puertas viejas de `herramientas.py`.** No eran alias: eran
el cuerpo. `_CUERPOS` ya tenía cuatro; `consultar_productos` y `cotizar`
delegaban a las seis. Ahora las seis son helpers privados
(`_lista`, `_catalogo`, `_ficha_por_id`, `_compatibilidad`, `_envio`,
`_presupuesto`). El vivo entra por las cuatro. Tests y banco siguen
llamando los nombres viejos: son el mismo helper, no otra lógica.

**El termómetro de invariantes.** El vivo usaba dos cosas:
`_RE_ITEM` y `pago_parcial`. El resto —`revisar`, `revisar_charla` y
las reglas— no muta el mensaje desde la FICHA 35. Sale de `app/`.
Queda en `banco_pruebas/invariantes.py`. El cobro sigue leyendo
`pago_parcial` de `app/`, porque el Dockerfile no copia el banco.

## Qué no se toca

Certificación, filtros, calculadora, índice, las cuatro puertas de
salida, `componer`. Las reglas de `componer` que el corpus no
despierta. Las piezas 0/54. FICHA 46 y 47.

## Cómo se verifica

La batería offline, incluido el piso de casetes. `test_archivo.py`
exige fila por snapshot. `app/` no importa `archivo/`.

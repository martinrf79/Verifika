# arquitectura/ — la orden de trabajo

**Esta carpeta es lo único que hace falta leer para trabajar.** La ficha
abierta es `FICHA_63_la_puerta_de_las_mejoras.md`. Las cerradas (30 a 58) y
los planes viejos están en `archivo/fichas_cerradas/`.

## Qué hay acá

| archivo | qué es |
|---|---|
| `README.md` | esta puerta |
| `FICHA_63_la_puerta_de_las_mejoras.md` | **la orden abierta**: cómo entra cada mejora |
| `FICHA_62_el_agente.md` | el modelo busca solo |
| `FICHA_61_desmenuzar_y_traducir.md` | cómo se parte el pedido, medida |
| `FICHA_60_las_58_por_tres_caminos.md` | la vara de las 58 |
| `FICHA_59_lo_que_el_modelo_puede.md` | qué puede el modelo, antes de diseñar |
| `MAPA_CABLEADO.md` | nombres históricos T/J/L/D. El camino vivo ya no es ese |

## El camino vivo, en una línea

`orchestrator` → `respuesta.procesar_turno` → `agente.turno` sobre
`motor.buscar`. Identidad, plata y tarifas las certifica el código.

## Quién escribe qué

```
EL DISEÑO     escribe .md y tests/. Nunca toca app/.
LA INGENIERÍA escribe app/. No reescribe la vara para que pase.
MARTÍN        aprueba el push, que es lo que deploya.
```

Verde no es lo mismo que funciona. Un test prueba lo que afirma, no que el
bot venda bien.

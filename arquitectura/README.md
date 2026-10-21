# arquitectura/ — la orden de trabajo

**Las fichas de diseño, de la 59 en adelante.** Cuál está abierta lo dice `PENDIENTE.md`; el plan,
`CLAUDE.md`; el método de la puerta es la 63. Las cerradas (30 a 58) y
los planes viejos están en `archivo/fichas_cerradas/`.

## Qué hay acá

| archivo | qué es |
|---|---|
| `README.md` | esta puerta |
| `FICHA_73_los_avisos.md` | los avisos: la información justa solo donde falla, 521 de 525 en el banco |
| `FICHA_70_la_traduccion_caso_por_caso.md` | la traducción caso por caso antes del código, la versión 3 |
| `FICHA_69_lo_que_recibe_el_interprete.md` | lo que recibe el intérprete en producción, medido |
| `FICHA_68_la_ficha_de_la_charla.md` | el estado de la charla escrito por el código |
| `FICHA_67_el_desmenuzado.md` | el desmenuzado y las 58 como ejemplos resueltos |
| `FICHA_66_la_red.md` | la red |
| `FICHA_65_el_tablero_y_la_biblioteca.md` | el tablero |
| `FICHA_64_la_interpretacion_robusta.md` | la interpretación, medida |
| `FICHA_63_la_puerta_de_las_mejoras.md` | el método: cómo entra cada mejora |
| `FICHA_62_el_agente.md` | el modelo busca solo |
| `FICHA_61_desmenuzar_y_traducir.md` | cómo se parte el pedido, medida |
| `FICHA_60_las_58_por_tres_caminos.md` | la vara de las 58 |
| `FICHA_59_lo_que_el_modelo_puede.md` | qué puede el modelo, antes de diseñar |
| `MAPA_CABLEADO.md` | histórico: sólo valen sus números `D`. El camino vivo lo nombra `MAPA.md` |

## El camino vivo, en una línea

`orchestrator` → `respuesta.procesar_turno` → `tablero.turno`, con las
herramientas de `agente` sobre `motor.buscar`. Identidad, plata y tarifas las certifica el código.

## Quién escribe qué

```
EL DISEÑO     escribe .md y tests/. Nunca toca app/.
LA INGENIERÍA escribe app/. No reescribe la vara para que pase.
MARTÍN        aprueba el push, que es lo que deploya.
```

Verde no es lo mismo que funciona. Un test prueba lo que afirma, no que el
bot venda bien.

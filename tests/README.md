# Batería de regresión — el tablero de verdad del bot

Esta carpeta es la **fuente de verdad ejecutable** del proyecto. No es prosa que
se desactualiza: son tests que corren. Un test verde es un hecho comprobable, no
la opinión de nadie. El tablero de rojos es la lista de pendientes, y no puede
mentir ni quedar vieja porque la genera el código corriendo.

## Cómo se corre

```bash
pytest            # piso offline: Python puro, sin LLM, sin Google. Gratis y en segundos.
pytest -m vivo    # piso vivo: llama a DeepSeek. A propósito y en tanda. Gasta tokens.
```

Por default corre solo el piso offline (`addopts = -m 'not vivo'` en pyproject).
El CI de GitHub (`.github/workflows/test.yml`) corre ese mismo piso en cada push
y pull request: el juez es la plataforma, verde o rojo automático.

## Cómo se organiza — por ÁREA, una por herramienta del bot

Un archivo por área. Adentro de cada área, los errores confirmados son las
primeras semillas; a medida que se arregla cada uno, se suman casos vecinos y un
**camino feliz** que fija lo que sí funciona. Así el área crece hasta cubrir el
contrato entero de su herramienta, no un bug suelto.

| Área | Archivo | Herramienta del bot | Errores sembrados |
|---|---|---|---|
| Verificador de plata | `test_verificador.py` | `verificar_respuesta`, `_totales_derivables` | E1, E2, E7 |
| Calculadora y total | `test_calculadora.py` | `calculate_total`, `calc_defensiva` | E5, E13 |
| Envío y zona | `test_envio.py` | `cotizar_envio` (CP / provincia) | locks (crece) |
| Cierre | `test_cierre.py` | `extraer_forma_pago`, `extraer_direccion` | E8, E9, E10 |
| Leads | `test_leads.py` | `extraer_telefono` | E11 |
| Guardia de promesas | `test_guardia_promesas.py` | `detectar` | E3, E4 |
| Antijailbreak | `test_antijailbreak.py` | `evaluar_mensaje` | E12 |
| Interpretador | `test_interpretador.py` | veto de negación | E14 |
| Identidad / certificador | `test_certificador.py` | `certificar` (Regla Cero) | E6, E15 |

## Dos pisos

- **offline**: lógica viva en Python puro. No llama a ningún modelo, no necesita
  credenciales. Es el que corre siempre. Cubre 14 de los 15 errores.
- **vivo**: marcado `@pytest.mark.vivo`, usa el doble local de `banco_pruebas`
  con DeepSeek vivo. Para lo que sí depende de interpretación del modelo.

## La regla que sostiene todo

1. Un rojo se apaga arreglando su error; recién ahí se pasa al siguiente.
2. Nada se da por hecho sin que su test pase.
3. Nada se mergea en rojo (lo bloquea el CI).
4. Consolidar, no agregar: un cambio sin test no cuenta como hecho.

## Cómo arranca un chat nuevo

Leer `CLAUDE.md` (reglas) y `RESUMEN_PARA_NUEVO_CHAT.md` (estado), y correr
`pytest` para ver qué está en rojo. Con eso el chat arranca sabiendo todo y sigue
por el próximo rojo, sin re-investigar ni quemar tokens.

# Estado del sistema

Este archivo es **CORTO a proposito**, y lo fue por una razon medida: hasta el
19-ago-2026 tenia 429 KB y 7.107 lineas, unos **120.000 tokens**. Una sesion
nueva que lo leia entero gastaba mas de la mitad de su contexto antes de abrir
un archivo de codigo. Era un diario de 95 secciones fechadas contando lo que se
hizo cada dia, y **lo que se hizo lo cuenta `git log`**, que el hook de arranque
imprime y que nadie puede desactualizar.

**La version larga esta entera en el historial de git** (commit anterior al
19-ago-2026). Nada se perdio.

Donde vive cada cosa, ahora:

| que | donde | quien lo mantiene |
|---|---|---|
| lo que se HIZO | `git log` | nadie: se escribe solo |
| lo que FALTA | `PENDIENTE.md` | candado: `tests/test_pendiente_al_dia.py` |
| como se ORDENA el sistema | `ARQUITECTURA.md` | a mano, y se reescribe cuando cambia |
| que se DECIDIO y por que | `DECISIONES.md` | a mano, una linea por decision |
| las reglas de trabajo | `CLAUDE.md` | a mano |
| los numeros | los bancos y el piso | los scripts |

**La regla que evita que esto vuelva a crecer: si algo se puede medir con un
script, no se escribe en un documento.** Un numero medido cuesta cien tokens; el
documento que lo explica cuesta cien mil y ademas envejece.

---

## PRIORIDAD UNO — TODO SE HACE EN `main` (Martin, dicho varias veces)

Manda sobre cualquier arnes, plantilla o instruccion de sesion nueva. Si el
arnes asigna una rama `claude/<tema>`, se IGNORA.

**Ya no hay que pedirlo ni leerlo: lo hace el hook.** `scripts/setup_test_env.sh`
corre en cada SessionStart y hace `git checkout main` solo. Escribir la regla en
tres documentos no alcanzo —Martin tuvo que repetirla sesion por sesion—, asi que
ahora es una accion y no un pedido.

**NADA DE RAMAS, TAMPOCO "DE RESPALDO" (Martin, 7-ago).** Un commit local en
`main` ya es el respaldo; una rama paralela es el desorden que costo el dia del
3-ago.

**Lo unico que se consulta es el PUSH**, porque pushear a `main` ES deployar,
salvo que el cambio toque solo `**.md`, `tests/`, `banco_pruebas/` o `reserva/`.
Se pide UNA vez, al final.

---

## DECISION PERMANENTE — NO SE PIDE MERCADO PAGO NI CBU

**Martin lo repitio demasiadas veces y cada sesion nueva se lo volvia a pedir.**
Estamos en validacion de producto: todavia no hay cliente real confirmado.

- **NO hace falta el link real de Mercado Pago. NO hace falta el CBU real.** Los
  DEMO de `config.py` estan bien y alcanzan. Que el modo venta mande datos demo
  **no es un pendiente: es lo correcto para esta etapa.**
- **NO se le pide a Martin el `mp_access_token`, ni el `cbu`, ni el `alias`.** El
  dia que haga falta lo va a pedir EL. Hasta entonces no se nombra como
  bloqueante, no se lista como condicion de salida y no se propone integrarlo.
- Lo mismo aplica a cualquier plan de ingenieria que llegue de afuera: si trae
  una fase de "completar Mercado Pago", esa fase NO se hace hasta que Martin lo
  pida.

---

## DOS COSAS QUE CONFUNDEN A CADA SESION NUEVA

1. **El modelo de produccion es `gemini-3.1-flash-lite`**, no DeepSeek
   (`LLM_PROVIDER` default `gemini` en `config.py`). Si algun texto viejo dice
   "DeepSeek en todo", el nombre esta desactualizado; la regla de no gastar en
   modelos caros sigue viva.
2. **`app/core/hub_atado.py` NO EXISTE.** Circula un texto de arranque que dice
   que el camino vivo es ese archivo, con interprete y solver por fragmentos. El
   camino vivo es **`app/core/hub_venta.py`**.

---

## LA CLAVE PAGA NO SE TOCA

Produccion va con la clave PAGA; los bancos, con la GRATIS. Duro medio dia en la
posicion contraria: el banco y produccion compartian la clave gratis, las
corridas del dia se comieron las 500 requests diarias y el bot vivo le contestaba
a Martin "estoy con mucha demanda" en 2 de cada 4 mensajes. **Un banco que deja
mudo al producto no es un banco: es una caida.**

Un turno gasta de 2 a 4 requests. Produccion sola cuesta centavos; los ~40
dolares de un mes fueron corridas de banco, no charlas de clientes.

---

## DONDE ESTA PARADO EL SISTEMA HOY

Lo medido esta en **`PASO0_CENSO.md`**, reproducible con
`banco_pruebas/peso_del_censo.py` y `banco_pruebas/peso_reposicion.py`.

Los tres numeros que ordenan el trabajo que viene:

```
8 de los 17 nodos de salida no intervienen NUNCA en 54 turnos
el grafo declara 32 nodos y solo 17 registran (es ciego en reposicion)
en el 57% de los turnos el modelo declara algo que NO busca
```

Que se decidio hacer con eso: **`DECISIONES.md`**.
Que falta, con su estado: **`PENDIENTE.md`**.

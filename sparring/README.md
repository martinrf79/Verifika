# 🥊 Sparring — el gimnasio de ventas

Producto digital independiente, creado el 6-jul-2026. NO es parte de Verifika:
vive acá temporalmente y debe moverse a su propio repo antes de comercializar.

## Qué es

Un simulador donde los vendedores entrenan por chat contra clientes difíciles
actuados por IA. Cada cliente tiene una **condición oculta de compra**: solo
compra si el vendedor hace lo correcto. Al terminar, un juez entrega un
**veredicto con puntaje y evidencia**: cada dimensión citada con la frase
textual del vendedor que la justifica, el turno exacto donde se cayó la venta
con lo que pensó el cliente en ese momento, y un único consejo accionable.

El puntaje final lo arma el código con una fórmula fija más señales duras
deterministas: descuento regalado, cero preguntas, muros de texto. El LLM
opina; el código decide y explica.

## Por qué es negocio

- Comprador: dueños y jefes de venta de pymes LatAm cuyos vendedores venden
  por WhatsApp: concesionarias, inmobiliarias, corredores de seguros, retail.
- Dolor: la venta se pierde en el chat y nadie entrena eso. Los simuladores
  de roleplay con IA ya son una categoría probada en inglés y B2B caro;
  en español rioplatense y a precio pyme, no existe.
- Ticket medio: diagnóstico del equipo por única vez (todo el equipo juega
  las 3 personas, el dueño recibe el ranking con veredictos) más abono
  mensual de gimnasio: personas nuevas por rubro, torneos, seguimiento.
- Se vende solo: demo pública jugable con resultado compartible
  ("le vendí a Marta 78/100, ¿podés vos?").

## Correr local

```bash
cd sparring
pip install fastapi uvicorn openai
export DEEPSEEK_API_KEY=...
uvicorn app.main:app --port 8090
# abrir http://localhost:8090
```

Demo por consola sin servidor: `python demo.py` (imprime la partida y guarda
`demo_veredicto.json`).

## Estructura

- `app/personas.py` — clientes difíciles con condición oculta y gatillos de fuga
- `app/cliente.py` — motor del cliente simulado (DeepSeek, estado interno por turno)
- `app/juez.py` — veredicto: dimensiones LLM con evidencia + señales duras + fórmula en código
- `app/main.py` — API FastAPI y sesiones
- `static/index.html` — UI completa: lobby, chat, veredicto
- `demo.py` — partida real de punta a punta por consola

## Pendiente para cobrar (en orden)

1. Deploy en Cloud Run como servicio propio, separado de agente-bot.
2. Página de venta con la demo pública y checkout de Mercado Pago.
3. Modo equipo: código de invitación, ranking del equipo, reporte del dueño.
4. Personas por rubro del cliente (se generan con una plantilla, no a mano).

"""
SMOKE TEST de Verifika — valida que el pipeline funcione antes de activarlo
en producción.

Ejecutar:
    python -m tests.smoke_verifika

Requiere:
    DEEPSEEK_API_KEY configurada en el entorno.

NO requiere Firestore: usa evidencia mockeada in-memory.
"""
import os
import sys
import asyncio

# Permitir correr desde la raíz del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_llm_adapter():
    """Test 1: el adaptador llama a DeepSeek y devuelve algo."""
    from app.verifika.llm_adapter import llm_complete, list_roles_config

    print("\n=== TEST 1: LLM Adapter ===")
    config = list_roles_config()
    print(f"Configuración de roles: {config}")

    result = llm_complete(
        messages=[{"role": "user", "content": "Decí solamente 'hola'"}],
        role="solver",
        temperature=0.0,
        max_tokens=20,
    )
    print(f"Provider: {result['provider']}")
    print(f"Model: {result['model']}")
    print(f"Respuesta: {result['content']}")
    assert result["content"], "Respuesta vacía"
    print("✓ Adaptador funciona\n")


def test_proposer():
    """Test 2: el Proposer descompone correctamente."""
    from app.verifika.proposer import propose_claims

    print("=== TEST 2: Proposer ===")
    texto = "Tenemos el monitor Samsung G7 a $280.000 con stock disponible."
    afirmaciones = propose_claims(texto, trace_id="smoke-1")
    print(f"Texto: {texto}")
    print(f"Afirmaciones extraídas: {afirmaciones}")
    assert len(afirmaciones) >= 1, "Debería extraer al menos 1 afirmación"
    print("✓ Proposer funciona\n")


def test_checker():
    """Test 3: el Checker valida contra evidencia."""
    from app.verifika.checker import check_claims

    print("=== TEST 3: Checker ===")
    afirmaciones = [
        {"id": "a1", "texto": "El monitor Samsung G7 cuesta 280000 pesos", "tipo": "precio"},
        {"id": "a2", "texto": "El teclado Razer Huntsman cuesta 999999 pesos", "tipo": "precio"},
    ]
    evidence = [
        {
            "tipo": "producto",
            "id": "MON-001",
            "nombre": "Monitor Samsung G7",
            "categoria": "monitores",
            "precio_ars": 280000,
            "stock": 5,
            "descripcion": "Monitor curvo gamer 27 pulgadas",
        },
    ]
    veredictos = check_claims(afirmaciones, evidence, trace_id="smoke-2")
    print(f"Veredictos: {veredictos}")
    assert len(veredictos) == 2, "Debería devolver 2 veredictos"
    # La primera debería estar soportada, la segunda contradicha o sin evidencia
    v_a1 = next(v for v in veredictos if v["id"] == "a1")
    v_a2 = next(v for v in veredictos if v["id"] == "a2")
    print(f"a1 (precio correcto): {v_a1['veredicto']}")
    print(f"a2 (precio inventado): {v_a2['veredicto']}")
    assert v_a1["veredicto"] == "soportada", \
        f"a1 debería ser 'soportada', fue '{v_a1['veredicto']}'"
    assert v_a2["veredicto"] in ("contradicha", "sin_evidencia"), \
        f"a2 debería ser 'contradicha' o 'sin_evidencia', fue '{v_a2['veredicto']}'"
    print("✓ Checker funciona\n")


def test_pipeline_completo():
    """Test 4: pipeline completo Proposer → Checker → Router."""
    from app.verifika.pipeline import verify_response

    print("=== TEST 4: Pipeline completo ===")

    # Caso A: respuesta correcta
    print("\n-- Caso A: respuesta correcta --")
    evidence = [
        {
            "tipo": "producto",
            "id": "MON-001",
            "nombre": "Monitor Samsung G7",
            "categoria": "monitores",
            "precio_ars": 280000,
            "stock": 5,
            "descripcion": "Monitor curvo gamer 27 pulgadas",
        },
    ]
    resultado_a = verify_response(
        respuesta_solver="Tenemos el Monitor Samsung G7 a $280.000 con stock.",
        evidence=evidence,
        trace_id="smoke-4a",
    )
    print(f"Acción: {resultado_a['accion']}")
    print(f"Score: {resultado_a['confianza']['score']}")
    print(f"Respuesta final: {resultado_a['respuesta_final']}")

    # Caso B: respuesta con precio inventado
    print("\n-- Caso B: respuesta con precio inventado --")
    resultado_b = verify_response(
        respuesta_solver="Tenemos el Monitor Samsung G7 a $99.000.",
        evidence=evidence,
        trace_id="smoke-4b",
    )
    print(f"Acción: {resultado_b['accion']}")
    print(f"Score: {resultado_b['confianza']['score']}")
    print(f"Respuesta final: {resultado_b['respuesta_final']}")
    assert resultado_b["accion"] == "bloquear", \
        "Una respuesta con precio inventado debería bloquearse"

    # Caso C: saludo (sin afirmaciones verificables)
    print("\n-- Caso C: saludo --")
    resultado_c = verify_response(
        respuesta_solver="¡Hola! ¿En qué te puedo ayudar?",
        evidence=evidence,
        trace_id="smoke-4c",
    )
    print(f"Acción: {resultado_c['accion']}")
    print(f"Afirmaciones: {len(resultado_c['afirmaciones'])}")
    assert resultado_c["accion"] == "responder", "Un saludo debería pasar"

    print("\n✓ Pipeline completo funciona\n")


def main():
    if not os.getenv("DEEPSEEK_API_KEY"):
        print("ERROR: DEEPSEEK_API_KEY no configurada en el entorno")
        sys.exit(1)

    try:
        test_llm_adapter()
        test_proposer()
        test_checker()
        test_pipeline_completo()
        print("=" * 60)
        print("TODOS LOS TESTS PASARON ✓")
        print("=" * 60)
        print("\nProximo paso: activar Verifika con USE_VERIFIKA=true")
        print("y testear con un cliente real en Telegram.")
    except AssertionError as e:
        print(f"\n✗ TEST FALLÓ: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ ERROR INESPERADO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

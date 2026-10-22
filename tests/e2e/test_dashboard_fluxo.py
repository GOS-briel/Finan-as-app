# Fluxos completos até o dashboard (Etapa 10)
# - Com a fatura real: pulado sem FATURA_PDF_PATH (CI)
# - Fluxo manual: roda sempre, inclusive no CI
import pytest

TOTAL_FATURA = 1699.21


@pytest.fixture
def outubro_importado(importar, fatura_teste, cliente_flask):
    """Fatura real importada; devolve os lançamentos de outubro."""
    importar(fatura_teste)
    return cliente_flask.get("/lancamentos?mes=10&ano=2026").get_json()


def _dash(cliente):
    return cliente.get("/dashboard?mes=10&ano=2026").get_json()


def test_dashboard_da_fatura_real(cliente_flask, outubro_importado):
    """Total 1699.21, tudo em 'Sem categoria', sem tetos: hero sem_teto, últimos 3 por id."""
    corpo = _dash(cliente_flask)
    assert corpo["hero"]["total_gasto"] == TOTAL_FATURA and corpo["hero"]["status"] == "sem_teto"
    assert (corpo["quantidade_sem_categoria"], corpo["valor_sem_categoria"]) == (23, TOTAL_FATURA)
    assert [u["id"] for u in corpo["ultimos_lancamentos"]] == sorted((l["id"] for l in outubro_importado), reverse=True)[:3]


def test_categorizar_a_fatura_inteira_zera_sem_categoria(cliente_flask, outubro_importado, categorias_popular):
    """Categorizando DECATHLON (66.66) e depois o resto: 22 → 0 sem categoria; total não muda."""
    decathlon = next(l for l in outubro_importado if l["descricao"].startswith("DECATHLON"))
    cliente_flask.post(f"/lancamentos/{decathlon['id']}/categorizar", json={"subcategoria_id": categorias_popular["Equipamento"]})
    corpo = _dash(cliente_flask)
    assert (corpo["quantidade_sem_categoria"], corpo["valor_sem_categoria"]) == (22, 1632.55)
    for lancamento in outubro_importado:
        if lancamento["id"] != decathlon["id"]:
            cliente_flask.put(f"/lancamentos/{lancamento['id']}", json={"subcategoria_id": categorias_popular["Mercado"]})
    corpo = _dash(cliente_flask)
    assert corpo["quantidade_sem_categoria"] == 0 and corpo["categorias"][-1]["gasto"] == 0
    assert corpo["hero"]["total_gasto"] == TOTAL_FATURA


def test_fluxo_manual_completo_ate_o_dashboard(cliente_flask):
    """Sem PDF: cria subs, define tetos, lança, categoriza com aprendizado e lê o dashboard."""
    mercado = cliente_flask.post("/subcategorias", json={"nome": "Mercado", "categoria_macro_id": 1}).get_json()["id"]
    cinema = cliente_flask.post("/subcategorias", json={"nome": "Cinema", "categoria_macro_id": 2}).get_json()["id"]
    cliente_flask.put("/tetos", json={"categoria_macro_id": 1, "mes": 9, "ano": 2026, "valor": 500})
    cliente_flask.put("/tetos", json={"categoria_macro_id": 2, "mes": 10, "ano": 2026, "valor": 100})

    feira = cliente_flask.post("/lancamentos", json={"data": "2026-10-10", "descricao": "Feira Livre", "valor": 420}).get_json()
    cliente_flask.post(f"/lancamentos/{feira['id']}/categorizar", json={"subcategoria_id": mercado})
    cliente_flask.post("/lancamentos", json={"data": "2026-10-20", "descricao": "Cinema", "valor": 30, "subcategoria_id": cinema})
    outra_feira = cliente_flask.post("/lancamentos", json={"data": "2026-10-21", "descricao": "FEIRA LIVRE", "valor": 50}).get_json()
    assert outra_feira["subcategoria_sugerida"]["nome"] == "Mercado"

    corpo = _dash(cliente_flask)
    assert corpo["hero"] == {"total_gasto": 500.0, "gasto_com_teto": 450.0, "gasto_sem_teto": 50.0,
                             "total_teto": 600.0, "percentual_uso": 75.0, "status": "folgado"}
    alimentacao = next(c for c in corpo["categorias"] if c["categoria_macro"] and c["categoria_macro"]["id"] == 1)
    assert (alimentacao["percentual"], alimentacao["status"], alimentacao["teto"]) == (84.0, "quase_no_teto", 500.0)
    assert corpo["categorias"][0] == alimentacao  # quase_no_teto vem antes do folgado (Lazer 30%)
    assert (corpo["quantidade_sem_categoria"], corpo["valor_sem_categoria"]) == (1, 50.0)
    assert [u["descricao"] for u in corpo["ultimos_lancamentos"]] == ["FEIRA LIVRE", "Cinema", "Feira Livre"]

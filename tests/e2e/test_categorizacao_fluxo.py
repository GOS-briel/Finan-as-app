# Importar a fatura real → categorizar → sugerir → reimportar (Etapas 8 e 9; pulado sem FATURA_PDF_PATH)
import pytest


@pytest.fixture
def importados(importar, fatura_teste, cliente_flask):
    """Importa a fatura real e devolve os 23 lançamentos de outubro/2026."""
    assert importar(fatura_teste).get_json()["inseridos"] == 23
    return cliente_flask.get("/lancamentos?mes=10&ano=2026&origem=fatura").get_json()


def _por_inicio(lista, prefixo):
    return next(l for l in lista if l["descricao"].startswith(prefixo))


def test_categorizar_importado_ensina_e_sugere_para_manual(cliente_flask, importados, categorias_popular):
    """Categorizar o DECATHLON importado faz um manual 'DECATHLON NITEROI' receber a sugestão."""
    decathlon = _por_inicio(importados, "DECATHLON")
    resposta = cliente_flask.post(f"/lancamentos/{decathlon['id']}/categorizar",
                                  json={"subcategoria_id": categorias_popular["Equipamento"]})
    assert resposta.get_json()["aprendizado"] == {"acao": "criado", "confianca": 1}
    manual = cliente_flask.post("/lancamentos", json={"data": "2026-10-22", "descricao": "Decathlon Niteroi", "valor": 99}).get_json()
    assert manual["subcategoria_sugerida"]["nome"] == "Equipamento"


def test_reimportacao_preserva_categorias_e_aprendizados(cliente_flask, importar, fatura_teste, importados,
                                                       categorias_popular, consultar):
    """Reimportar a fatura não duplica o importado categorizado nem mexe nos aprendizados."""
    decathlon = _por_inicio(importados, "DECATHLON")
    cliente_flask.post(f"/lancamentos/{decathlon['id']}/categorizar", json={"subcategoria_id": categorias_popular["Equipamento"]})
    cliente_flask.put(f"/lancamentos/{decathlon['id']}", json={"nota": "tenis de corrida"})
    aprendizados = consultar("SELECT * FROM aprendizados")
    assert importar(fatura_teste).get_json()["inseridos"] == 0
    lista = cliente_flask.get("/lancamentos?mes=10&ano=2026&origem=fatura").get_json()
    decathlons = [l for l in lista if l["descricao"].startswith("DECATHLON")]
    assert len(decathlons) == 1 and decathlons[0]["subcategoria_nome"] == "Equipamento"
    assert consultar("SELECT * FROM aprendizados") == aprendizados


def test_importado_apagado_volta_na_reimportacao(cliente_flask, importar, fatura_teste, importados):
    """DELETE definitivo + dedup por contagem: o importado apagado volta ao reimportar (ADR-016)."""
    renner = _por_inicio(importados, "RENNER")
    assert cliente_flask.delete(f"/lancamentos/{renner['id']}").status_code == 204
    corpo = importar(fatura_teste).get_json()
    assert (corpo["inseridos"], corpo["ignorados_duplicata"], corpo["total_confere"]) == (1, 22, True)


def test_importado_real_bloqueia_edicao_de_valor(cliente_flask, importados):
    """Um lançamento da fatura real não aceita mudar valor (403)."""
    renner = _por_inicio(importados, "RENNER")
    assert cliente_flask.put(f"/lancamentos/{renner['id']}", json={"valor": 1}).status_code == 403

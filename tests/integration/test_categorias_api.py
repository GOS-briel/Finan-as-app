# CRUD de subcategorias e listagem das macro (Etapa 6, ADRs 011 e 012)
import pytest

MACROS = ["Alimentação", "Lazer", "Compras", "Saúde", "Educação", "Esporte", "Transporte", "Outros"]
DUPLICADO = {"erro": "ja existe uma subcategoria com esse nome nesta categoria"}


@pytest.fixture
def criar(cliente_flask):
    def post(nome, macro_id, como_form=False):
        corpo = {"nome": nome, "categoria_macro_id": macro_id}
        if como_form:
            return cliente_flask.post("/subcategorias", data=corpo)
        return cliente_flask.post("/subcategorias", json=corpo)
    return post


def _subs_de(cliente, macro_id):
    macro = next(m for m in cliente.get("/categorias/macro").get_json() if m["id"] == macro_id)
    return macro["subcategorias"]


# GET /categorias/macro --------------------------------------------------------------
def test_get_sem_subcategorias(cliente_flask):
    """As 8 macro em ordem de id, todas com subcategorias = []."""
    corpo = cliente_flask.get("/categorias/macro").get_json()
    assert [m["nome"] for m in corpo] == MACROS
    assert all(m["subcategorias"] == [] for m in corpo)


def test_get_embute_subcategorias_em_ordem_natural(cliente_flask, criar):
    """Subs embutidas na macro, ordenadas sem acento e sem maiúsculas."""
    for nome in ("Zoológico", "açaí", "Água", "bar", "Delivery", "Restaurante"):
        criar(nome, 1)
    assert [s["nome"] for s in _subs_de(cliente_flask, 1)] == ["açaí", "Água", "bar", "Delivery", "Restaurante", "Zoológico"]


# POST /subcategorias --------------------------------------------------------------
def test_post_valido_cria_com_201(criar):
    """Nome válido numa macro existente → 201 com id, nome e macro."""
    resposta = criar("Delivery", 1)
    assert resposta.status_code == 201
    assert resposta.get_json() == {"id": 1, "nome": "Delivery", "categoria_macro_id": 1}


def test_post_por_formulario_com_id_em_texto_e_espacos(criar):
    """Form com id '1' e nome com espaços nas pontas → 201 com o nome limpo."""
    resposta = criar("  Restaurante  ", "1", como_form=True)
    assert resposta.status_code == 201 and resposta.get_json()["nome"] == "Restaurante"


@pytest.mark.parametrize("duplicado", ["Delivery", "DELIVERY", "delivery"])
def test_post_duplicado_na_mesma_macro_e_409(criar, duplicado):
    """Mesmo nome (sem diferenciar maiúsculas) na mesma macro → 409."""
    criar("Delivery", 1)
    resposta = criar(duplicado, 1)
    assert resposta.status_code == 409 and resposta.get_json() == DUPLICADO


def test_post_duplicado_com_acento_e_maiusculas_e_409(criar):
    """'AÇAÍ' colide com 'açaí' (casefold trata acentuadas, NOCASE do SQLite não)."""
    criar("açaí", 1)
    assert criar("AÇAÍ", 1).status_code == 409


def test_mesmo_nome_em_outra_macro_e_permitido(criar):
    """O nome só precisa ser único dentro da mesma macro."""
    criar("Delivery", 1)
    assert criar("Delivery", 2).status_code == 201


def test_post_macro_inexistente_e_400(criar):
    """categoria_macro_id que não existe no banco → 400 (sem fixar 1-8 no código)."""
    resposta = criar("Teste", 99)
    assert resposta.status_code == 400 and resposta.get_json() == {"erro": "categoria_macro_id nao existe"}


@pytest.mark.parametrize("macro_id", ["abc", True, 2.5, None], ids=["texto", "bool", "float", "ausente"])
def test_post_macro_id_invalido_e_400(criar, macro_id):
    """categoria_macro_id não inteiro (inclusive true) → 400."""
    assert criar("Teste", macro_id).status_code == 400


@pytest.mark.parametrize("nome", ["", "   ", None, "x" * 51], ids=["vazio", "espacos", "ausente", "51-chars"])
def test_post_nome_invalido_e_400(criar, nome):
    """Nome vazio, só espaços, ausente ou com mais de 50 caracteres → 400."""
    assert criar(nome, 1).status_code == 400


def test_post_nome_com_exatamente_50_caracteres(criar):
    """50 caracteres é o limite aceito."""
    assert criar("x" * 50, 8).status_code == 201


# PUT /subcategorias/<id> ------------------------------------------------------------
def test_put_renomeia(cliente_flask, criar):
    """Renomear → 200 com o novo nome."""
    sub = criar("Restaurante", 1).get_json()
    resposta = cliente_flask.put(f"/subcategorias/{sub['id']}", json={"nome": "Restaurantes"})
    assert resposta.status_code == 200
    assert resposta.get_json() == {"id": sub["id"], "nome": "Restaurantes", "categoria_macro_id": 1}


def test_put_mudando_so_maiusculas_do_proprio_nome(cliente_flask, criar):
    """Mudar a capitalização do próprio nome não é duplicata."""
    sub = criar("Restaurantes", 1).get_json()
    assert cliente_flask.put(f"/subcategorias/{sub['id']}", json={"nome": "RESTAURANTES"}).status_code == 200


def test_put_com_nome_de_outra_sub_da_mesma_macro_e_409(cliente_flask, criar):
    """Renomear para o nome de outra sub da mesma macro → 409."""
    criar("Delivery", 1)
    sub = criar("Restaurante", 1).get_json()
    resposta = cliente_flask.put(f"/subcategorias/{sub['id']}", json={"nome": "delivery"})
    assert resposta.status_code == 409 and resposta.get_json() == DUPLICADO


def test_put_id_inexistente_e_404(cliente_flask):
    """PUT em subcategoria que não existe → 404."""
    assert cliente_flask.put("/subcategorias/9999", json={"nome": "Nada"}).status_code == 404


def test_put_nome_vazio_e_400(cliente_flask, criar):
    """PUT com nome só de espaços → 400."""
    sub = criar("Restaurante", 1).get_json()
    assert cliente_flask.put(f"/subcategorias/{sub['id']}", json={"nome": "  "}).status_code == 400


# DELETE /subcategorias/<id> -----------------------------------------------------------
def test_delete_sem_vinculos_e_204(cliente_flask, criar, consultar):
    """Sem lançamentos nem aprendizados → 204 sem corpo, e a linha some."""
    sub = criar("bar", 1).get_json()
    resposta = cliente_flask.delete(f"/subcategorias/{sub['id']}")
    assert resposta.status_code == 204 and resposta.data == b""
    assert consultar("SELECT COUNT(*) FROM subcategorias") == [(0,)]
    assert cliente_flask.delete(f"/subcategorias/{sub['id']}").status_code == 404


def test_delete_com_lancamentos_e_409_com_contagem(cliente_flask, criar, lancamento_manual, consultar):
    """2 lançamentos vinculados → 409 com as duas contagens e nada apagado (ADR-011)."""
    sub = criar("Delivery", 1).get_json()
    lancamento_manual(subcategoria_id=sub["id"])
    lancamento_manual(subcategoria_id=sub["id"])
    resposta = cliente_flask.delete(f"/subcategorias/{sub['id']}")
    assert resposta.status_code == 409
    assert resposta.get_json() == {
        "erro": "nao e possivel deletar: 2 lancamentos e 0 aprendizados vinculados a esta subcategoria",
        "lancamentos_vinculados": 2, "aprendizados_vinculados": 0}
    assert consultar("SELECT COUNT(*) FROM subcategorias") == [(1,)]


def test_delete_com_aprendizado_e_409(cliente_flask, criar, banco_temporario):
    """1 aprendizado vinculado também bloqueia (evitaria 500 por FK) — ADR-012."""
    from app.db import inicializar
    sub = criar("Zoológico", 1).get_json()
    conexao = inicializar.conectar()
    with conexao:
        conexao.execute("INSERT INTO aprendizados (padrao_descricao, subcategoria_id, criado_em, atualizado_em) "
                        "VALUES ('zoo niteroi', ?, 'agora', 'agora')", (sub["id"],))
    conexao.close()
    corpo = cliente_flask.delete(f"/subcategorias/{sub['id']}").get_json()
    assert (corpo["lancamentos_vinculados"], corpo["aprendizados_vinculados"]) == (0, 1)


def test_delete_id_inexistente_e_404(cliente_flask):
    """DELETE de subcategoria que não existe → 404."""
    assert cliente_flask.delete("/subcategorias/9999").status_code == 404


def test_macro_continuam_intactas_apos_operacoes(cliente_flask, criar, consultar):
    """Nenhuma operação de subcategoria altera as 8 macro."""
    sub = criar("X", 1).get_json()
    cliente_flask.put(f"/subcategorias/{sub['id']}", json={"nome": "Y"})
    cliente_flask.delete(f"/subcategorias/{sub['id']}")
    assert consultar("SELECT id, nome FROM categorias_macro ORDER BY id") == list(enumerate(MACROS, 1))

# Categorização com aprendizado e sugestões (Etapa 9, ADRs 017 a 020)
import pytest

from app.db import lancamentos as db_lancamentos


@pytest.fixture
def categorizar(cliente_flask):
    def enviar(lancamento_id, subcategoria_id, como_form=False):
        url = f"/lancamentos/{lancamento_id}/categorizar"
        corpo = {"subcategoria_id": subcategoria_id}
        return cliente_flask.post(url, data=corpo) if como_form else cliente_flask.post(url, json=corpo)
    return enviar


@pytest.fixture
def decathlons(lancamento_manual):
    """Importado parcelado + manuais com o mesmo padrão ('decathlon niteroi') e um de outra cidade."""
    return {
        "importado": lancamento_manual(descricao="DECATHLON NITEROI - Parcela 5/6", valor=66.66, data="2026-10-01",
                                       origem="fatura", parcela_atual=5, parcela_total=6),
        "m1": lancamento_manual(descricao="DECATHLON NITEROI"),
        "m2": lancamento_manual(descricao="Decathlon  Niteroi"),
        "m4": lancamento_manual(descricao="DECATHLON NITEROI"),
        "rio": lancamento_manual(descricao="DECATHLON RIO"),
        "acai": lancamento_manual(descricao="ACAI DA BARRA NITEROI"),
    }


def _item(cliente, lancamento_id, query="mes=10&ano=2026"):
    return next(l for l in cliente.get(f"/lancamentos?{query}").get_json() if l["id"] == lancamento_id)


# Ciclo de aprendizado (ADR-019) ------------------------------------------------------------
def test_criado(cliente_flask, categorizar, decathlons, categorias_popular):
    """Padrão novo → acao 'criado', confianca 1, e o lançamento volta no formato do GET."""
    corpo = categorizar(decathlons["importado"], categorias_popular["Equipamento"]).get_json()
    assert corpo["aprendizado"] == {"acao": "criado", "confianca": 1}
    assert corpo["lancamento"]["subcategoria_nome"] == "Equipamento"
    assert corpo["lancamento"]["subcategoria_sugerida"] is None
    assert set(corpo["lancamento"]) == set(_item(cliente_flask, decathlons["importado"]))


def test_inalterado_no_clique_duplo(categorizar, decathlons, categorias_popular):
    """Categorizar de novo o mesmo lançamento na mesma sub não infla a confiança."""
    categorizar(decathlons["importado"], categorias_popular["Equipamento"])
    corpo = categorizar(decathlons["importado"], categorias_popular["Equipamento"]).get_json()
    assert corpo["aprendizado"] == {"acao": "inalterado", "confianca": 1}


def test_reforcado(categorizar, decathlons, categorias_popular):
    """Outro lançamento com o mesmo padrão e a mesma sub → 'reforcado', confianca 2."""
    categorizar(decathlons["importado"], categorias_popular["Equipamento"])
    corpo = categorizar(decathlons["m1"], categorias_popular["Equipamento"]).get_json()
    assert corpo["aprendizado"] == {"acao": "reforcado", "confianca": 2}


def test_sobrescrito(categorizar, decathlons, categorias_popular):
    """Mesmo padrão, outra sub → 'sobrescrito', confianca volta a 1 (maiúsculas/espaços não importam)."""
    categorizar(decathlons["importado"], categorias_popular["Equipamento"])
    categorizar(decathlons["m1"], categorias_popular["Equipamento"])
    corpo = categorizar(decathlons["m2"], categorias_popular["Roupas"]).get_json()
    assert corpo["aprendizado"] == {"acao": "sobrescrito", "confianca": 1}


def test_apagado_ao_descategorizar(cliente_flask, categorizar, decathlons, categorias_popular, consultar):
    """Descategorizar o lançamento cuja sub é a do aprendizado → 'apagado', e a sugestão some dos outros."""
    categorizar(decathlons["m2"], categorias_popular["Roupas"])
    assert _item(cliente_flask, decathlons["m4"])["subcategoria_sugerida"]["nome"] == "Roupas"
    corpo = categorizar(decathlons["m2"], None).get_json()
    assert corpo["aprendizado"] == {"acao": "apagado", "confianca": None}
    assert corpo["lancamento"]["subcategoria_id"] is None
    assert consultar("SELECT COUNT(*) FROM aprendizados") == [(0,)]
    assert _item(cliente_flask, decathlons["m4"])["subcategoria_sugerida"] is None


def test_nenhuma_sem_aprendizado(categorizar, decathlons):
    """Descategorizar sem aprendizado existente → 'nenhuma'."""
    assert categorizar(decathlons["m1"], None).get_json()["aprendizado"]["acao"] == "nenhuma"


def test_nenhuma_preserva_aprendizado_de_outra_sub(cliente_flask, categorizar, decathlons, categorias_popular, consultar):
    """Lançamento em Mercado (via PUT silencioso), aprendizado em Equipamento: descategorizar não apaga."""
    categorizar(decathlons["m1"], categorias_popular["Equipamento"])
    cliente_flask.put(f"/lancamentos/{decathlons['m4']}", json={"subcategoria_id": categorias_popular["Mercado"]})
    antes = consultar("SELECT padrao_descricao, subcategoria_id, confianca FROM aprendizados")
    assert categorizar(decathlons["m4"], None).get_json()["aprendizado"]["acao"] == "nenhuma"
    assert consultar("SELECT padrao_descricao, subcategoria_id, confianca FROM aprendizados") == antes


def test_descricao_vazia_apos_normalizar_nao_aprende(categorizar, lancamento_manual, categorias_popular, consultar):
    """Descrição que some na normalização (só sufixo de parcela) não cria aprendizado."""
    lancamento_id = lancamento_manual(descricao="- Parcela 1/2")
    corpo = categorizar(lancamento_id, categorias_popular["Mercado"]).get_json()
    assert corpo["aprendizado"] == {"acao": "nenhuma", "confianca": None}
    assert corpo["lancamento"]["subcategoria_nome"] == "Mercado"
    assert consultar("SELECT COUNT(*) FROM aprendizados") == [(0,)]


# Validação ------------------------------------------------------------------------------------
def test_lancamento_inexistente_e_404(categorizar, categorias_popular):
    """Categorizar lançamento que não existe → 404."""
    assert categorizar(9999, categorias_popular["Mercado"]).status_code == 404


def test_subcategoria_inexistente_e_400_sem_mudar_nada(cliente_flask, categorizar, decathlons):
    """Subcategoria inexistente → 400, e o lançamento continua sem categoria (transação desfeita)."""
    resposta = categorizar(decathlons["rio"], 999)
    assert resposta.status_code == 400 and resposta.get_json() == {"erro": "subcategoria_id nao existe"}
    assert _item(cliente_flask, decathlons["rio"])["subcategoria_id"] is None


def test_corpo_sem_subcategoria_id_e_400(cliente_flask, decathlons):
    """subcategoria_id é obrigatório (null é o jeito de descategorizar)."""
    resposta = cliente_flask.post(f"/lancamentos/{decathlons['rio']}/categorizar", json={})
    assert resposta.status_code == 400


def test_campo_extra_e_400(cliente_flask, decathlons, categorias_popular):
    """Qualquer campo além de subcategoria_id → 400 campos_nao_permitidos."""
    resposta = cliente_flask.post(f"/lancamentos/{decathlons['rio']}/categorizar",
                                  json={"subcategoria_id": categorias_popular["Mercado"], "nota": "x"})
    assert resposta.get_json()["campos_nao_permitidos"] == ["nota"]


def test_subcategoria_texto_invalido_e_400(categorizar, decathlons):
    """subcategoria_id 'abc' → 400."""
    assert categorizar(decathlons["rio"], "abc").status_code == 400


def test_formulario_id_em_texto_e_vazio_descategoriza(categorizar, decathlons, categorias_popular):
    """Pelo form: '7' categoriza; '' descategoriza."""
    assert categorizar(decathlons["rio"], str(categorias_popular["Equipamento"]), como_form=True).get_json()["aprendizado"]["acao"] == "criado"
    assert categorizar(decathlons["rio"], "", como_form=True).get_json()["aprendizado"]["acao"] == "apagado"


# Sugestões no GET (ADR-018, ADR-020) ------------------------------------------------------------
def test_sem_aprendizados_todos_tem_sugestao_null(cliente_flask, decathlons):
    """A chave subcategoria_sugerida existe em todos e é null sem aprendizados."""
    lista = cliente_flask.get("/lancamentos?mes=10&ano=2026").get_json()
    assert lista and all("subcategoria_sugerida" in l and l["subcategoria_sugerida"] is None for l in lista)


def test_sugestao_aparece_em_outro_do_mesmo_padrao(cliente_flask, categorizar, decathlons, categorias_popular):
    """Depois de categorizar o importado, outro 'DECATHLON NITEROI' recebe a sugestão completa."""
    categorizar(decathlons["importado"], categorias_popular["Equipamento"])
    assert _item(cliente_flask, decathlons["m4"])["subcategoria_sugerida"] == {
        "id": categorias_popular["Equipamento"], "nome": "Equipamento", "categoria_macro_id": 6,
        "categoria_macro_nome": "Esporte", "confianca": 1}
    assert _item(cliente_flask, decathlons["m2"])["subcategoria_sugerida"]["nome"] == "Equipamento"


def test_sugestao_acompanha_reforco_e_sobrescrita(cliente_flask, categorizar, decathlons, categorias_popular):
    """A confiança e a sub sugeridas refletem o aprendizado atual."""
    categorizar(decathlons["importado"], categorias_popular["Equipamento"])
    categorizar(decathlons["m1"], categorias_popular["Equipamento"])
    assert _item(cliente_flask, decathlons["m4"])["subcategoria_sugerida"]["confianca"] == 2
    categorizar(decathlons["m2"], categorias_popular["Roupas"])
    sugestao = _item(cliente_flask, decathlons["m4"])["subcategoria_sugerida"]
    assert (sugestao["nome"], sugestao["categoria_macro_nome"], sugestao["confianca"]) == ("Roupas", "Compras", 1)


def test_sem_sugestao_para_outro_padrao_e_para_categorizados(cliente_flask, categorizar, decathlons, categorias_popular):
    """'DECATHLON RIO' e 'ACAI' não recebem a sugestão; o categorizado tem sugestão null."""
    categorizar(decathlons["importado"], categorias_popular["Equipamento"])
    assert _item(cliente_flask, decathlons["rio"])["subcategoria_sugerida"] is None
    assert _item(cliente_flask, decathlons["acai"])["subcategoria_sugerida"] is None
    assert _item(cliente_flask, decathlons["importado"])["subcategoria_sugerida"] is None


def test_get_faz_uma_unica_query_em_aprendizados(cliente_flask, decathlons, monkeypatch):
    """Sugestões em lote: 1 query em aprendizados para a lista inteira (sem N+1)."""
    queries = []
    original = db_lancamentos.conectar

    def conectar_rastreado():
        conexao = original()
        conexao.set_trace_callback(queries.append)
        return conexao

    monkeypatch.setattr(db_lancamentos, "conectar", conectar_rastreado)
    cliente_flask.get("/lancamentos?mes=10&ano=2026")
    assert len([q for q in queries if "aprendizados" in q]) == 1
    assert len(queries) == 2


# Filtro sem_categoria ------------------------------------------------------------------------
def test_filtro_sem_categoria(cliente_flask, categorizar, decathlons, categorias_popular):
    """sem_categoria=true traz só os não categorizados; false traz todos."""
    categorizar(decathlons["importado"], categorias_popular["Equipamento"])
    sem = cliente_flask.get("/lancamentos?mes=10&ano=2026&sem_categoria=true").get_json()
    todos = cliente_flask.get("/lancamentos?mes=10&ano=2026&sem_categoria=false").get_json()
    assert len(sem) == 5 and all(l["subcategoria_id"] is None for l in sem)
    assert len(todos) == 6


def test_filtro_sem_categoria_com_origem(cliente_flask, decathlons):
    """sem_categoria combina com origem."""
    lista = cliente_flask.get("/lancamentos?mes=10&ano=2026&sem_categoria=true&origem=fatura").get_json()
    assert [l["id"] for l in lista] == [decathlons["importado"]]


def test_filtro_sem_categoria_invalido_e_400(cliente_flask):
    """Só 'true' ou 'false'."""
    assert cliente_flask.get("/lancamentos?mes=10&ano=2026&sem_categoria=sim").status_code == 400


# Integração com outras etapas --------------------------------------------------------------------
def test_subcategoria_com_aprendizado_nao_pode_ser_apagada(cliente_flask, categorizar, decathlons, categorias_popular):
    """A Etapa 6 protege a sugestão: DELETE da sub com aprendizado → 409."""
    categorizar(decathlons["importado"], categorias_popular["Equipamento"])
    resposta = cliente_flask.delete(f"/subcategorias/{categorias_popular['Equipamento']}")
    assert resposta.status_code == 409 and resposta.get_json()["aprendizados_vinculados"] == 1

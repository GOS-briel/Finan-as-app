# CRUD de lançamentos manuais e proteção dos importados (Etapa 8, ADRs 015, 016 e 017)
# "Hoje" é 2026-10-22 (fixture hoje_fixo): 89 dias = 2026-07-25, 90 = 07-24, 91 = 07-23.
import pytest

BLOQUEIO = "lancamentos importados da fatura so permitem edicao de subcategoria e nota"


@pytest.fixture
def post(cliente_flask):
    def enviar(**corpo):
        return cliente_flask.post("/lancamentos", json=corpo)
    return enviar


@pytest.fixture
def put(cliente_flask):
    def enviar(lancamento_id, **corpo):
        return cliente_flask.put(f"/lancamentos/{lancamento_id}", json=corpo)
    return enviar


@pytest.fixture
def importado(lancamento_manual):
    """Um lançamento como os da fatura: origem 'fatura', parcelado, data AAAA-MM-01."""
    return lancamento_manual(descricao="LOJA ESPORTE NITEROI - Parcela 5/6", valor=66.66, data="2026-10-01",
                             origem="fatura", parcela_atual=5, parcela_total=6)


def _valido(**extra):
    return {"data": "2026-10-22", "descricao": "Padaria", "valor": 12.5, **extra}


# POST ---------------------------------------------------------------------------
def test_post_manual_valido(post, categorias_popular):
    """201 com origem manual, parcelas null, nomes de subcategoria/macro e criado_em."""
    resposta = post(**_valido(subcategoria_id=categorias_popular["Mercado"], nota="pao"))
    corpo = resposta.get_json()
    assert resposta.status_code == 201
    assert corpo["origem"] == "manual" and corpo["parcela_atual"] is None and corpo["parcela_total"] is None
    assert (corpo["subcategoria_nome"], corpo["categoria_macro_nome"]) == ("Mercado", "Alimentação")
    assert corpo["nota"] == "pao" and corpo["criado_em"]


@pytest.mark.parametrize("data", ["2026-10-22", "2026-07-25", "2026-07-24"], ids=["hoje", "89-dias", "90-dias"])
def test_post_data_dentro_da_janela(post, data):
    """Hoje, 89 e 90 dias atrás são aceitos (fronteira literal de '> 90 dias')."""
    assert post(**_valido(data=data)).status_code == 201


@pytest.mark.parametrize(
    ("data", "erro"),
    [("2026-10-23", "data nao pode ser futura"), ("2026-07-23", "data nao pode ser anterior a 90 dias atras"),
     ("21/10/2026", "data deve estar no formato AAAA-MM-DD"), ("20261021", "data deve estar no formato AAAA-MM-DD"),
     ("2026-W43-3", "data deve estar no formato AAAA-MM-DD"), ("2026-02-30", "data invalida"), (None, "data e obrigatoria")],
    ids=["amanha", "91-dias", "formato-br", "sem-hifens", "semana-iso", "dia-impossivel", "ausente"],
)
def test_post_data_invalida(post, data, erro):
    """Futuro, mais de 90 dias e formatos fora de AAAA-MM-DD → 400 (ADR-015)."""
    resposta = post(**_valido(data=data))
    assert resposta.status_code == 400 and resposta.get_json() == {"erro": erro}


@pytest.mark.parametrize("descricao", ["", "   ", None, "x" * 201], ids=["vazia", "espacos", "ausente", "201-chars"])
def test_post_descricao_invalida(post, descricao):
    """Descrição obrigatória, até 200 caracteres."""
    assert post(**_valido(descricao=descricao)).status_code == 400


def test_post_descricao_perde_espacos_das_pontas(post):
    """'  Uber  ' é gravado como 'Uber'."""
    assert post(**_valido(descricao="  Uber  ")).get_json()["descricao"] == "Uber"


def test_post_valor_negativo_e_400(post):
    """Valor negativo é recusado no Python (o CHECK não existe em lancamentos)."""
    assert post(**_valido(valor=-5)).status_code == 400


def test_post_subcategoria_inexistente_e_400(post):
    """subcategoria_id que não existe → 400."""
    resposta = post(**_valido(subcategoria_id=999))
    assert resposta.status_code == 400 and resposta.get_json() == {"erro": "subcategoria_id nao existe"}


def test_post_sem_subcategoria(post):
    """Sem subcategoria: os 4 campos de categoria vêm null."""
    corpo = post(**_valido()).get_json()
    assert [corpo[k] for k in ("subcategoria_id", "subcategoria_nome", "categoria_macro_id", "categoria_macro_nome")] == [None] * 4


def test_post_nota_longa_e_400(post):
    """Nota com mais de 500 caracteres → 400."""
    assert post(**_valido(nota="n" * 501)).status_code == 400


@pytest.mark.parametrize(
    ("extra", "nao_permitidos"),
    [({"origem": "fatura"}, ["origem"]), ({"parcela_atual": 1, "parcela_total": 3, "id": 50}, ["id", "parcela_atual", "parcela_total"])],
    ids=["origem", "parcelas-e-id"],
)
def test_post_campos_nao_permitidos_e_400(post, extra, nao_permitidos):
    """Campos que ninguém edita → 400 listando todos (não são ignorados em silêncio)."""
    corpo = post(**_valido(**extra)).get_json()
    assert corpo["campos_nao_permitidos"] == nao_permitidos


# PUT em manual -------------------------------------------------------------------------
def test_put_manual_muda_valor(put, lancamento_manual):
    """Manual aceita alterar o valor."""
    lancamento_id = lancamento_manual(valor=12.5)
    resposta = put(lancamento_id, valor=15)
    assert resposta.status_code == 200 and resposta.get_json()["valor"] == 15.0


def test_put_manual_muda_data_dentro_da_janela_e_descricao(put, lancamento_manual):
    """Data nova dentro dos 90 dias e descrição nova → 200."""
    lancamento_id = lancamento_manual()
    corpo = put(lancamento_id, data="2026-10-17", descricao="Padaria Nova").get_json()
    assert (corpo["data"], corpo["descricao"]) == ("2026-10-17", "Padaria Nova")


@pytest.mark.parametrize("data", ["2026-10-23", "2026-06-24"], ids=["futuro", "fora-da-janela"])
def test_put_manual_mudando_data_invalida_e_400(put, lancamento_manual, data):
    """Mudar a data para o futuro ou para mais de 90 dias atrás → 400."""
    assert put(lancamento_manual(), data=data).status_code == 400


def test_put_manual_antigo_reenviando_a_mesma_data(put, lancamento_manual):
    """Manual de 120 dias atrás: reenviar a mesma data e mudar só o valor funciona (janela só se a data mudar)."""
    lancamento_id = lancamento_manual(data="2026-06-24", descricao="Antigo", valor=10)
    resposta = put(lancamento_id, data="2026-06-24", descricao="Antigo", valor=11)
    assert resposta.status_code == 200 and resposta.get_json()["valor"] == 11.0


def test_put_null_descategoriza_e_limpa_nota(put, lancamento_manual, categorias_popular):
    """subcategoria_id e nota null removem a categoria e a nota."""
    lancamento_id = lancamento_manual(subcategoria_id=categorias_popular["Mercado"], nota="x")
    corpo = put(lancamento_id, subcategoria_id=None, nota=None).get_json()
    assert corpo["subcategoria_id"] is None and corpo["nota"] is None


def test_put_manual_com_origem_e_400_nao_403(put, lancamento_manual):
    """origem é 'nunca editável' (400), mesmo em manual."""
    resposta = put(lancamento_manual(), origem="fatura")
    assert resposta.status_code == 400 and resposta.get_json()["campos_nao_permitidos"] == ["origem"]


def test_put_criado_em_e_400(put, lancamento_manual):
    """criado_em não é editável."""
    assert put(lancamento_manual(), criado_em="2020-01-01").status_code == 400


def test_put_corpo_vazio_e_400(put, lancamento_manual):
    """PUT sem nenhum campo → 400."""
    resposta = put(lancamento_manual())
    assert resposta.status_code == 400 and resposta.get_json() == {"erro": "nenhum campo para atualizar"}


def test_put_id_inexistente_e_404(put):
    """PUT em lançamento que não existe → 404."""
    assert put(9999, valor=1).status_code == 404


def test_put_subcategoria_inexistente_e_400(put, lancamento_manual):
    """Subcategoria inexistente no PUT → 400."""
    assert put(lancamento_manual(), subcategoria_id=999).status_code == 400


def test_put_formato_invalido_e_400(put, lancamento_manual):
    """Valor em formato inválido no PUT → 400."""
    assert put(lancamento_manual(), valor="abc").status_code == 400


# PUT em importado (ADR-016) ---------------------------------------------------------------
def test_put_importado_mudando_campos_bloqueados_e_403(put, importado):
    """Alterar descricao, valor e data de um importado → 403 listando os 3."""
    resposta = put(importado, valor=1, descricao="OUTRA", data="2026-10-02")
    assert resposta.status_code == 403
    assert resposta.get_json() == {"erro": BLOQUEIO, "campos_bloqueados": ["descricao", "valor", "data"]}


def test_put_importado_valor_mudando_1_centavo_e_403(put, importado):
    """Qualquer mudança real num campo bloqueado é 403, listando só ele."""
    assert put(importado, valor=66.67).get_json()["campos_bloqueados"] == ["valor"]


def test_put_importado_muda_subcategoria_e_nota(put, importado, categorias_popular):
    """Subcategoria e nota são editáveis em importados; a resposta traz os nomes do JOIN."""
    corpo = put(importado, subcategoria_id=categorias_popular["Equipamento"], nota="tenis").get_json()
    assert (corpo["subcategoria_nome"], corpo["categoria_macro_nome"], corpo["nota"]) == ("Equipamento", "Esporte", "tenis")


def test_put_importado_reenviando_objeto_inteiro_igual(put, importado, categorias_popular):
    """Objeto inteiro com data/descrição/valor iguais + subcategoria nova → 200 (só conta o que mudou)."""
    resposta = put(importado, data="2026-10-01", descricao="LOJA ESPORTE NITEROI - Parcela 5/6", valor=66.66,
                   subcategoria_id=categorias_popular["Equipamento"])
    assert resposta.status_code == 200 and resposta.get_json()["subcategoria_nome"] == "Equipamento"


def test_put_importado_valores_iguais_em_outro_formato(put, importado):
    """'66.66' em texto e descrição com espaços extras são normalizados e contam como iguais."""
    assert put(importado, valor="66.66", descricao="  LOJA ESPORTE NITEROI - Parcela 5/6  ").status_code == 200


def test_put_nao_cria_aprendizado(put, importado, categorias_popular, consultar):
    """O PUT categoriza em silêncio (ADR-017): nada em aprendizados."""
    put(importado, subcategoria_id=categorias_popular["Equipamento"])
    assert consultar("SELECT COUNT(*) FROM aprendizados") == [(0,)]


# DELETE ---------------------------------------------------------------------------------
def test_delete_manual_e_204(cliente_flask, lancamento_manual, consultar):
    """DELETE de manual → 204 sem corpo, e a linha some."""
    lancamento_id = lancamento_manual()
    resposta = cliente_flask.delete(f"/lancamentos/{lancamento_id}")
    assert resposta.status_code == 204 and resposta.data == b""
    assert consultar("SELECT COUNT(*) FROM lancamentos") == [(0,)]


def test_delete_importado_e_204(cliente_flask, importado, consultar):
    """Hard delete não discrimina origem."""
    assert cliente_flask.delete(f"/lancamentos/{importado}").status_code == 204
    assert consultar("SELECT COUNT(*) FROM lancamentos") == [(0,)]


def test_delete_inexistente_e_404(cliente_flask):
    """DELETE de lançamento que não existe → 404."""
    assert cliente_flask.delete("/lancamentos/9999").status_code == 404


# GET /lancamentos --------------------------------------------------------------------------
@pytest.fixture
def mes_variado(lancamento_manual, categorias_popular, importado):
    """Outubro: 1 importado (sem categoria), manuais em Alimentação/Esporte/sem categoria; julho: 1 manual."""
    ids = {
        "importado": importado,
        "feira": lancamento_manual(descricao="Feira", data="2026-10-20", subcategoria_id=categorias_popular["Mercado"]),
        "chuteira": lancamento_manual(descricao="Chuteira", data="2026-10-21", subcategoria_id=categorias_popular["Equipamento"]),
        "avulso": lancamento_manual(descricao="Avulso", data="2026-10-21"),
        "julho": lancamento_manual(descricao="Julho", data="2026-07-25"),
    }
    return ids


def _descricoes(cliente, query):
    return [l["descricao"] for l in cliente.get(f"/lancamentos?{query}").get_json()]


def test_get_lista_o_mes_ordenado(cliente_flask, mes_variado):
    """Só outubro, por data DESC e id DESC; o de julho fica de fora."""
    assert _descricoes(cliente_flask, "mes=10&ano=2026") == [
        "Avulso", "Chuteira", "Feira", "LOJA ESPORTE NITEROI - Parcela 5/6"]


def test_get_sem_categoria_aparece_com_nulls(cliente_flask, mes_variado):
    """LEFT JOIN: importado sem categoria aparece, com campos de categoria null."""
    importado = next(l for l in cliente_flask.get("/lancamentos?mes=10&ano=2026").get_json() if l["origem"] == "fatura")
    assert importado["categoria_macro_id"] is None and importado["subcategoria_nome"] is None


@pytest.mark.parametrize(
    ("filtro", "esperado"),
    [("origem=fatura", ["LOJA ESPORTE NITEROI - Parcela 5/6"]), ("origem=manual", ["Avulso", "Chuteira", "Feira"]),
     ("categoria_macro_id=6", ["Chuteira"]), ("categoria_macro_id=1&origem=manual", ["Feira"]),
     ("categoria_macro_id=1&origem=fatura", []), ("categoria_macro_id=8", [])],
    ids=["so-importados", "so-manuais", "so-esporte", "alimentacao-e-manual", "intersecao-vazia", "macro-sem-lancamentos"],
)
def test_get_filtros(cliente_flask, mes_variado, filtro, esperado):
    """Filtros de origem e macro, sozinhos e combinados (interseção)."""
    assert _descricoes(cliente_flask, f"mes=10&ano=2026&{filtro}") == esperado


def test_get_outro_mes(cliente_flask, mes_variado):
    """Julho traz só o lançamento de julho."""
    assert _descricoes(cliente_flask, "mes=7&ano=2026") == ["Julho"]


def test_get_dezembro_vai_ate_o_fim_do_ano(cliente_flask, lancamento_manual):
    """O intervalo de dezembro termina em 1º de janeiro do ano seguinte."""
    lancamento_manual(descricao="Natal", data="2025-12-31")
    lancamento_manual(descricao="Ano novo", data="2026-01-01")
    assert _descricoes(cliente_flask, "mes=12&ano=2025") == ["Natal"]


@pytest.mark.parametrize("query", ["ano=2026", "mes=10&ano=2026&origem=outra", "mes=10&ano=2026&categoria_macro_id=abc"],
                         ids=["sem-mes", "origem-invalida", "macro-invalida"])
def test_get_parametros_invalidos_e_400(cliente_flask, query):
    """mes obrigatório; origem só manual/fatura; macro inteira."""
    assert cliente_flask.get(f"/lancamentos?{query}").status_code == 400

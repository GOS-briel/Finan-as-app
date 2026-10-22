# CRUD de tetos com herança do mês anterior (Etapa 7, ADRs 013 e 014)
import pytest

NULO = {"valor": None, "herdado": False, "origem_mes": None, "origem_ano": None}


@pytest.fixture
def api(cliente_flask):
    class Api:
        @staticmethod
        def get(mes, ano):
            return cliente_flask.get(f"/tetos?mes={mes}&ano={ano}")

        @staticmethod
        def put(macro, mes, ano, valor, como_form=False):
            corpo = {"categoria_macro_id": macro, "mes": mes, "ano": ano, "valor": valor}
            return cliente_flask.put("/tetos", data=corpo) if como_form else cliente_flask.put("/tetos", json=corpo)

        @staticmethod
        def delete(macro, mes, ano):
            return cliente_flask.delete(f"/tetos?categoria_macro_id={macro}&mes={mes}&ano={ano}")

        @classmethod
        def teto(cls, macro, mes, ano):
            linha = cls.get(mes, ano).get_json()[macro - 1]
            return {k: linha[k] for k in ("valor", "herdado", "origem_mes", "origem_ano")}

    return Api


# GET -----------------------------------------------------------------------------
def test_get_sem_tetos_traz_8_linhas_nulas(api):
    """Sem nenhum teto: 8 linhas na ordem canônica, valor null e herdado false."""
    corpo = api.get(10, 2026).get_json()
    assert len(corpo) == 8 and [l["categoria_macro"]["id"] for l in corpo] == list(range(1, 9))
    assert all({k: l[k] for k in NULO} == NULO for l in corpo)


@pytest.mark.parametrize("query", ["mes=10", "ano=2026", "mes=13&ano=2026", "mes=10&ano=1999"])
def test_get_parametros_invalidos_e_400(cliente_flask, query):
    """mes/ano ausentes ou fora do intervalo → 400."""
    assert cliente_flask.get(f"/tetos?{query}").status_code == 400


# PUT (upsert) ------------------------------------------------------------------------
def test_put_cria_e_get_mostra_teto_definido(api):
    """PUT novo → 200; GET do mesmo mês mostra herdado false e origem no próprio mês."""
    resposta = api.put(1, 10, 2026, 800)
    assert resposta.status_code == 200
    assert resposta.get_json() == {"valor": 800.0, "categoria_macro_id": 1, "mes": 10, "ano": 2026}
    assert api.teto(1, 10, 2026) == {"valor": 800.0, "herdado": False, "origem_mes": 10, "origem_ano": 2026}


def test_put_atualiza_sem_duplicar(api, consultar):
    """Segundo PUT na mesma combinação faz UPDATE (ON CONFLICT): 1 linha, valor novo."""
    api.put(1, 10, 2026, 800)
    assert api.put(1, 10, 2026, 900).get_json()["valor"] == 900.0
    assert consultar("SELECT valor FROM tetos") == [(900.0,)]


def test_put_por_formulario_com_campos_em_texto(api):
    """Form com todos os campos em texto → 200 com tipos corretos."""
    resposta = api.put("4", "10", "2026", "350.5", como_form=True)
    assert resposta.get_json() == {"valor": 350.5, "categoria_macro_id": 4, "mes": 10, "ano": 2026}


def test_put_valor_zero_e_valido_e_diferente_de_null(api):
    """Teto 0 ('não gastar nada') é aceito e aparece como 0, não null."""
    assert api.put(2, 10, 2026, 0).status_code == 200
    assert api.teto(2, 10, 2026)["valor"] == 0.0


def test_put_arredonda_valor(api):
    """123.456 vira 123.46."""
    assert api.put(3, 10, 2026, 123.456).get_json()["valor"] == 123.46


@pytest.mark.parametrize(
    ("macro", "mes", "ano", "valor", "erro"),
    [(99, 10, 2026, 100, "categoria_macro_id nao existe"), (1, 13, 2026, 100, "mes deve estar entre 1 e 12"),
     (1, 0, 2026, 100, "mes deve estar entre 1 e 12"), (1, 10, 1999, 100, "ano deve estar entre 2000 e 2100"),
     (1, 10, 2101, 100, "ano deve estar entre 2000 e 2100"), (1, "x", 2026, 100, "mes deve ser inteiro"),
     (1, 10, 2026, -10, "valor nao pode ser negativo"), (1, 10, 2026, "abc", "valor deve ser numero"),
     (1, 10, 2026, True, "valor deve ser numero"), (1, 10, 2026, None, "valor e obrigatorio"),
     (1, 10, 2026, "nan", "valor deve ser numero")],
    ids=["macro-99", "mes-13", "mes-0", "ano-1999", "ano-2101", "mes-texto", "valor-negativo", "valor-texto",
         "valor-bool", "valor-ausente", "valor-nan"],
)
def test_put_invalido_e_400(api, macro, mes, ano, valor, erro):
    """Validação no Python antes dos CHECKs, com mensagem clara."""
    resposta = api.put(macro, mes, ano, valor)
    assert resposta.status_code == 400 and resposta.get_json() == {"erro": erro}


# Herança (ADR-013) -----------------------------------------------------------------------
def test_mes_sem_teto_herda_do_anterior(api):
    """11/2026 sem teto herda 10/2026 (herdado true, origem 10/2026); outras macro seguem null."""
    api.put(1, 10, 2026, 900)
    assert api.teto(1, 11, 2026) == {"valor": 900.0, "herdado": True, "origem_mes": 10, "origem_ano": 2026}
    assert api.teto(2, 11, 2026) == NULO


def test_heranca_cruza_o_ano(api):
    """01/2027 herda de 10/2026."""
    api.put(1, 10, 2026, 900)
    assert api.teto(1, 1, 2027) == {"valor": 900.0, "herdado": True, "origem_mes": 10, "origem_ano": 2026}


def test_nao_herda_do_futuro(api):
    """Com só 10/2026 definido, 07/2026 fica null."""
    api.put(1, 10, 2026, 900)
    assert api.teto(1, 7, 2026) == NULO


def test_herda_o_mais_recente(api):
    """Com 08=500 e 10=900: 11 herda 900 (de 10) e 09 herda 500 (de 08)."""
    api.put(1, 8, 2026, 500)
    api.put(1, 10, 2026, 900)
    assert api.teto(1, 11, 2026)["valor"] == 900.0
    assert api.teto(1, 9, 2026) == {"valor": 500.0, "herdado": True, "origem_mes": 8, "origem_ano": 2026}


def test_get_com_heranca_nao_grava_nada(api, consultar):
    """A herança é calculada em runtime: vários GETs não criam linhas."""
    api.put(1, 10, 2026, 900)
    for mes in (11, 12, 7):
        api.get(mes, 2026)
    api.get(1, 2027)
    assert consultar("SELECT COUNT(*) FROM tetos") == [(1,)]


# DELETE (ADR-014) -------------------------------------------------------------------------
def test_delete_apaga_e_volta_a_null(api):
    """DELETE → 204; sem nada para herdar, o mês volta a null."""
    api.put(1, 10, 2026, 900)
    resposta = api.delete(1, 10, 2026)
    assert resposta.status_code == 204 and resposta.data == b""
    assert api.teto(1, 10, 2026) == NULO


def test_delete_devolve_o_mes_a_heranca(api):
    """Apagar 10/2026 com 08/2026 definido: 10 passa a herdar 500 de 08."""
    api.put(1, 8, 2026, 500)
    api.put(1, 10, 2026, 900)
    api.delete(1, 10, 2026)
    assert api.teto(1, 10, 2026) == {"valor": 500.0, "herdado": True, "origem_mes": 8, "origem_ano": 2026}


def test_delete_inexistente_e_404(api):
    """Não dá para apagar teto que não existe no mês exato (herdado não conta)."""
    api.put(1, 8, 2026, 500)
    resposta = api.delete(1, 10, 2026)
    assert resposta.status_code == 404
    assert resposta.get_json() == {"erro": "nao existe teto definido para esta categoria/mes/ano"}


@pytest.mark.parametrize("query", ["categoria_macro_id=1&ano=2026", "mes=10&ano=2026", "categoria_macro_id=x&mes=10&ano=2026"])
def test_delete_parametros_invalidos_e_400(cliente_flask, query):
    """DELETE sem mes, sem macro ou com macro inválida → 400."""
    assert cliente_flask.delete(f"/tetos?{query}").status_code == 400

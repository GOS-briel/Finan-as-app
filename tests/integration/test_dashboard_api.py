# GET /dashboard: hero, breakdown, "Sem categoria" e últimos lançamentos (Etapa 10, ADRs 021 a 023)
# "Hoje" é 2026-10-22 (fixture hoje_fixo).
import pytest

from app.db import dashboard as db_dashboard
from app.db import lancamentos as db_lancamentos
from app.db import tetos as db_tetos


def _dash(cliente, mes, ano):
    return cliente.get(f"/dashboard?mes={mes}&ano={ano}").get_json()


def _por_macro(corpo, macro_id):
    return next(c for c in corpo["categorias"] if c["categoria_macro"] and c["categoria_macro"]["id"] == macro_id)


def _ordem(corpo):
    return [c["categoria_macro"]["id"] if c["categoria_macro"] else "virtual" for c in corpo["categorias"]]


@pytest.fixture
def agosto(cliente_flask, categorias_popular, lancamento_manual):
    """Agosto/2026 com um caso de cada status (valores documentados na ADR-022)."""
    s = categorias_popular
    lancamento_manual(descricao="TREINO", valor=850, data="2026-08-10", subcategoria_id=s["Equipamento"])  # Esporte 170%
    lancamento_manual(descricao="MERCADO", valor=680, data="2026-08-11", subcategoria_id=s["Mercado"])     # Alimentação 85%
    lancamento_manual(descricao="ROUPA", valor=100, data="2026-08-12", subcategoria_id=s["Roupas"])        # Compras 50%
    lancamento_manual(descricao="CINEMA", valor=30, data="2026-08-13", subcategoria_id=s["Cinema"])        # Lazer 10% (herdado)
    lancamento_manual(descricao="CURSO", valor=20, data="2026-08-14", subcategoria_id=s["Curso"])          # Educação teto 0
    lancamento_manual(descricao="ONIBUS", valor=40, data="2026-08-15", subcategoria_id=s["Onibus"])        # Transporte sem teto
    lancamento_manual(descricao="AVULSO A", valor=25, data="2026-08-16")                                   # Sem categoria
    lancamento_manual(descricao="AVULSO B", valor=15, data="2026-08-16")
    for macro, mes, valor in ((6, 8, 500), (1, 8, 800), (3, 8, 200), (2, 7, 300), (4, 8, 0), (5, 8, 0)):
        assert cliente_flask.put("/tetos", json={"categoria_macro_id": macro, "mes": mes, "ano": 2026, "valor": valor}).status_code == 200
    return _dash(cliente_flask, 8, 2026)


# Validação --------------------------------------------------------------------------------
@pytest.mark.parametrize("query", ["", "mes=13&ano=2026", "mes=10&ano=1999"], ids=["sem-parametros", "mes-13", "ano-1999"])
def test_parametros_invalidos_e_400(cliente_flask, query):
    """mes/ano reaproveitam o validador comum → 400."""
    assert cliente_flask.get(f"/dashboard?{query}").status_code == 400


# Banco vazio ------------------------------------------------------------------------------
def test_banco_vazio(cliente_flask):
    """Hero zerado e sem_teto; 8 macro com gasto 0 e convite; 'Sem categoria' presente com 0/0."""
    corpo = _dash(cliente_flask, 10, 2026)
    assert corpo["hero"] == {"total_gasto": 0, "gasto_com_teto": 0, "gasto_sem_teto": 0, "total_teto": 0,
                             "percentual_uso": None, "status": "sem_teto"}
    assert len(corpo["categorias"]) == 9
    assert all(c["gasto"] == 0 and c["status"] == "sem_teto" and c["convite_definir_teto"] for c in corpo["categorias"][:8])
    virtual = corpo["categorias"][-1]
    assert (virtual["categoria_virtual_nome"], virtual["gasto"], virtual["quantidade"], virtual["convite_definir_teto"]) == (
        "Sem categoria", 0, 0, False)
    assert corpo["ultimos_lancamentos"] == [] and (corpo["mes"], corpo["ano"]) == (10, 2026)


def test_todos_os_itens_tem_as_mesmas_chaves(cliente_flask):
    """Formato fixo: os 9 itens do breakdown têm exatamente as mesmas chaves."""
    corpo = _dash(cliente_flask, 10, 2026)
    assert {tuple(sorted(c)) for c in corpo["categorias"]} == {(
        "categoria_macro", "categoria_virtual_nome", "convite_definir_teto", "diferenca", "gasto", "percentual",
        "quantidade", "status", "teto")}


# Hero (ADR-022) ----------------------------------------------------------------------------
def test_hero_agosto(agosto):
    """total 1760; com teto 1680; sem teto 80; teto 1800 (com herdado); 93.33% quase_no_teto."""
    assert agosto["hero"] == {"total_gasto": 1760.0, "gasto_com_teto": 1680.0, "gasto_sem_teto": 80.0,
                              "total_teto": 1800.0, "percentual_uso": 93.33, "status": "quase_no_teto"}


def test_hero_com_tetos_herdados_e_gasto_so_sem_teto(cliente_flask, agosto, lancamento_manual, categorias_popular):
    """Setembro herda os tetos, mas só tem gasto em Outros (sem teto): 0% folgado."""
    lancamento_manual(descricao="SETEMBRO", valor=50, data="2026-09-05", subcategoria_id=categorias_popular["Diversos"])
    hero = _dash(cliente_flask, 9, 2026)["hero"]
    assert (hero["total_teto"], hero["gasto_com_teto"], hero["gasto_sem_teto"], hero["percentual_uso"], hero["status"]) == (
        1800.0, 0.0, 50.0, 0.0, "folgado")


def test_hero_antes_de_qualquer_teto(cliente_flask, agosto):
    """Junho (sem teto nem herança): percentual null e status sem_teto."""
    hero = _dash(cliente_flask, 6, 2026)["hero"]
    assert hero["percentual_uso"] is None and hero["status"] == "sem_teto"


# Breakdown (ADRs 021 a 023) ----------------------------------------------------------------
def test_ordem_do_breakdown(agosto):
    """Estourados (teto 0 = infinito, depois 170%), quase, folgados por % DESC, sem_teto por id, Sem categoria."""
    assert _ordem(agosto) == [5, 6, 1, 3, 2, 4, 7, 8, "virtual"]


@pytest.mark.parametrize(
    ("macro_id", "esperado"),
    [
        (6, {"gasto": 850.0, "teto": 500.0, "percentual": 170.0, "status": "estourado", "diferenca": -350.0}),
        (1, {"gasto": 680.0, "teto": 800.0, "percentual": 85.0, "status": "quase_no_teto", "diferenca": 120.0}),
        (3, {"gasto": 100.0, "teto": 200.0, "percentual": 50.0, "status": "folgado", "diferenca": 100.0}),
        (2, {"gasto": 30.0, "teto": 300.0, "percentual": 10.0, "status": "folgado", "diferenca": 270.0}),
        (5, {"gasto": 20.0, "teto": 0.0, "percentual": None, "status": "estourado", "diferenca": -20.0}),
        (4, {"gasto": 0.0, "teto": 0.0, "percentual": 0.0, "status": "folgado", "diferenca": 0.0}),
        (7, {"gasto": 40.0, "teto": None, "percentual": None, "status": "sem_teto", "diferenca": None}),
    ],
    ids=["esporte-170", "alimentacao-85", "compras-50", "lazer-herdado-10", "educacao-teto-zero-com-gasto",
         "saude-teto-zero-sem-gasto", "transporte-sem-teto"],
)
def test_itens_do_breakdown(agosto, macro_id, esperado):
    """Gasto, teto, percentual, status e diferença (teto - gasto) de cada caso."""
    item = _por_macro(agosto, macro_id)
    assert {k: item[k] for k in esperado} == esperado


def test_convite_definir_teto(agosto):
    """Convite só nas macro sem teto; nunca na categoria virtual."""
    convites = {c["categoria_macro"]["id"] for c in agosto["categorias"][:8] if c["convite_definir_teto"]}
    assert convites == {7, 8} and agosto["categorias"][-1]["convite_definir_teto"] is False


def test_quantidades_e_sem_categoria(agosto):
    """quantidade por item; 'Sem categoria' com 2 lançamentos e R$ 40."""
    assert _por_macro(agosto, 6)["quantidade"] == 1 and _por_macro(agosto, 8)["quantidade"] == 0
    assert (agosto["quantidade_sem_categoria"], agosto["valor_sem_categoria"]) == (2, 40.0)
    assert agosto["categorias"][-1]["gasto"] == 40.0 and agosto["categorias"][-1]["quantidade"] == 2


def test_sem_categoria_diminui_ao_categorizar_e_some_com_tudo_categorizado(cliente_flask, lancamento_manual, categorias_popular):
    """Categorizar reduz 'Sem categoria'; com tudo categorizado ela continua no fim com 0/0, e o total não muda."""
    a = lancamento_manual(descricao="A", valor=66.66, data="2026-10-01", origem="fatura")
    b = lancamento_manual(descricao="B", valor=33.34, data="2026-10-01", origem="fatura")
    assert (_dash(cliente_flask, 10, 2026)["quantidade_sem_categoria"]) == 2
    cliente_flask.post(f"/lancamentos/{a}/categorizar", json={"subcategoria_id": categorias_popular["Equipamento"]})
    corpo = _dash(cliente_flask, 10, 2026)
    assert (corpo["quantidade_sem_categoria"], corpo["valor_sem_categoria"], corpo["hero"]["total_gasto"]) == (1, 33.34, 100.0)
    cliente_flask.put(f"/lancamentos/{b}", json={"subcategoria_id": categorias_popular["Mercado"]})
    virtual = _dash(cliente_flask, 10, 2026)["categorias"][-1]
    assert (virtual["categoria_virtual_nome"], virtual["gasto"], virtual["quantidade"]) == ("Sem categoria", 0.0, 0)


# Dias restantes -------------------------------------------------------------------------------
@pytest.mark.parametrize(("mes", "ano", "esperado"), [(10, 2026, 9), (9, 2026, 0), (11, 2026, 30)],
                         ids=["mes-atual", "mes-passado", "mes-futuro"])
def test_dias_restantes_pelo_endpoint(cliente_flask, mes, ano, esperado):
    """Com hoje = 22/10/2026: outubro 9, setembro 0, novembro 30."""
    assert _dash(cliente_flask, mes, ano)["dias_restantes_no_mes"] == esperado


# Últimos lançamentos ----------------------------------------------------------------------------
def test_ultimos_lancamentos(cliente_flask, lancamento_manual, categorias_popular):
    """3 itens: data DESC, depois criado_em DESC (antes do id), depois id DESC; formato do GET."""
    importados = [lancamento_manual(descricao=f"IMPORTADO {i}", data="2026-10-01", origem="fatura") for i in range(3)]
    lancamento_manual(descricao="MAIS NOVO", data="2026-10-15", subcategoria_id=categorias_popular["Cinema"],
                      criado_em="2026-10-15T10:00:00")
    lancamento_manual(descricao="CRIADO ANTES", data="2026-10-15", criado_em="2026-10-15T09:00:00")
    ultimos = _dash(cliente_flask, 10, 2026)["ultimos_lancamentos"]
    assert [u["descricao"] for u in ultimos] == ["MAIS NOVO", "CRIADO ANTES", "IMPORTADO 2"]
    assert ultimos[2]["id"] == max(importados)
    assert (ultimos[0]["subcategoria_nome"], ultimos[0]["categoria_macro_nome"]) == ("Cinema", "Lazer")
    lista = cliente_flask.get("/lancamentos?mes=10&ano=2026").get_json()
    assert set(ultimos[0]) == set(lista[0]) and "subcategoria_sugerida" in ultimos[1]


def test_ultimos_com_menos_de_3(cliente_flask, lancamento_manual):
    """Mês com 1 lançamento → 1 item."""
    lancamento_manual(data="2026-09-05")
    assert len(_dash(cliente_flask, 9, 2026)["ultimos_lancamentos"]) == 1


# Desempenho (ADR-021) --------------------------------------------------------------------------
@pytest.fixture
def contar_selects(monkeypatch):
    """Rastreia os SELECTs feitos pelos módulos usados no dashboard."""
    queries = []
    for modulo in (db_dashboard, db_lancamentos, db_tetos):
        original = modulo.conectar

        def rastreado(original=original):
            conexao = original()
            conexao.set_trace_callback(queries.append)
            return conexao

        monkeypatch.setattr(modulo, "conectar", rastreado)
    return lambda: len([q for q in queries if q.lstrip().upper().startswith("SELECT")])


@pytest.mark.parametrize(
    ("mes", "lancamento_sem_categoria_no_mes", "esperado"),
    [(8, False, 15), (10, False, 19), (10, True, 20)],
    ids=["agosto-5-tetos-proprios", "outubro-tudo-herdado-sem-lancamentos", "outubro-tudo-herdado-maximo"],
)
def test_quantidade_de_selects_do_dashboard(cliente_flask, agosto, lancamento_manual, contar_selects,
                                            mes, lancamento_sem_categoria_no_mes, esperado):
    """1 agregada + 1 macros + 1 ou 2 por macro (exato, depois herdado) + últimos + sugestões (só se houver sem categoria); máximo 20."""
    if lancamento_sem_categoria_no_mes:
        lancamento_manual(data="2026-10-05")
    _dash(cliente_flask, mes, 2026)
    assert contar_selects() == esperado

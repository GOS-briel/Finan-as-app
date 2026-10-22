# Validadores de entrada do main.py (Etapas 6, 7 e 8): mensagens claras antes dos CHECKs do schema
from datetime import timedelta

import pytest

import main


# _validar_inteiro --------------------------------------------------------------
@pytest.mark.parametrize(("valor", "esperado"), [(3, 3), ("3", 3), (" 7 ", 7)])
def test_validar_inteiro_aceita_numero_e_texto_numerico(valor, esperado):
    """Form e query string mandam texto: '3' vale 3."""
    assert main._validar_inteiro(valor, "campo") == esperado


@pytest.mark.parametrize(
    ("valor", "mensagem"),
    [(None, "campo e obrigatorio"), ("", "campo e obrigatorio"), (True, "campo deve ser inteiro"),
     (2.5, "campo deve ser inteiro"), ("abc", "campo deve ser inteiro"), ([1], "campo deve ser inteiro")],
    ids=["none", "vazio", "bool", "float", "texto", "lista"],
)
def test_validar_inteiro_recusa(valor, mensagem):
    """Ausente, bool (True seria 1), float e texto não numérico são recusados com mensagem própria."""
    with pytest.raises(ValueError, match=mensagem):
        main._validar_inteiro(valor, "campo")


def test_validar_inteiro_fora_do_intervalo():
    """Fora de [minimo, maximo] informa o intervalo."""
    with pytest.raises(ValueError, match="mes deve estar entre 1 e 12"):
        main._validar_inteiro(13, "mes", 1, 12)


@pytest.mark.parametrize(
    ("mes", "ano", "mensagem"),
    [(0, 2026, "mes deve estar entre 1 e 12"), (13, 2026, "mes deve estar entre 1 e 12"),
     (10, 1999, "ano deve estar entre 2000 e 2100"), (10, 2101, "ano deve estar entre 2000 e 2100")],
)
def test_validar_mes_ano_fronteiras(mes, ano, mensagem):
    """Mês 1-12 e ano 2000-2100 (mesmas regras dos CHECKs do schema)."""
    with pytest.raises(ValueError, match=mensagem):
        main._validar_mes_ano({"mes": mes, "ano": ano})


def test_validar_mes_ano_valido():
    """Mês e ano válidos voltam como inteiros."""
    assert main._validar_mes_ano({"mes": "1", "ano": "2000"}) == (1, 2000)


# _validar_valor ----------------------------------------------------------------
@pytest.mark.parametrize(("valor", "esperado"), [(800, 800.0), ("350.5", 350.5), (0, 0.0), (123.456, 123.46)])
def test_validar_valor_aceita_e_arredonda(valor, esperado):
    """Número ou texto numérico >= 0, arredondado a 2 casas."""
    assert main._validar_valor(valor) == esperado


@pytest.mark.parametrize(
    ("valor", "mensagem"),
    [(None, "obrigatorio"), ("", "obrigatorio"), (True, "deve ser numero"), ("abc", "deve ser numero"),
     ("nan", "deve ser numero"), ("inf", "deve ser numero"), (-10, "nao pode ser negativo"), ({}, "deve ser numero")],
)
def test_validar_valor_recusa(valor, mensagem):
    """Ausente, bool, texto, NaN, infinito e negativo são recusados."""
    with pytest.raises(ValueError, match=mensagem):
        main._validar_valor(valor)


# _validar_texto ----------------------------------------------------------------
def test_validar_texto_tira_espacos_e_respeita_limite():
    """Espaços das pontas saem; exatamente o limite passa, 1 a mais não."""
    assert main._validar_texto("  Uber  ", "descricao", 200, obrigatorio=True) == "Uber"
    assert main._validar_texto("x" * 50, "nome", 50, obrigatorio=True) == "x" * 50
    with pytest.raises(ValueError, match="nome deve ter no maximo 50 caracteres"):
        main._validar_texto("x" * 51, "nome", 50, obrigatorio=True)


@pytest.mark.parametrize(("valor", "mensagem"), [("", "nao pode ser vazio"), ("   ", "nao pode ser vazio"), (None, "deve ser texto"), (5, "deve ser texto")])
def test_validar_texto_obrigatorio_recusa(valor, mensagem):
    """Texto obrigatório vazio, só espaços ou de outro tipo é recusado."""
    with pytest.raises(ValueError, match=mensagem):
        main._validar_texto(valor, "descricao", 200, obrigatorio=True)


@pytest.mark.parametrize("valor", [None, "", "   "])
def test_validar_texto_opcional_vazio_vira_none(valor):
    """Nota vazia ou ausente vira None (limpa o campo)."""
    assert main._validar_texto(valor, "nota", 500, obrigatorio=False) is None


# Datas -------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("valor", "mensagem"),
    [(None, "data e obrigatoria"), ("21/10/2026", "formato AAAA-MM-DD"), ("20261021", "formato AAAA-MM-DD"),
     ("2026-W43-3", "formato AAAA-MM-DD"), ("2026-02-30", "data invalida"), (20261021, "formato AAAA-MM-DD")],
    ids=["ausente", "formato-br", "sem-hifens", "semana-iso", "dia-impossivel", "numero"],
)
def test_validar_formato_data_recusa(valor, mensagem):
    """Só AAAA-MM-DD estrito (fromisoformat sozinho aceitaria '20261021' e '2026-W43-3')."""
    with pytest.raises(ValueError, match=mensagem):
        main._validar_formato_data(valor)


@pytest.mark.parametrize("dias_atras", [0, 89, 90])
def test_janela_aceita_hoje_ate_90_dias(hoje_fixo, dias_atras):
    """Hoje, 89 e 90 dias atrás são aceitos (o limite é '> 90 dias')."""
    main._validar_janela_data((hoje_fixo - timedelta(days=dias_atras)).isoformat())


def test_janela_recusa_91_dias_e_futuro():
    """91 dias atrás e amanhã são recusados (ADR-015)."""
    with pytest.raises(ValueError, match="anterior a 90 dias"):
        main._validar_janela_data("2026-07-22")
    with pytest.raises(ValueError, match="nao pode ser futura"):
        main._validar_janela_data("2026-10-23")


@pytest.mark.parametrize(("valor", "esperado"), [(None, None), ("", None), ("4", 4), (4, 4)])
def test_validar_subcategoria_id(valor, esperado):
    """null/'' significam 'sem subcategoria'; números viram int."""
    assert main._validar_subcategoria_id(valor) == esperado

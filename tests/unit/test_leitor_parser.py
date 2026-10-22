# Parser da fatura (Etapas 1, 2 e 5.3) sem o PDF real: o pdfplumber é simulado com texto controlado
import pytest

from app.fatura import leitor


class _PaginaFalsa:
    """Imita page do pdfplumber: crop() devolve a si mesma e extract_text() o texto dado."""

    def __init__(self, texto):
        self.texto = texto
        self.height = 800
        self.recortes = []

    def crop(self, caixa):
        self.recortes.append(caixa)
        return self

    def extract_text(self):
        return self.texto


class _PdfFalso:
    def __init__(self, textos):
        self.pages = [_PaginaFalsa(texto) for texto in textos]

    def __enter__(self):
        return self

    def __exit__(self, *erro):
        return False


@pytest.fixture
def pdf_com(mocker):
    """Faz pdfplumber.open devolver páginas com os textos dados."""

    def configurar(*textos):
        pdf = _PdfFalso(textos)
        mocker.patch.object(leitor.pdfplumber, "open", return_value=pdf)
        return pdf

    return configurar


# _converter_valor ------------------------------------------------------------
@pytest.mark.parametrize(("texto", "esperado"), [("1.940,44", 1940.44), ("3,85", 3.85), ("1.234.567,89", 1234567.89)])
def test_converter_valor(texto, esperado):
    """Valor no formato brasileiro vira float."""
    assert leitor._converter_valor(texto) == esperado


# _detectar_parcela -------------------------------------------------------------
@pytest.mark.parametrize(
    ("descricao", "esperado"),
    [
        ("DECATHLON 05/06 NITEROI", ("DECATHLON NITEROI - Parcela 5/6", 5, 6)),
        ("MIINA DA PRATA PLAZA05/06 NITEROI", ("MIINA DA PRATA PLAZA NITEROI - Parcela 5/6", 5, 6)),
        ("RENNER 03/03 CABREUVA", ("RENNER CABREUVA - Parcela 3/3", 3, 3)),
        ("CONTA VIVO SAO PAULO", ("CONTA VIVO SAO PAULO", None, None)),
        ("LOJA 15/03 CENTRO", ("LOJA 15/03 CENTRO", None, None)),
        ("LOJA 00/03 CENTRO", ("LOJA 00/03 CENTRO", None, None)),
        ("CODIGO 123/456 X", ("CODIGO 123/456 X", None, None)),
    ],
    ids=["com-espacos", "colado-no-nome", "ultima-parcela", "sem-parcela",
         "atual-maior-que-total", "parcela-zero", "numero-maior-nao-e-parcela"],
)
def test_detectar_parcela(descricao, esperado):
    """Detecta 'DD/DD' como parcela só quando 1 <= atual <= total, inclusive colado no nome."""
    assert leitor._detectar_parcela(descricao) == esperado


# extrair_lancamentos ------------------------------------------------------------
def test_extrai_despesas_e_ignora_creditos(pdf_com):
    """Linha com valor terminado em '-' (pagamento/crédito) não entra na lista."""
    pdf_com("08/05 DECATHLON 05/06 NITEROI 66,66\n10/09 PAGAMENTO RECEBIDO 1.940,44-\n12/09 PADARIA 12,50")
    assert leitor.extrair_lancamentos("x.pdf") == [
        {"data": "08/05", "descricao": "DECATHLON NITEROI - Parcela 5/6", "valor": 66.66,
         "parcela_atual": 5, "parcela_total": 6},
        {"data": "12/09", "descricao": "PADARIA", "valor": 12.5, "parcela_atual": None, "parcela_total": None},
    ]


def test_ignora_linhas_sem_data_ou_sem_valor(pdf_com):
    """Cabeçalhos, linhas sem 'DD/MM ' no início e descrição quebrada sem valor são ignorados."""
    pdf_com("Total da fatura R$ 100,00\n15/09 DESCRICAO QUEBRADA SEM VALOR\nTEXTO 15/09 5,00\n16/09 LOJA 5,00")
    resultado = leitor.extrair_lancamentos("x.pdf")
    assert [item["descricao"] for item in resultado] == ["LOJA"]


def test_le_todas_as_paginas_recortando_a_coluna_esquerda(pdf_com):
    """Cada página é recortada em x < 358 e as páginas não grudam a última linha na primeira."""
    pdf = pdf_com("01/09 PRIMEIRA 1,00", "02/09 SEGUNDA 2,00", None)
    resultado = leitor.extrair_lancamentos("x.pdf")
    assert [item["descricao"] for item in resultado] == ["PRIMEIRA", "SEGUNDA"]
    assert all(pagina.recortes == [(0, 0, 358, 800)] for pagina in pdf.pages)


# Cabeçalho: competência e total ----------------------------------------------------
CABECALHO = (
    "Total de fatura Vencimento Limite de compras Limite de Saque\n"
    "R$ 1.699,21 10/10/2026 R$ 7.200,00 R$ 1.080,00\n"
    "A previsão de fechamento da sua próxima fatura é dia27/10/2026"
)


def test_competencia_vem_do_vencimento(mocker):
    """Vencimento 10/10/2026 no cabeçalho vira {mes: 10, ano: 2026} (ADR-009)."""
    mocker.patch.object(leitor, "_texto_primeira_pagina", return_value=CABECALHO)
    assert leitor.extrair_competencia("x.pdf") == {"mes": 10, "ano": 2026}


def test_total_vem_do_cabecalho(mocker):
    """'Total de fatura' na linha de cima, valor na de baixo."""
    mocker.patch.object(leitor, "_texto_primeira_pagina", return_value=CABECALHO)
    assert leitor.extrair_total_fatura("x.pdf") == 1699.21


@pytest.mark.parametrize(
    "texto", ["Fatura sem cabeçalho conhecido", "Vencimento\nR$ 1,00 10/13/2026"],
    ids=["sem-vencimento", "mes-invalido"],
)
def test_competencia_nao_detectada_retorna_none(mocker, texto):
    """Sem vencimento reconhecível (ou mês fora de 1-12), retorna None para o fallback 422."""
    mocker.patch.object(leitor, "_texto_primeira_pagina", return_value=texto)
    assert leitor.extrair_competencia("x.pdf") is None


def test_total_nao_encontrado_retorna_none(mocker):
    """Sem 'Total de fatura', o total é None (e total_confere fica null na API)."""
    mocker.patch.object(leitor, "_texto_primeira_pagina", return_value="outro layout")
    assert leitor.extrair_total_fatura("x.pdf") is None


def test_texto_da_primeira_pagina_sem_recorte(pdf_com):
    """O cabeçalho é lido da página 1 inteira; página sem texto vira string vazia."""
    pdf_com(CABECALHO, "pagina 2")
    assert leitor._texto_primeira_pagina("x.pdf") == CABECALHO
    pdf_com(None)
    assert leitor._texto_primeira_pagina("x.pdf") == ""

# POST /fatura/importar sem o PDF real: o parser é simulado (Etapas 4 e 5.3, ADR-009/010)
import io

import pytest

import main

EXTRAIDOS = [
    {"data": "08/05", "descricao": "LOJA A - Parcela 5/6", "valor": 66.66, "parcela_atual": 5, "parcela_total": 6},
    {"data": "12/09", "descricao": "LOJA B", "valor": 33.34, "parcela_atual": None, "parcela_total": None},
]


@pytest.fixture
def parser_simulado(mocker):
    """Substitui as 3 funções do parser no main; devolve os mocks para ajustar por teste."""
    return {
        "lancamentos": mocker.patch.object(main, "extrair_lancamentos", return_value=EXTRAIDOS),
        "competencia": mocker.patch.object(main, "extrair_competencia", return_value={"mes": 10, "ano": 2026}),
        "total": mocker.patch.object(main, "extrair_total_fatura", return_value=100.0),
    }


def _enviar(cliente, conteudo=b"%PDF-falso", nome="fatura.pdf", **campos):
    return cliente.post("/fatura/importar", data={"arquivo": (io.BytesIO(conteudo), nome), **campos},
                        content_type="multipart/form-data")


# Validação do upload ------------------------------------------------------------
def test_sem_arquivo_retorna_400(cliente_flask):
    """POST sem o campo 'arquivo' → 400 'nenhum arquivo enviado'."""
    resposta = cliente_flask.post("/fatura/importar")
    assert resposta.status_code == 400 and resposta.get_json() == {"erro": "nenhum arquivo enviado"}


def test_arquivo_sem_nome_retorna_400(cliente_flask):
    """Formulário enviado sem escolher arquivo (filename vazio) → 400."""
    assert _enviar(cliente_flask, nome="").status_code == 400


@pytest.mark.parametrize("nome", ["fatura.txt", "fatura.pdf.exe", "fatura"])
def test_extensao_diferente_de_pdf_retorna_400(cliente_flask, nome):
    """Só .pdf (sem diferenciar maiúsculas) é aceito."""
    resposta = _enviar(cliente_flask, nome=nome)
    assert resposta.status_code == 400 and resposta.get_json() == {"erro": "arquivo deve ser PDF"}


def test_extensao_pdf_maiuscula_e_aceita(cliente_flask, parser_simulado):
    """'FATURA.PDF' passa pela validação de extensão."""
    assert _enviar(cliente_flask, nome="FATURA.PDF").status_code == 200


def test_arquivo_que_nao_e_pdf_de_verdade_retorna_500_e_limpa_o_temporario(cliente_flask):
    """Texto com extensão .pdf quebra o parser real → 500, e o temporário é apagado (fixture vigia)."""
    resposta = _enviar(cliente_flask, conteudo=b"isto nao e um pdf")
    assert resposta.status_code == 500 and resposta.get_json() == {"erro": "falha ao processar fatura"}


# Competência --------------------------------------------------------------------
def test_competencia_do_pdf(cliente_flask, parser_simulado):
    """Sem mes/ano no formulário, usa o detectado no PDF, com fonte 'pdf' e data AAAA-MM-01."""
    corpo = _enviar(cliente_flask).get_json()
    assert corpo["competencia"] == {"mes": 10, "ano": 2026, "fonte": "pdf"}
    assert {item["data"] for item in corpo["lancamentos"]} == {"2026-10-01"}


def test_formulario_tem_prioridade_sobre_o_pdf(cliente_flask, parser_simulado):
    """mes/ano do formulário vencem o PDF (fonte 'formulario')."""
    corpo = _enviar(cliente_flask, mes="9", ano="2026").get_json()
    assert corpo["competencia"] == {"mes": 9, "ano": 2026, "fonte": "formulario"}


@pytest.mark.parametrize(
    "campos",
    [{"mes": "13", "ano": "2026"}, {"mes": "10"}, {"ano": "2026"}, {"mes": "abc", "ano": "2026"}, {"mes": "10", "ano": "1999"}],
    ids=["mes-13", "so-mes", "so-ano", "mes-texto", "ano-1999"],
)
def test_mes_ano_invalidos_no_formulario_retornam_400(cliente_flask, parser_simulado, campos):
    """mes/ano incompletos ou fora do intervalo → 400 'mes/ano invalidos'."""
    resposta = _enviar(cliente_flask, **campos)
    assert resposta.status_code == 400 and resposta.get_json() == {"erro": "mes/ano invalidos"}


def test_sem_competencia_detectada_pede_ao_usuario(cliente_flask, parser_simulado, consultar):
    """PDF sem vencimento e sem mes/ano no formulário → 422 com pedir_do_usuario, nada gravado."""
    parser_simulado["competencia"].return_value = None
    resposta = _enviar(cliente_flask)
    assert resposta.status_code == 422
    assert resposta.get_json() == {"erro": "nao foi possivel detectar o mes/ano", "pedir_do_usuario": True}
    assert consultar("SELECT COUNT(*) FROM lancamentos") == [(0,)]


def test_sem_competencia_no_pdf_mas_com_formulario_funciona(cliente_flask, parser_simulado):
    """O fallback do 422: o usuário informa mes/ano e a importação segue."""
    parser_simulado["competencia"].return_value = None
    assert _enviar(cliente_flask, mes="10", ano="2026").status_code == 200


# Resposta e persistência -------------------------------------------------------------
def test_resposta_traz_contagens_e_conferencia_do_total(cliente_flask, parser_simulado):
    """quantidade/inseridos/ignorados, total das despesas e total_confere com o cabeçalho."""
    corpo = _enviar(cliente_flask).get_json()
    assert (corpo["quantidade_total"], corpo["inseridos"], corpo["ignorados_duplicata"]) == (2, 2, 0)
    assert corpo["total_despesas"] == 100.0 and corpo["total_fatura_pdf"] == 100.0 and corpo["total_confere"] is True
    assert [item["status"] for item in corpo["lancamentos"]] == ["inserido", "inserido"]


def test_total_divergente_e_sinalizado(cliente_flask, parser_simulado):
    """Se o parser perder linhas, a soma não bate com o cabeçalho: total_confere false."""
    parser_simulado["total"].return_value = 150.0
    assert _enviar(cliente_flask).get_json()["total_confere"] is False


def test_total_ausente_no_cabecalho_deixa_conferencia_null(cliente_flask, parser_simulado):
    """Sem total no cabeçalho, total_confere é null (não dá para conferir)."""
    parser_simulado["total"].return_value = None
    assert _enviar(cliente_flask).get_json()["total_confere"] is None


def test_reimportacao_nao_duplica(cliente_flask, parser_simulado, consultar):
    """Mesmo conteúdo duas vezes: 2ª importação ignora tudo (ADR-010)."""
    _enviar(cliente_flask)
    corpo = _enviar(cliente_flask).get_json()
    assert (corpo["inseridos"], corpo["ignorados_duplicata"]) == (0, 2)
    assert consultar("SELECT COUNT(*) FROM lancamentos") == [(2,)]


def test_erro_ao_gravar_retorna_500_sem_gravar_nada(cliente_flask, parser_simulado, mocker, consultar):
    """Falha no banco durante a gravação → 500 'falha ao salvar...' e nenhum lançamento fica."""
    mocker.patch.object(main.lancamentos, "salvar_lancamentos_fatura", side_effect=RuntimeError("disco cheio"))
    resposta = _enviar(cliente_flask)
    assert resposta.status_code == 500 and resposta.get_json() == {"erro": "falha ao salvar lancamentos no banco"}
    assert consultar("SELECT COUNT(*) FROM lancamentos") == [(0,)]


def test_importacao_e_atomica(cliente_flask, parser_simulado, consultar):
    """Erro no meio da gravação desfaz tudo: ou entra a fatura inteira, ou nada (ADR-010)."""
    # O 3º item viola o NOT NULL de descricao: os 2 primeiros já tinham sido inseridos na transação
    parser_simulado["lancamentos"].return_value = EXTRAIDOS + [
        {"data": "13/09", "descricao": None, "valor": 1.0, "parcela_atual": None, "parcela_total": None}]
    resposta = _enviar(cliente_flask)
    assert resposta.status_code == 500
    assert consultar("SELECT COUNT(*) FROM lancamentos") == [(0,)]

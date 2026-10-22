# Gravação da importação no banco: data da competência e deduplicação por contagem (ADR-007, ADR-010)
from app.db.lancamentos import salvar_lancamentos_fatura


def _item(descricao, valor, parcela_atual=None, parcela_total=None):
    return {"descricao": descricao, "valor": valor, "parcela_atual": parcela_atual, "parcela_total": parcela_total}


CAFE = _item("CAFE DA ESQUINA NITEROI", 8.0)
PADARIA = _item("PADARIA NITEROI", 12.5)


def _status(resultado):
    return [item["status"] for item in resultado]


def test_primeira_importacao_insere_tudo_com_data_do_mes(banco_temporario, consultar):
    """Lançamentos da fatura são gravados com data AAAA-MM-01, origem fatura e sem categoria."""
    resultado = salvar_lancamentos_fatura([CAFE, PADARIA], 10, 2026)
    assert _status(resultado) == ["inserido", "inserido"]
    assert {item["data"] for item in resultado} == {"2026-10-01"}
    assert consultar("SELECT data, origem, subcategoria_id FROM lancamentos") == [
        ("2026-10-01", "fatura", None), ("2026-10-01", "fatura", None)]


def test_dois_cafes_iguais_na_mesma_fatura_entram_os_dois(banco_temporario, consultar):
    """Dois lançamentos idênticos legítimos não são tratados como duplicata (bug dos cafés)."""
    resultado = salvar_lancamentos_fatura([CAFE, CAFE, PADARIA], 10, 2026)
    assert _status(resultado) == ["inserido", "inserido", "inserido"]
    assert consultar("SELECT COUNT(*) FROM lancamentos WHERE descricao LIKE 'CAFE%'") == [(2,)]


def test_reimportacao_da_mesma_fatura_nao_duplica(banco_temporario, consultar):
    """Reimportar a mesma fatura ignora tudo (n - m = 0 para cada chave)."""
    salvar_lancamentos_fatura([CAFE, CAFE, PADARIA], 10, 2026)
    resultado = salvar_lancamentos_fatura([CAFE, CAFE, PADARIA], 10, 2026)
    assert _status(resultado) == ["ignorado_duplicata"] * 3
    assert consultar("SELECT COUNT(*) FROM lancamentos") == [(3,)]


def test_ocorrencia_nova_de_chave_repetida_entra(banco_temporario, consultar):
    """Se o PDF passa a ter 3 cafés e o banco tem 2, só o 3º entra."""
    salvar_lancamentos_fatura([CAFE, CAFE], 10, 2026)
    resultado = salvar_lancamentos_fatura([CAFE, CAFE, CAFE, PADARIA], 10, 2026)
    assert _status(resultado) == ["ignorado_duplicata", "ignorado_duplicata", "inserido", "inserido"]
    assert consultar("SELECT COUNT(*) FROM lancamentos WHERE descricao LIKE 'CAFE%'") == [(3,)]


def test_nao_parcelado_e_reconhecido_como_duplicata(banco_temporario):
    """A busca usa IS nas parcelas: NULL = NULL não seria verdadeiro com '='."""
    salvar_lancamentos_fatura([CAFE], 10, 2026)
    assert _status(salvar_lancamentos_fatura([CAFE], 10, 2026)) == ["ignorado_duplicata"]


def test_parcelas_diferentes_nao_sao_duplicata(banco_temporario):
    """Mesma loja e valor, mas parcela 5/6 e 6/6, são lançamentos distintos."""
    salvar_lancamentos_fatura([_item("LOJA X", 50.0, 5, 6)], 10, 2026)
    assert _status(salvar_lancamentos_fatura([_item("LOJA X", 50.0, 6, 6)], 10, 2026)) == ["inserido"]


def test_mesmo_lancamento_em_outro_mes_nao_e_duplicata(banco_temporario):
    """A data (competência) faz parte da chave: a mesma assinatura em novembro entra."""
    salvar_lancamentos_fatura([CAFE], 10, 2026)
    assert _status(salvar_lancamentos_fatura([CAFE], 11, 2026)) == ["inserido"]


def test_lancamento_manual_identico_nao_conta_como_duplicata(banco_temporario, lancamento_manual):
    """Só origem 'fatura' entra na contagem: um manual igual não bloqueia a importação."""
    lancamento_manual(descricao=CAFE["descricao"], valor=8.0, data="2026-10-01", origem="manual")
    assert _status(salvar_lancamentos_fatura([CAFE], 10, 2026)) == ["inserido"]

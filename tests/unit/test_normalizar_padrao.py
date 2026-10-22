# Normalização da chave de aprendizado (ADR-008, estendida pela ADR-019)
import pytest

from app.db.aprendizados import normalizar_padrao


@pytest.mark.parametrize(
    ("descricao", "esperado"),
    [
        ("DECATHLON NITEROI - Parcela 5/6", "decathlon niteroi"),
        ("DECATHLON NITEROI - Parcela 6/6", "decathlon niteroi"),
        ("LOJAS RIACHUELO SAO PAULO - Parcela 3/4", "lojas riachuelo sao paulo"),
        ("ACAI DA BARRA NITEROI", "acai da barra niteroi"),
        ("ANTHROPIC* CLAUDE SUB 110,00ANTHROPIC.C", "anthropic* claude sub 110,00anthropic.c"),
        ("UBER 12,50", "uber"),
        ("POSTO SHELL 1.234,56 789", "posto shell"),
        ("Padaria  Central ", "padaria central"),
        ("99Food *KiDelicia Pizza e Rio de Janeir", "99food *kidelicia pizza e rio de janeir"),
        ("123", "123"),
    ],
    ids=["parcela-5-6", "parcela-6-6", "parcela-3-4", "sem-mudanca", "numero-colado-nao-corta",
         "numero-solto-com-virgula", "varios-numeros-soltos", "espacos-e-maiusculas",
         "numero-no-inicio-fica", "so-numero-sem-espaco-fica"],
)
def test_normalizar_padrao(descricao, esperado):
    """A descrição vira a chave de aprendizado esperada."""
    assert normalizar_padrao(descricao) == esperado


def test_parcelas_diferentes_da_mesma_compra_tem_o_mesmo_padrao():
    """Parcelas 5/6 e 6/6 da mesma loja geram a mesma chave (match entre meses)."""
    assert normalizar_padrao("DECATHLON NITEROI - Parcela 5/6") == normalizar_padrao("DECATHLON NITEROI - Parcela 6/6")


def test_cidades_diferentes_nao_se_misturam():
    """Mesma loja em outra cidade é outro padrão (ADR-008, opção B)."""
    assert normalizar_padrao("DECATHLON RIO") != normalizar_padrao("DECATHLON NITEROI")


def test_maiusculas_com_acento_casam():
    """'AÇAÍ' e 'açaí' viram a mesma chave (casefold trata acentuadas)."""
    assert normalizar_padrao("AÇAÍ") == normalizar_padrao("açaí")

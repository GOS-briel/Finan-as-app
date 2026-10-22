# Comparação e ordenação de nomes de subcategoria (ADR-012)
import pytest

from app.db.categorias import _chave_ordenacao, _comparavel


@pytest.mark.parametrize(("a", "b"), [("Delivery", "DELIVERY"), ("AÇAÍ", "açaí"), ("ç", "ç")],
                         ids=["maiusculas", "acentuadas", "unicode-composto-vs-decomposto"])
def test_comparavel_ignora_maiusculas(a, b):
    """Nomes que só diferem em maiúsculas (ou na forma Unicode) colidem."""
    assert _comparavel(a) == _comparavel(b)


def test_comparavel_mantem_acentos():
    """'Acai' e 'Açaí' são nomes diferentes (só a ordenação ignora acentos)."""
    assert _comparavel("Acai") != _comparavel("Açaí")


def test_ordenacao_natural():
    """Sem acento e sem maiúsculas: Água não vai para depois de Zoológico."""
    nomes = ["Zoológico", "bar", "Água", "Delivery", "açaí", "Restaurante"]
    assert sorted(nomes, key=_chave_ordenacao) == ["açaí", "Água", "bar", "Delivery", "Restaurante", "Zoológico"]

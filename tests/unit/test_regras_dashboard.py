# Regras puras do dashboard: status por threshold e dias restantes (ADR-021, ADR-022)
from datetime import date

import pytest

from app.db.dashboard import THRESHOLD_QUASE_NO_TETO, classificar, dias_restantes_no_mes


def test_threshold_e_80_por_cento():
    """O threshold de 'quase no teto' é a constante 0.80."""
    assert THRESHOLD_QUASE_NO_TETO == 0.80


@pytest.mark.parametrize(
    ("gasto", "teto", "esperado"),
    [
        (850, 500, (170.0, "estourado")),
        (680, 800, (85.0, "quase_no_teto")),
        (100, 200, (50.0, "folgado")),
        (79.99, 100, (79.99, "folgado")),
        (80, 100, (80.0, "quase_no_teto")),
        (100, 100, (100.0, "quase_no_teto")),
        (100.01, 100, (100.01, "estourado")),
        (100.004, 100, (100.0, "estourado")),
        (0, None, (None, "sem_teto")),
        (40, None, (None, "sem_teto")),
        (0, 0, (0.0, "folgado")),
        (20, 0, (None, "estourado")),
    ],
    ids=["170", "85", "50", "79.99-fronteira", "80-fronteira", "100-exato", "100.01", "100.004-arredonda-mas-estoura",
         "sem-teto-zero-gasto", "sem-teto-com-gasto", "teto-zero-sem-gasto", "teto-zero-com-gasto"],
)
def test_classificar(gasto, teto, esperado):
    """(percentual, status) pela razão sem arredondar; teto 0 com gasto é estouro com percentual null."""
    assert classificar(gasto, teto) == esperado


HOJE = date(2026, 10, 22)


@pytest.mark.parametrize(
    ("mes", "ano", "hoje", "esperado"),
    [(10, 2026, HOJE, 9), (9, 2026, HOJE, 0), (10, 2025, HOJE, 0), (11, 2026, HOJE, 30),
     (2, 2028, HOJE, 29), (2, 2027, HOJE, 28), (12, 2026, date(2026, 12, 31), 0), (10, 2026, date(2026, 10, 1), 30)],
    ids=["mes-atual", "mes-passado", "ano-passado", "mes-futuro", "fev-bissexto", "fev-comum", "ultimo-dia", "primeiro-dia"],
)
def test_dias_restantes_no_mes(mes, ano, hoje, esperado):
    """Passado: 0; atual: último dia - hoje; futuro: o mês inteiro."""
    assert dias_restantes_no_mes(mes, ano, hoje) == esperado

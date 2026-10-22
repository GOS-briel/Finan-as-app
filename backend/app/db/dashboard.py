# Dashboard: visão agregada do mês
#
# Hero (total do mês vs orçamento), breakdown pelas 8 macro + a categoria
# virtual "Sem categoria", e os últimos lançamentos (ADRs 021 a 023).
#
# Queries por chamada (típico ~20, todas num SQLite local):
#   1  gasto e quantidade por macro, numa query agrupada (inclui "Sem categoria")
#   17 tetos efetivos via tetos.listar_tetos (1 + 2 por macro: exato e herdado)
#   2  últimos lançamentos (1) + sugestões em lote (1)
# Reaproveitar listar_tetos mantém a regra de herança (ADR-013) num lugar só.

import calendar
from datetime import date

from app.db import lancamentos, tetos
from app.db.inicializar import conectar

# A partir de 80% do teto, a categoria está "quase no teto" (ADR-022)
THRESHOLD_QUASE_NO_TETO = 0.80

NOME_SEM_CATEGORIA = "Sem categoria"

# Ordem dos grupos no breakdown (ADR-023)
ORDEM_STATUS = {"estourado": 0, "quase_no_teto": 1, "folgado": 2, "sem_teto": 3}


def classificar(gasto: float, teto: float | None) -> tuple[float | None, str]:
    """
    (percentual, status) de um gasto contra um teto (ADR-022).
    O status usa a razão SEM arredondar; o percentual arredondado é só
    para exibição (evita 100,004% aparecer como 100.0 e "estourado").
    """
    if teto is None:
        return None, "sem_teto"
    if teto == 0:  # teto zero = "não gastar nada" (ADR-013)
        return (0.0, "folgado") if gasto == 0 else (None, "estourado")  # None = infinito
    razao = gasto / teto
    if razao > 1:
        status = "estourado"
    elif razao >= THRESHOLD_QUASE_NO_TETO:
        status = "quase_no_teto"
    else:
        status = "folgado"
    return round(razao * 100, 2), status


def dias_restantes_no_mes(mes: int, ano: int, hoje: date) -> int:
    """Mês passado: 0. Mês atual: último dia - hoje. Mês futuro: o mês inteiro."""
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    if (ano, mes) < (hoje.year, hoje.month):
        return 0
    if (ano, mes) == (hoje.year, hoje.month):
        return ultimo_dia - hoje.day
    return ultimo_dia


def _gastos_por_macro(mes: int, ano: int) -> dict:
    """{macro_id ou None (sem categoria): (gasto, quantidade)} numa query só."""
    inicio, fim = lancamentos.intervalo_do_mes(mes, ano)
    conexao = conectar()
    try:
        linhas = conexao.execute(
            """
            SELECT m.id, SUM(l.valor), COUNT(*)
            FROM lancamentos l
            LEFT JOIN subcategorias s ON s.id = l.subcategoria_id
            LEFT JOIN categorias_macro m ON m.id = s.categoria_macro_id
            WHERE l.data >= ? AND l.data < ?
            GROUP BY m.id
            """,
            (inicio, fim),
        ).fetchall()
    finally:
        conexao.close()
    return {macro_id: (round(soma, 2), quantidade) for macro_id, soma, quantidade in linhas}


def _chave_ordenacao(item: dict):
    """Grupo do status; dentro dele, percentual DESC (null = infinito); depois id."""
    percentual = item["percentual"]
    return (
        ORDEM_STATUS[item["status"]],
        -(percentual if percentual is not None else float("inf")),
        item["categoria_macro"]["id"],
    )


def montar_dashboard(mes: int, ano: int, hoje: date) -> dict:
    gastos = _gastos_por_macro(mes, ano)

    categorias = []
    for linha in tetos.listar_tetos(mes, ano):
        macro = linha["categoria_macro"]
        gasto, quantidade = gastos.get(macro["id"], (0.0, 0))
        teto = linha["valor"]
        percentual, status = classificar(gasto, teto)
        categorias.append({
            "categoria_macro": macro,
            "categoria_virtual_nome": None,
            "gasto": gasto,
            "quantidade": quantidade,
            "teto": teto,
            "percentual": percentual,
            "status": status,
            "diferenca": None if teto is None else round(teto - gasto, 2),  # + sobrou, - estourou
            "convite_definir_teto": teto is None,
        })
    categorias.sort(key=_chave_ordenacao)

    # Categoria virtual: não existe em categorias_macro, sempre no fim
    valor_sem_categoria, quantidade_sem_categoria = gastos.get(None, (0.0, 0))
    categorias.append({
        "categoria_macro": None,
        "categoria_virtual_nome": NOME_SEM_CATEGORIA,
        "gasto": valor_sem_categoria,
        "quantidade": quantidade_sem_categoria,
        "teto": None,
        "percentual": None,
        "status": "sem_teto",
        "diferenca": None,
        "convite_definir_teto": False,
    })

    # Hero (fluxo completo na ADR-022)
    com_teto = [c for c in categorias if c["teto"] is not None]
    total_gasto = round(sum(gasto for gasto, _ in gastos.values()), 2)        # 1. tudo que saiu
    gasto_com_teto = round(sum(c["gasto"] for c in com_teto), 2)               # 2. só macro com teto
    total_teto = round(sum(c["teto"] for c in com_teto), 2)                    # 3. só tetos existentes
    gasto_sem_teto = round(total_gasto - gasto_com_teto, 2)                    # 4.
    if total_teto == 0:                                                        # 5.
        percentual_uso, status_hero = None, "sem_teto"
    else:                                                                      # 6.
        percentual_uso, status_hero = classificar(gasto_com_teto, total_teto)

    return {
        "mes": mes,
        "ano": ano,
        "dias_restantes_no_mes": dias_restantes_no_mes(mes, ano, hoje),
        "hero": {
            "total_gasto": total_gasto,
            "gasto_com_teto": gasto_com_teto,
            "gasto_sem_teto": gasto_sem_teto,
            "total_teto": total_teto,
            "percentual_uso": percentual_uso,
            "status": status_hero,
        },
        "quantidade_sem_categoria": quantidade_sem_categoria,
        "valor_sem_categoria": valor_sem_categoria,
        "categorias": categorias,
        "ultimos_lancamentos": lancamentos.ultimos_lancamentos(mes, ano, limite=3),
    }

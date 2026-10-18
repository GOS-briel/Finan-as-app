# Persistência de lançamentos
#
# SQL puro com sqlite3 (ADR-004). Sempre parâmetros "?", nunca SQL
# montado com concatenação de strings.

from collections import Counter
from datetime import datetime

from app.db.inicializar import conectar

# "IS" em vez de "=" nas parcelas: em SQL, "NULL = NULL" não é verdadeiro,
# então lançamentos não parcelados nunca seriam reconhecidos como duplicata
SQL_CONTAR_IGUAIS = """
    SELECT COUNT(*) FROM lancamentos
    WHERE origem = 'fatura' AND descricao = ? AND valor = ? AND data = ?
      AND parcela_atual IS ? AND parcela_total IS ?
"""

SQL_INSERIR = """
    INSERT INTO lancamentos
        (data, descricao, valor, subcategoria_id, parcela_atual, parcela_total,
         origem, criado_em)
    VALUES (?, ?, ?, NULL, ?, ?, 'fatura', ?)
"""


def salvar_lancamentos_fatura(lancamentos: list[dict], mes: int, ano: int) -> list[dict]:
    """
    Grava os lançamentos da fatura com data AAAA-MM-01 (ADR-007).

    Deduplicação por contagem (ADR-010): se uma chave aparece n vezes no PDF
    e já existe m vezes no banco, insere só n - m. Assim dois lançamentos
    iguais legítimos (ex: dois cafés de mesmo valor no mês) entram os dois,
    e reimportar a mesma fatura não duplica nada.

    Tudo numa transação só: se der erro, nada é gravado.
    Retorna os lançamentos com a data gravada e "status"
    ("inserido" ou "ignorado_duplicata").
    """
    data = f"{ano:04d}-{mes:02d}-01"
    criado_em = datetime.now().isoformat(timespec="seconds")
    ja_no_banco = {}  # chave -> m (contado antes de inserir qualquer uma dessa chave)
    vistos_no_pdf = Counter()  # chave -> quantas já foram processadas
    resultado = []

    conexao = conectar()
    try:
        with conexao:  # commit no fim, rollback se der exceção
            for item in lancamentos:
                chave = (
                    item["descricao"], item["valor"],
                    item["parcela_atual"], item["parcela_total"],
                )
                if chave not in ja_no_banco:
                    ja_no_banco[chave] = conexao.execute(
                        SQL_CONTAR_IGUAIS,
                        (item["descricao"], item["valor"], data,
                         item["parcela_atual"], item["parcela_total"]),
                    ).fetchone()[0]
                vistos_no_pdf[chave] += 1

                if vistos_no_pdf[chave] > ja_no_banco[chave]:
                    conexao.execute(
                        SQL_INSERIR,
                        (data, item["descricao"], item["valor"],
                         item["parcela_atual"], item["parcela_total"], criado_em),
                    )
                    status = "inserido"
                else:
                    status = "ignorado_duplicata"
                resultado.append({**item, "data": data, "status": status})
    finally:
        conexao.close()
    return resultado

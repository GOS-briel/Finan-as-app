# Persistência de lançamentos
#
# SQL puro com sqlite3 (ADR-004). Sempre parâmetros "?", nunca SQL
# montado com concatenação de valores.
#
# - Importação da fatura com deduplicação por contagem (ADR-010)
# - CRUD de lançamentos: manuais editáveis; importados só permitem
#   alterar subcategoria e nota (ADR-016). DELETE é definitivo.
# - Categorização com aprendizado e sugestões (ADRs 017 a 020)
#
# Erros viram exceções próprias; o main.py traduz cada uma para HTTP.

import sqlite3
from collections import Counter
from datetime import datetime

from app.db import aprendizados
from app.db.inicializar import conectar


class LancamentoNaoEncontrado(Exception):
    pass


class SubcategoriaNaoEncontrada(Exception):
    pass


class EdicaoBloqueada(Exception):
    def __init__(self, campos: list[str]):
        super().__init__(f"campos bloqueados: {campos}")
        self.campos = campos


# Únicos campos que um cliente pode enviar; o resto (id, origem,
# parcelas, criado_em) nunca é editável
CAMPOS_EDITAVEIS = ("data", "descricao", "valor", "subcategoria_id", "nota")
# Em importados também são bloqueados: são a chave de deduplicação (ADR-010)
CAMPOS_BLOQUEADOS_EM_IMPORTADOS = ("descricao", "valor", "data")

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


# LEFT JOIN: lançamento sem subcategoria continua na lista, com os campos
# de categoria em null (com JOIN simples, os não categorizados sumiriam)
SQL_SELECIONAR = """
    SELECT l.id, l.data, l.descricao, l.valor,
           l.subcategoria_id, s.nome AS subcategoria_nome,
           m.id AS categoria_macro_id, m.nome AS categoria_macro_nome,
           l.parcela_atual, l.parcela_total, l.origem, l.nota, l.criado_em
    FROM lancamentos l
    LEFT JOIN subcategorias s ON s.id = l.subcategoria_id
    LEFT JOIN categorias_macro m ON m.id = s.categoria_macro_id
"""


def _conectar_com_dicts() -> sqlite3.Connection:
    conexao = conectar()
    conexao.row_factory = sqlite3.Row  # linhas acessíveis por nome de coluna
    return conexao


def _enriquecer_com_sugestoes(conexao, lista: list[dict]) -> list[dict]:
    """
    Acrescenta "subcategoria_sugerida" em todos os lançamentos (ADR-018):
    sugestão do aprendizado para os sem categoria, null para o resto.
    Uma única query em aprendizados para a lista inteira.
    """
    padroes = {
        item["id"]: aprendizados.normalizar_padrao(item["descricao"])
        for item in lista if item["subcategoria_id"] is None
    }
    sugestoes = aprendizados.buscar_sugestoes_batch(conexao, padroes.values())
    for item in lista:
        padrao = padroes.get(item["id"])
        item["subcategoria_sugerida"] = sugestoes.get(padrao) if padrao is not None else None
    return lista


def _buscar(conexao, lancamento_id: int) -> dict:
    linha = conexao.execute(SQL_SELECIONAR + " WHERE l.id = ?", (lancamento_id,)).fetchone()
    if linha is None:
        raise LancamentoNaoEncontrado()
    # Mesmo formato do GET em qualquer resposta de lançamento único
    return _enriquecer_com_sugestoes(conexao, [dict(linha)])[0]


def _garantir_subcategoria(conexao, subcategoria_id: int) -> None:
    existe = conexao.execute(
        "SELECT 1 FROM subcategorias WHERE id = ?", (subcategoria_id,)
    ).fetchone()
    if existe is None:
        raise SubcategoriaNaoEncontrada()


def intervalo_do_mes(mes: int, ano: int) -> tuple[str, str]:
    """("2026-10-01", "2026-11-01"): filtro "data >= inicio AND data < fim"."""
    inicio = f"{ano:04d}-{mes:02d}-01"
    fim = f"{ano + 1:04d}-01-01" if mes == 12 else f"{ano:04d}-{mes + 1:02d}-01"
    return inicio, fim


def listar_lancamentos(mes: int, ano: int, categoria_macro_id: int | None = None,
                       origem: str | None = None, sem_categoria: bool = False) -> list[dict]:
    """
    Lançamentos do mês/ano, mais recentes primeiro, com sugestão de
    subcategoria para os não categorizados. Filtros opcionais.
    """
    inicio, fim = intervalo_do_mes(mes, ano)
    condicoes, parametros = ["l.data >= ?", "l.data < ?"], [inicio, fim]
    if categoria_macro_id is not None:
        condicoes.append("m.id = ?")
        parametros.append(categoria_macro_id)
    if origem is not None:
        condicoes.append("l.origem = ?")
        parametros.append(origem)
    if sem_categoria:
        condicoes.append("l.subcategoria_id IS NULL")

    conexao = _conectar_com_dicts()
    try:
        linhas = conexao.execute(
            SQL_SELECIONAR + " WHERE " + " AND ".join(condicoes)
            + " ORDER BY l.data DESC, l.id DESC",
            parametros,
        ).fetchall()
        return _enriquecer_com_sugestoes(conexao, [dict(linha) for linha in linhas])
    finally:
        conexao.close()


def ultimos_lancamentos(mes: int, ano: int, limite: int = 3) -> list[dict]:
    """
    Os mais recentes do mês, no mesmo formato do GET /lancamentos.
    id DESC desempata: importados da mesma fatura têm a mesma data e o
    mesmo criado_em (gravados no mesmo segundo).
    """
    inicio, fim = intervalo_do_mes(mes, ano)
    conexao = _conectar_com_dicts()
    try:
        linhas = conexao.execute(
            SQL_SELECIONAR
            + " WHERE l.data >= ? AND l.data < ?"
            + " ORDER BY l.data DESC, l.criado_em DESC, l.id DESC LIMIT ?",
            (inicio, fim, limite),
        ).fetchall()
        return _enriquecer_com_sugestoes(conexao, [dict(linha) for linha in linhas])
    finally:
        conexao.close()


def buscar_lancamento(lancamento_id: int) -> dict:
    conexao = _conectar_com_dicts()
    try:
        return _buscar(conexao, lancamento_id)
    finally:
        conexao.close()


def criar_lancamento_manual(data: str, descricao: str, valor: float,
                            subcategoria_id: int | None, nota: str | None) -> dict:
    """Origem sempre 'manual' e sem parcelas (não há parcelamento manual na v1)."""
    conexao = _conectar_com_dicts()
    try:
        with conexao:
            if subcategoria_id is not None:
                _garantir_subcategoria(conexao, subcategoria_id)
            cursor = conexao.execute(
                """
                INSERT INTO lancamentos
                    (data, descricao, valor, subcategoria_id, parcela_atual,
                     parcela_total, origem, nota, criado_em)
                VALUES (?, ?, ?, ?, NULL, NULL, 'manual', ?, ?)
                """,
                (data, descricao, valor, subcategoria_id, nota,
                 datetime.now().isoformat(timespec="seconds")),
            )
            return _buscar(conexao, cursor.lastrowid)
    finally:
        conexao.close()


def atualizar_lancamento(lancamento_id: int, alteracoes: dict) -> dict:
    """
    Aplica só os campos que MUDARAM (o main.py compara com o valor atual,
    então reenviar o objeto inteiro não conta como alteração).
    Importado (origem 'fatura'): alterar descricao, valor ou data levanta
    EdicaoBloqueada (ADR-016).
    """
    conexao = _conectar_com_dicts()
    try:
        with conexao:
            linha = conexao.execute(
                "SELECT origem FROM lancamentos WHERE id = ?", (lancamento_id,)
            ).fetchone()
            if linha is None:
                raise LancamentoNaoEncontrado()
            if linha["origem"] == "fatura":
                bloqueados = [c for c in CAMPOS_BLOQUEADOS_EM_IMPORTADOS if c in alteracoes]
                if bloqueados:
                    raise EdicaoBloqueada(bloqueados)
            if alteracoes.get("subcategoria_id") is not None:
                _garantir_subcategoria(conexao, alteracoes["subcategoria_id"])

            # Nomes de coluna vêm da lista fixa CAMPOS_EDITAVEIS, nunca do
            # cliente; valores sempre por "?"
            colunas = [c for c in CAMPOS_EDITAVEIS if c in alteracoes]
            if colunas:
                conexao.execute(
                    f"UPDATE lancamentos SET {', '.join(f'{c} = ?' for c in colunas)} WHERE id = ?",
                    [alteracoes[c] for c in colunas] + [lancamento_id],
                )
            return _buscar(conexao, lancamento_id)
    finally:
        conexao.close()


def categorizar_lancamento(lancamento_id: int, subcategoria_id: int | None) -> tuple[dict, dict]:
    """
    Categoriza (ou descategoriza, com None) E aprende (ADR-017, ADR-019).
    Tudo numa transação: nunca fica lançamento categorizado sem o
    aprendizado correspondente, nem o contrário.
    Retorna (lancamento, {"acao", "confianca"}).
    """
    conexao = _conectar_com_dicts()
    try:
        with conexao:
            linha = conexao.execute(
                "SELECT descricao, subcategoria_id FROM lancamentos WHERE id = ?",
                (lancamento_id,),
            ).fetchone()
            if linha is None:
                raise LancamentoNaoEncontrado()
            if subcategoria_id is not None:
                _garantir_subcategoria(conexao, subcategoria_id)
            subcategoria_anterior = linha["subcategoria_id"]

            conexao.execute(
                "UPDATE lancamentos SET subcategoria_id = ? WHERE id = ?",
                (subcategoria_id, lancamento_id),
            )

            padrao = aprendizados.normalizar_padrao(linha["descricao"])
            if not padrao:
                aprendizado = {"acao": "nenhuma", "confianca": None}
            elif subcategoria_id is None:
                aprendizado = aprendizados.apagar_aprendizado(conexao, padrao, subcategoria_anterior)
            else:
                aprendizado = aprendizados.upsert_aprendizado(
                    conexao, padrao, subcategoria_id,
                    lancamento_ja_estava_nela=(subcategoria_anterior == subcategoria_id),
                )
            return _buscar(conexao, lancamento_id), aprendizado
    finally:
        conexao.close()


def apagar_lancamento(lancamento_id: int) -> None:
    """DELETE definitivo, de qualquer origem (sem lixeira nem restauração)."""
    conexao = conectar()
    try:
        with conexao:
            cursor = conexao.execute("DELETE FROM lancamentos WHERE id = ?", (lancamento_id,))
            if cursor.rowcount == 0:
                raise LancamentoNaoEncontrado()
    finally:
        conexao.close()

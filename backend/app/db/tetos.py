# Tetos de orçamento por categoria macro e mês/ano
#
# SQL puro com sqlite3 (ADR-004). Teto por mês/ano (ADR-006).
# Mês sem teto herda o do mês anterior mais recente, calculado na hora
# da consulta e nunca gravado no banco (ADR-013). PUT e DELETE agem só
# no mês/ano exato (ADR-014).
#
# Erros viram exceções próprias; o main.py traduz cada uma para HTTP.

from app.db.inicializar import conectar


class MacroNaoEncontrada(Exception):
    pass


class TetoNaoEncontrado(Exception):
    pass


SQL_TETO_EXATO = """
    SELECT valor, mes, ano FROM tetos
    WHERE categoria_macro_id = ? AND mes = ? AND ano = ?
"""

# Mais recente estritamente ANTES de mes/ano: nunca herda de mês futuro
SQL_TETO_ANTERIOR = """
    SELECT valor, mes, ano FROM tetos
    WHERE categoria_macro_id = ?
      AND (ano < ? OR (ano = ? AND mes < ?))
    ORDER BY ano DESC, mes DESC
    LIMIT 1
"""


def listar_tetos(mes: int, ano: int) -> list[dict]:
    """
    Uma linha por categoria macro (ordem de id, ADR-005) com o teto do
    mês/ano: o definido, o herdado do mês anterior mais recente, ou null.
    """
    conexao = conectar()
    try:
        resultado = []
        macros = conexao.execute(
            "SELECT id, nome FROM categorias_macro ORDER BY id"
        ).fetchall()
        for macro_id, nome in macros:
            # 1-2. Teto definido para o mês/ano exato
            linha = conexao.execute(SQL_TETO_EXATO, (macro_id, mes, ano)).fetchone()
            herdado = False
            # 3-4. Senão, herda o mais recente anterior
            if linha is None:
                linha = conexao.execute(
                    SQL_TETO_ANTERIOR, (macro_id, ano, ano, mes)
                ).fetchone()
                herdado = linha is not None
            # 5. Nada definido nem para herdar: valor e origem ficam null
            valor, origem_mes, origem_ano = linha if linha else (None, None, None)
            resultado.append({
                "categoria_macro": {"id": macro_id, "nome": nome},
                "valor": valor,
                "herdado": herdado,
                "origem_mes": origem_mes,
                "origem_ano": origem_ano,
            })
    finally:
        conexao.close()
    return resultado


def definir_teto(categoria_macro_id: int, mes: int, ano: int, valor: float) -> dict:
    """Upsert: cria o teto do mês/ano ou atualiza o valor se já existir."""
    conexao = conectar()
    try:
        with conexao:
            existe = conexao.execute(
                "SELECT 1 FROM categorias_macro WHERE id = ?", (categoria_macro_id,)
            ).fetchone()
            if existe is None:
                raise MacroNaoEncontrada()
            # Atômico: usa o UNIQUE (categoria_macro_id, mes, ano) do schema,
            # sem a janela entre "SELECT para ver se existe" e INSERT/UPDATE
            conexao.execute(
                """
                INSERT INTO tetos (categoria_macro_id, mes, ano, valor)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (categoria_macro_id, mes, ano)
                DO UPDATE SET valor = excluded.valor
                """,
                (categoria_macro_id, mes, ano, valor),
            )
    finally:
        conexao.close()
    return {"valor": valor, "categoria_macro_id": categoria_macro_id, "mes": mes, "ano": ano}


def apagar_teto(categoria_macro_id: int, mes: int, ano: int) -> None:
    """Apaga só o teto do mês/ano exato. O GET passa a mostrar a herança."""
    conexao = conectar()
    try:
        with conexao:
            cursor = conexao.execute(
                "DELETE FROM tetos WHERE categoria_macro_id = ? AND mes = ? AND ano = ?",
                (categoria_macro_id, mes, ano),
            )
            if cursor.rowcount == 0:
                raise TetoNaoEncontrado()
    finally:
        conexao.close()

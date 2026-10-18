# Inicialização do banco SQLite
#
# Cria as tabelas a partir do schema.sql e popula as 8 categorias macro
# fixas (ADR-005). Pode rodar várias vezes sem duplicar nada.
#
# Uso: python backend/app/db/inicializar.py

import sqlite3
from pathlib import Path

PASTA_DB = Path(__file__).parent
CAMINHO_BANCO = PASTA_DB / "financas.db"
CAMINHO_SCHEMA = PASTA_DB / "schema.sql"

CATEGORIAS_MACRO = [
    "Alimentação",
    "Lazer",
    "Compras",
    "Saúde",
    "Educação",
    "Esporte",
    "Transporte",
    "Outros",
]


def conectar() -> sqlite3.Connection:
    """Abre o banco com foreign keys ligadas (o SQLite vem com elas desligadas)."""
    conexao = sqlite3.connect(CAMINHO_BANCO)
    # O PRAGMA vale só para esta conexão, por isso fica aqui e não no schema
    conexao.execute("PRAGMA foreign_keys = ON")
    return conexao


def criar_banco() -> None:
    """Executa o schema.sql (CREATE TABLE IF NOT EXISTS)."""
    schema = CAMINHO_SCHEMA.read_text(encoding="utf-8")
    conexao = conectar()
    conexao.executescript(schema)
    conexao.close()


def popular_categorias_macro() -> int:
    """Insere as categorias macro que ainda não existem. Retorna quantas entraram."""
    conexao = conectar()
    with conexao:
        inseridas = 0
        for nome in CATEGORIAS_MACRO:
            cursor = conexao.execute(
                "INSERT OR IGNORE INTO categorias_macro (nome) VALUES (?)", (nome,)
            )
            inseridas += cursor.rowcount
    conexao.close()
    return inseridas


def main() -> None:
    print(f"Banco: {CAMINHO_BANCO}")

    criar_banco()
    conexao = conectar()
    tabelas = conexao.execute(
        "SELECT COUNT(*) FROM sqlite_master "
        "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).fetchone()[0]
    print(f"Schema aplicado ({tabelas} tabelas).")

    inseridas = popular_categorias_macro()
    total = conexao.execute("SELECT COUNT(*) FROM categorias_macro").fetchone()[0]
    conexao.close()
    print(f"Categorias macro: {inseridas} inseridas ({total} no total).")


if __name__ == "__main__":
    main()

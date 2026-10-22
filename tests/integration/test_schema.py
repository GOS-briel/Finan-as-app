# Schema SQLite e inicialização (Etapa 5.2, ADR-005/006): agora no banco temporário, não no real
import sqlite3

import pytest

import main
from app.db import inicializar

MACROS = ["Alimentação", "Lazer", "Compras", "Saúde", "Educação", "Esporte", "Transporte", "Outros"]


def test_cria_as_5_tabelas(consultar):
    """O schema cria as 5 tabelas na ordem das dependências."""
    tabelas = consultar("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY rowid")
    assert [nome for (nome,) in tabelas] == ["categorias_macro", "subcategorias", "tetos", "lancamentos", "aprendizados"]


def test_popula_as_8_macro_na_ordem_canonica(consultar):
    """As 8 macro fixas entram com ids 1-8 e acentos corretos."""
    assert consultar("SELECT id, nome FROM categorias_macro ORDER BY id") == list(enumerate(MACROS, 1))


def test_inicializar_e_idempotente(banco_temporario, consultar):
    """Rodar de novo não duplica macro nem dá erro (IF NOT EXISTS + INSERT OR IGNORE)."""
    inicializar.criar_banco()
    assert inicializar.popular_categorias_macro() == 0
    assert consultar("SELECT COUNT(*) FROM categorias_macro") == [(8,)]


def test_conectar_liga_foreign_keys(banco_temporario):
    """PRAGMA foreign_keys vale por conexão: conectar() sempre liga."""
    conexao = inicializar.conectar()
    try:
        assert conexao.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        conexao.close()


@pytest.mark.parametrize(
    ("sql", "parametros"),
    [
        ("INSERT INTO subcategorias (nome, categoria_macro_id) VALUES ('x', 999)", ()),
        ("INSERT INTO tetos (categoria_macro_id, mes, ano, valor) VALUES (999, 10, 2026, 1)", ()),
        ("INSERT INTO lancamentos (data, descricao, valor, subcategoria_id, origem, criado_em) "
         "VALUES ('2026-10-01', 'x', 1, 999, 'manual', 'agora')", ()),
    ],
    ids=["subcategoria-macro-inexistente", "teto-macro-inexistente", "lancamento-sub-inexistente"],
)
def test_foreign_key_inexistente_e_bloqueada(banco_temporario, sql, parametros):
    """Referência a id inexistente falha com FOREIGN KEY constraint failed."""
    conexao = inicializar.conectar()
    try:
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            conexao.execute(sql, parametros)
    finally:
        conexao.close()


@pytest.mark.parametrize(
    ("mes", "valor", "mensagem"),
    [(13, 500.0, "mes BETWEEN 1 AND 12"), (0, 500.0, "mes BETWEEN 1 AND 12"), (10, -100.0, "valor >= 0")],
)
def test_checks_de_tetos(banco_temporario, mes, valor, mensagem):
    """CHECKs do schema barram mês fora de 1-12 e teto negativo (rede de segurança)."""
    conexao = inicializar.conectar()
    try:
        with pytest.raises(sqlite3.IntegrityError, match=mensagem):
            conexao.execute("INSERT INTO tetos (categoria_macro_id, mes, ano, valor) VALUES (1, ?, 2026, ?)", (mes, valor))
    finally:
        conexao.close()


def test_check_de_origem_do_lancamento(banco_temporario):
    """Origem só pode ser 'manual' ou 'fatura'."""
    conexao = inicializar.conectar()
    try:
        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            conexao.execute("INSERT INTO lancamentos (data, descricao, valor, origem, criado_em) "
                            "VALUES ('2026-10-01', 'x', 1, 'outra', 'agora')")
    finally:
        conexao.close()


def test_banco_inexistente_e_criado_na_primeira_requisicao(tmp_path, monkeypatch):
    """before_request cria o banco (schema + 8 macro) se o arquivo não existe."""
    caminho = tmp_path / "novo.db"
    monkeypatch.setattr(inicializar, "CAMINHO_BANCO", caminho)
    assert not caminho.exists()
    resposta = main.app.test_client().get("/categorias/macro")
    assert resposta.status_code == 200 and len(resposta.get_json()) == 8
    assert caminho.exists()


def test_health_check(cliente_flask):
    """A rota raiz responde, servindo de health check."""
    resposta = cliente_flask.get("/")
    assert resposta.status_code == 200 and "controle financeiro" in resposta.get_data(as_text=True)

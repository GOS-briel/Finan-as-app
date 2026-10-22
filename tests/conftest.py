# Fixtures compartilhadas da suíte (ADR-024).
#
# Regras gerais:
# - Todo teste que toca o banco usa `banco_temporario`: o financas.db real
#   nunca é aberto (conectar() lê inicializar.CAMINHO_BANCO na hora da chamada).
# - "Hoje" é congelado em HOJE_FIXO para todos os testes (janela de 90 dias,
#   dias restantes do dashboard): a suíte não quebra ao virar o mês.
# - A pasta temporária usada pelo app é vigiada: sobrou PDF, o teste falha.
# - A fatura real só existe na máquina do dev (FATURA_PDF_PATH); sem ela,
#   os testes que a usam são pulados (caso do CI).

import io
import os
import tempfile
from datetime import date
from pathlib import Path

import pytest

import main
from app.db import inicializar

HOJE_FIXO = date(2026, 10, 22)
FATURA_PDF_PATH = os.environ.get("FATURA_PDF_PATH")


class _DataFixa(date):
    """date com today() congelado; o resto (fromisoformat, comparações) é o normal."""

    @classmethod
    def today(cls):
        return cls(HOJE_FIXO.year, HOJE_FIXO.month, HOJE_FIXO.day)


@pytest.fixture(autouse=True)
def hoje_fixo(monkeypatch):
    """Congela date.today() do main.py em HOJE_FIXO."""
    monkeypatch.setattr(main, "date", _DataFixa)
    return HOJE_FIXO


@pytest.fixture(autouse=True)
def pasta_temp_monitorada(tmp_path_factory, monkeypatch):
    """O app grava o PDF do upload aqui; no fim, nenhum .pdf pode ter sobrado."""
    pasta = tmp_path_factory.mktemp("temp_do_app")
    monkeypatch.setattr(tempfile, "tempdir", str(pasta))
    yield pasta
    sobras = sorted(p.name for p in pasta.glob("*.pdf"))
    assert not sobras, f"arquivos temporários não foram apagados: {sobras}"


@pytest.fixture
def banco_temporario(tmp_path, monkeypatch):
    """SQLite novo (schema + 8 macro) num diretório temporário, apagado no fim."""
    caminho = tmp_path / "teste.db"
    monkeypatch.setattr(inicializar, "CAMINHO_BANCO", caminho)
    inicializar.main()
    yield caminho
    caminho.unlink(missing_ok=True)


@pytest.fixture
def cliente_flask(banco_temporario):
    """Cliente de teste do Flask, apontando para o banco temporário."""
    main.app.config["TESTING"] = True
    return main.app.test_client()


@pytest.fixture
def categorias_popular(cliente_flask):
    """Uma subcategoria por macro (+ Restaurante em Alimentação). Retorna {nome: id}."""
    nomes = [
        ("Mercado", 1), ("Restaurante", 1), ("Cinema", 2), ("Roupas", 3), ("Farmacia", 4),
        ("Curso", 5), ("Equipamento", 6), ("Onibus", 7), ("Diversos", 8),
    ]
    ids = {}
    for nome, macro in nomes:
        resposta = cliente_flask.post("/subcategorias", json={"nome": nome, "categoria_macro_id": macro})
        assert resposta.status_code == 201
        ids[nome] = resposta.get_json()["id"]
    return ids


@pytest.fixture
def lancamento_manual(banco_temporario):
    """
    Factory: insere um lançamento direto no banco e retorna o id.
    Direto no SQL para permitir datas fora da janela de 90 dias e
    origem "fatura" sem precisar do PDF.
    """

    def criar(descricao="LANCAMENTO TESTE", valor=10.0, data="2026-10-22", subcategoria_id=None,
              origem="manual", parcela_atual=None, parcela_total=None, nota=None,
              criado_em="2026-10-22T12:00:00"):
        conexao = inicializar.conectar()
        try:
            with conexao:
                cursor = conexao.execute(
                    """
                    INSERT INTO lancamentos (data, descricao, valor, subcategoria_id, parcela_atual,
                                             parcela_total, origem, nota, criado_em)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (data, descricao, valor, subcategoria_id, parcela_atual, parcela_total,
                     origem, nota, criado_em),
                )
                return cursor.lastrowid
        finally:
            conexao.close()

    return criar


@pytest.fixture
def consultar(banco_temporario):
    """Executa um SELECT no banco temporário e devolve todas as linhas."""

    def executar(sql, parametros=()):
        conexao = inicializar.conectar()
        try:
            return conexao.execute(sql, parametros).fetchall()
        finally:
            conexao.close()

    return executar


@pytest.fixture
def fatura_teste():
    """Caminho do PDF real da fatura (FATURA_PDF_PATH). Sem ele, o teste é pulado."""
    if not FATURA_PDF_PATH or not Path(FATURA_PDF_PATH).is_file():
        pytest.skip("FATURA_PDF_PATH não definida (fatura real só existe na máquina do dev)")
    return Path(FATURA_PDF_PATH)


@pytest.fixture
def importar(cliente_flask):
    """Envia um PDF para /fatura/importar. Retorna a resposta do Flask."""

    def enviar(caminho_pdf, **campos):
        conteudo = Path(caminho_pdf).read_bytes()
        return cliente_flask.post(
            "/fatura/importar",
            data={"arquivo": (io.BytesIO(conteudo), "fatura.pdf"), **campos},
            content_type="multipart/form-data",
        )

    return enviar


def pytest_collection_modifyitems(items):
    """Marca com fatura_real todo teste que usa a fixture fatura_teste (filtro: -m fatura_real)."""
    for item in items:
        if "fatura_teste" in getattr(item, "fixturenames", ()):
            item.add_marker(pytest.mark.fatura_real)

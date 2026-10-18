-- Schema do banco SQLite do app de finanças.
-- Decisões em DECISOES.md (ADRs 004 a 008).
-- IF NOT EXISTS: pode rodar de novo sem erro e sem apagar dados.
-- Atenção: as foreign keys só valem com "PRAGMA foreign_keys = ON",
-- que precisa ser executado em cada conexão (ver inicializar.conectar).

-- ADR-005: 8 categorias macro fixas
CREATE TABLE IF NOT EXISTS categorias_macro (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL UNIQUE
);

-- ADR-005: subcategorias customizáveis, sempre ligadas a uma macro
CREATE TABLE IF NOT EXISTS subcategorias (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    nome               TEXT NOT NULL,
    categoria_macro_id INTEGER NOT NULL,
    FOREIGN KEY (categoria_macro_id) REFERENCES categorias_macro(id),
    UNIQUE (nome, categoria_macro_id)
);

-- ADR-006: teto por categoria macro, por mês/ano
CREATE TABLE IF NOT EXISTS tetos (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    categoria_macro_id INTEGER NOT NULL,
    mes                INTEGER NOT NULL,
    ano                INTEGER NOT NULL,
    valor              REAL NOT NULL,
    FOREIGN KEY (categoria_macro_id) REFERENCES categorias_macro(id),
    UNIQUE (categoria_macro_id, mes, ano),
    CHECK (mes BETWEEN 1 AND 12),
    CHECK (valor >= 0)
);

-- ADR-007: data no formato YYYY-MM-DD (fatura = primeiro dia do mês)
-- ADR-002: parcelas registradas no mês da fatura
CREATE TABLE IF NOT EXISTS lancamentos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    data            TEXT NOT NULL,
    descricao       TEXT NOT NULL,
    valor           REAL NOT NULL,
    subcategoria_id INTEGER,
    parcela_atual   INTEGER,
    parcela_total   INTEGER,
    origem          TEXT NOT NULL CHECK (origem IN ('manual', 'fatura')),
    nota            TEXT,
    criado_em       TEXT NOT NULL,
    FOREIGN KEY (subcategoria_id) REFERENCES subcategorias(id)
);

-- ADR-008: padrão = descrição limpa (sem " - Parcela X/Y")
CREATE TABLE IF NOT EXISTS aprendizados (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    padrao_descricao TEXT NOT NULL UNIQUE,
    subcategoria_id  INTEGER NOT NULL,
    confianca        INTEGER NOT NULL DEFAULT 1,
    criado_em        TEXT NOT NULL,
    atualizado_em    TEXT NOT NULL,
    FOREIGN KEY (subcategoria_id) REFERENCES subcategorias(id)
);

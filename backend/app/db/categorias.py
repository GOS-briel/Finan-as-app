# Categorias macro e subcategorias
#
# SQL puro com sqlite3 (ADR-004). As macro são fixas (ADR-005): aqui só
# são lidas. O CRUD é das subcategorias (ADRs 011 e 012).
#
# Erros viram exceções próprias; o main.py traduz cada uma para HTTP.

import sqlite3
import unicodedata

from app.db.inicializar import conectar


class MacroNaoEncontrada(Exception):
    pass


class SubcategoriaNaoEncontrada(Exception):
    pass


class NomeDuplicado(Exception):
    pass


class SubcategoriaEmUso(Exception):
    def __init__(self, lancamentos: int, aprendizados: int):
        super().__init__(f"{lancamentos} lancamentos e {aprendizados} aprendizados vinculados")
        self.lancamentos = lancamentos
        self.aprendizados = aprendizados


def _comparavel(nome: str) -> str:
    """Forma usada para detectar duplicata: ignora maiúsculas/minúsculas."""
    # NFC: "ç" pode vir como 1 caractere ou como "c" + cedilha; aqui viram iguais
    return unicodedata.normalize("NFC", nome).casefold()


def _chave_ordenacao(nome: str) -> str:
    """"Água" -> "agua": sem acento e sem maiúsculas, para ordem alfabética natural."""
    decomposto = unicodedata.normalize("NFKD", nome)
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    return sem_acento.casefold()


def _nome_em_uso(conexao, nome: str, categoria_macro_id: int, ignorar_id: int | None = None) -> bool:
    """
    True se já existe outra subcategoria com esse nome na mesma macro,
    sem diferenciar maiúsculas/minúsculas. O UNIQUE do schema diferencia,
    e COLLATE NOCASE não trata letras acentuadas (ADR-012).
    """
    alvo = _comparavel(nome)
    linhas = conexao.execute(
        "SELECT id, nome FROM subcategorias WHERE categoria_macro_id = ?",
        (categoria_macro_id,),
    )
    return any(_comparavel(n) == alvo and i != ignorar_id for i, n in linhas)


def listar_macros_com_subcategorias() -> list[dict]:
    """
    Macro em ordem de id (ordem canônica da ADR-005), cada uma com as suas
    subcategorias em ordem alfabética natural.
    """
    conexao = conectar()
    try:
        macros = [
            {"id": id_, "nome": nome, "subcategorias": []}
            for id_, nome in conexao.execute("SELECT id, nome FROM categorias_macro ORDER BY id")
        ]
        por_id = {macro["id"]: macro for macro in macros}
        for id_, nome, macro_id in conexao.execute(
            "SELECT id, nome, categoria_macro_id FROM subcategorias"
        ):
            por_id[macro_id]["subcategorias"].append({"id": id_, "nome": nome})
    finally:
        conexao.close()

    # Ordena no Python: o ORDER BY do SQLite poria "Água" depois de "Zoo"
    for macro in macros:
        macro["subcategorias"].sort(key=lambda sub: _chave_ordenacao(sub["nome"]))
    return macros


def criar_subcategoria(nome: str, categoria_macro_id: int) -> dict:
    conexao = conectar()
    try:
        with conexao:
            existe = conexao.execute(
                "SELECT 1 FROM categorias_macro WHERE id = ?", (categoria_macro_id,)
            ).fetchone()
            if existe is None:
                raise MacroNaoEncontrada()
            if _nome_em_uso(conexao, nome, categoria_macro_id):
                raise NomeDuplicado()
            cursor = conexao.execute(
                "INSERT INTO subcategorias (nome, categoria_macro_id) VALUES (?, ?)",
                (nome, categoria_macro_id),
            )
            return {"id": cursor.lastrowid, "nome": nome, "categoria_macro_id": categoria_macro_id}
    except sqlite3.IntegrityError as erro:
        # Rede de segurança: o UNIQUE do schema também barra o nome exato
        if "UNIQUE" in str(erro):
            raise NomeDuplicado() from erro
        raise
    finally:
        conexao.close()


def renomear_subcategoria(subcategoria_id: int, nome: str) -> dict:
    conexao = conectar()
    try:
        with conexao:
            linha = conexao.execute(
                "SELECT categoria_macro_id FROM subcategorias WHERE id = ?", (subcategoria_id,)
            ).fetchone()
            if linha is None:
                raise SubcategoriaNaoEncontrada()
            categoria_macro_id = linha[0]
            # ignorar_id: renomear para o próprio nome (ou mudar só maiúsculas) é permitido
            if _nome_em_uso(conexao, nome, categoria_macro_id, ignorar_id=subcategoria_id):
                raise NomeDuplicado()
            conexao.execute(
                "UPDATE subcategorias SET nome = ? WHERE id = ?", (nome, subcategoria_id)
            )
            return {"id": subcategoria_id, "nome": nome, "categoria_macro_id": categoria_macro_id}
    except sqlite3.IntegrityError as erro:
        if "UNIQUE" in str(erro):
            raise NomeDuplicado() from erro
        raise
    finally:
        conexao.close()


def deletar_subcategoria(subcategoria_id: int) -> None:
    """Só apaga se nada aponta para ela: nada é deletado silenciosamente (ADR-011)."""
    conexao = conectar()
    try:
        with conexao:
            existe = conexao.execute(
                "SELECT 1 FROM subcategorias WHERE id = ?", (subcategoria_id,)
            ).fetchone()
            if existe is None:
                raise SubcategoriaNaoEncontrada()
            lancamentos = conexao.execute(
                "SELECT COUNT(*) FROM lancamentos WHERE subcategoria_id = ?", (subcategoria_id,)
            ).fetchone()[0]
            aprendizados = conexao.execute(
                "SELECT COUNT(*) FROM aprendizados WHERE subcategoria_id = ?", (subcategoria_id,)
            ).fetchone()[0]
            if lancamentos or aprendizados:
                raise SubcategoriaEmUso(lancamentos, aprendizados)
            conexao.execute("DELETE FROM subcategorias WHERE id = ?", (subcategoria_id,))
    finally:
        conexao.close()

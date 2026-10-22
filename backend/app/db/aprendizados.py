# Aprendizados: padrão de descrição -> subcategoria
#
# SQL puro com sqlite3 (ADR-004). Padrão = descrição limpa (ADR-008,
# estendida pela ADR-019). Regras de criar/reforçar/sobrescrever/apagar
# na ADR-019; sugestão a partir de 1 confirmação (ADR-020).
#
# As funções recebem a conexão de quem chama, para rodar dentro da mesma
# transação que atualiza o lançamento (ver lancamentos.categorizar_lancamento).

import re
import unicodedata
from datetime import datetime

# Sufixo que o parser acrescenta aos parcelados (Etapa 2)
RE_SUFIXO_PARCELA = re.compile(r"\s*-\s*Parcela\s+\d+/\d+\s*$")
# Números SOLTOS no final (precedidos de espaço): "UBER 12,50" -> "UBER".
# Exigir o espaço evita cortar "...SUB 110,00ANTHROPIC.C"
RE_NUMEROS_FINAIS = re.compile(r"(\s+\d[\d.,]*)+\s*$")


def normalizar_padrao(descricao: str) -> str:
    """
    Chave de aprendizado de uma descrição:
    "DECATHLON NITEROI - Parcela 5/6" -> "decathlon niteroi".
    Além da ADR-008, ignora espaços repetidos e maiúsculas/minúsculas
    (ADR-019): descrições manuais são digitadas à mão.
    """
    padrao = RE_SUFIXO_PARCELA.sub("", descricao)
    padrao = RE_NUMEROS_FINAIS.sub("", padrao)
    padrao = " ".join(padrao.split())
    return unicodedata.normalize("NFC", padrao).casefold()


def buscar_sugestoes_batch(conexao, padroes) -> dict:
    """
    Uma única query para todos os padrões (ADR-018), já com os nomes de
    subcategoria e macro. Retorna {padrao: sugestao}.
    """
    padroes = sorted(set(padroes))
    if not padroes:
        return {}
    marcadores = ", ".join("?" for _ in padroes)
    linhas = conexao.execute(
        f"""
        SELECT a.padrao_descricao, s.id, s.nome, m.id, m.nome, a.confianca
        FROM aprendizados a
        JOIN subcategorias s ON s.id = a.subcategoria_id
        JOIN categorias_macro m ON m.id = s.categoria_macro_id
        WHERE a.padrao_descricao IN ({marcadores})
        """,
        padroes,
    ).fetchall()
    return {
        padrao: {
            "id": sub_id,
            "nome": sub_nome,
            "categoria_macro_id": macro_id,
            "categoria_macro_nome": macro_nome,
            "confianca": confianca,
        }
        for padrao, sub_id, sub_nome, macro_id, macro_nome, confianca in linhas
    }


def upsert_aprendizado(conexao, padrao: str, subcategoria_id: int,
                       lancamento_ja_estava_nela: bool) -> dict:
    """
    Registra que `padrao` pertence a `subcategoria_id`:
    - padrão novo: cria com confianca 1 ("criado")
    - mesma subcategoria: confianca + 1 ("reforcado")
    - outra subcategoria: troca e volta a confianca 1 ("sobrescrito")
    - lançamento já estava nela e o aprendizado já aponta para ela: não
      mexe ("inalterado") — clique duplo não infla a confiança
    """
    anterior = conexao.execute(
        "SELECT subcategoria_id, confianca FROM aprendizados WHERE padrao_descricao = ?",
        (padrao,),
    ).fetchone()
    if anterior is not None and anterior[0] == subcategoria_id and lancamento_ja_estava_nela:
        return {"acao": "inalterado", "confianca": anterior[1]}

    agora = datetime.now().isoformat(timespec="seconds")
    # Uma instrução atômica para as 3 regras. No DO UPDATE, as colunas sem
    # "excluded." são os valores ANTIGOS da linha, então o CASE compara a
    # subcategoria antiga com a nova antes de trocá-la
    confianca = conexao.execute(
        """
        INSERT INTO aprendizados
            (padrao_descricao, subcategoria_id, confianca, criado_em, atualizado_em)
        VALUES (?, ?, 1, ?, ?)
        ON CONFLICT (padrao_descricao) DO UPDATE SET
            confianca = CASE
                WHEN aprendizados.subcategoria_id = excluded.subcategoria_id
                THEN aprendizados.confianca + 1
                ELSE 1
            END,
            subcategoria_id = excluded.subcategoria_id,
            atualizado_em = excluded.atualizado_em
        RETURNING confianca
        """,
        (padrao, subcategoria_id, agora, agora),
    ).fetchall()[0][0]

    if anterior is None:
        acao = "criado"
    elif anterior[0] == subcategoria_id:
        acao = "reforcado"
    else:
        acao = "sobrescrito"
    return {"acao": acao, "confianca": confianca}


def apagar_aprendizado(conexao, padrao: str, subcategoria_anterior: int | None) -> dict:
    """
    Descategorizar: apaga o aprendizado só se ele aponta para a subcategoria
    que o lançamento tinha — não apaga o que este lançamento nunca alimentou.
    """
    cursor = conexao.execute(
        "DELETE FROM aprendizados WHERE padrao_descricao = ? AND subcategoria_id = ?",
        (padrao, subcategoria_anterior),
    )
    return {"acao": "apagado" if cursor.rowcount else "nenhuma", "confianca": None}

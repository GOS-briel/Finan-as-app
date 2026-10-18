import os
import tempfile

from flask import Flask, jsonify, request

from app.db import categorias, inicializar
from app.db.lancamentos import salvar_lancamentos_fatura
from app.fatura.leitor import (
    extrair_competencia,
    extrair_lancamentos,
    extrair_total_fatura,
)

app = Flask(__name__)


@app.before_request
def garantir_banco():
    if not inicializar.CAMINHO_BANCO.exists():
        inicializar.main()


@app.route("/")
def index():
    return "Olá, controle financeiro"


def _competencia_do_formulario() -> dict | None:
    """
    Lê "mes" e "ano" opcionais do formulário. Retorna None se nenhum veio,
    ou levanta ValueError se vierem incompletos ou inválidos.
    """
    mes = request.form.get("mes") or None
    ano = request.form.get("ano") or None
    if mes is None and ano is None:
        return None
    if mes is None or ano is None:
        raise ValueError("mes e ano devem vir juntos")
    mes, ano = int(mes), int(ano)
    if not (1 <= mes <= 12 and 2000 <= ano <= 2100):
        raise ValueError("mes/ano fora do intervalo")
    return {"mes": mes, "ano": ano, "fonte": "formulario"}


@app.route("/fatura/importar", methods=["POST"])
def importar_fatura():
    arquivo = request.files.get("arquivo")
    if arquivo is None or arquivo.filename == "":
        return jsonify({"erro": "nenhum arquivo enviado"}), 400
    if not arquivo.filename.lower().endswith(".pdf"):
        return jsonify({"erro": "arquivo deve ser PDF"}), 400
    try:
        competencia_formulario = _competencia_do_formulario()
    except ValueError:
        return jsonify({"erro": "mes/ano invalidos"}), 400

    # mkstemp em vez de NamedTemporaryFile: no Windows o arquivo aberto
    # pelo NamedTemporaryFile não pode ser reaberto pelo pdfplumber
    descritor, caminho = tempfile.mkstemp(suffix=".pdf")
    os.close(descritor)
    try:
        arquivo.save(caminho)
        lancamentos = extrair_lancamentos(caminho)
        competencia_pdf = extrair_competencia(caminho)
        total_fatura = extrair_total_fatura(caminho)
    except Exception:
        app.logger.exception("Falha ao processar fatura")
        return jsonify({"erro": "falha ao processar fatura"}), 500
    finally:
        os.remove(caminho)

    # Formulário tem prioridade sobre o detectado no PDF (ADR-009)
    if competencia_formulario is not None:
        competencia = competencia_formulario
    elif competencia_pdf is not None:
        competencia = {**competencia_pdf, "fonte": "pdf"}
    else:
        return jsonify({
            "erro": "nao foi possivel detectar o mes/ano",
            "pedir_do_usuario": True,
        }), 422

    try:
        salvos = salvar_lancamentos_fatura(
            lancamentos, competencia["mes"], competencia["ano"]
        )
    except Exception:
        app.logger.exception("Falha ao salvar lancamentos no banco")
        return jsonify({"erro": "falha ao salvar lancamentos no banco"}), 500

    inseridos = sum(1 for item in salvos if item["status"] == "inserido")
    total_despesas = round(sum(item["valor"] for item in salvos), 2)
    return jsonify({
        "competencia": competencia,
        "quantidade_total": len(salvos),
        "inseridos": inseridos,
        "ignorados_duplicata": len(salvos) - inseridos,
        "total_despesas": total_despesas,
        "total_fatura_pdf": total_fatura,
        # Protege contra mudança de layout: se o parser perder linhas, não bate
        "total_confere": (
            None if total_fatura is None
            else abs(total_despesas - total_fatura) < 0.005
        ),
        "lancamentos": salvos,
    })


def _dados_da_requisicao():
    """Corpo da requisição em JSON ou formulário."""
    dados = request.get_json(silent=True)
    return dados if isinstance(dados, dict) else request.form


def _validar_nome(valor) -> str:
    if not isinstance(valor, str):
        raise ValueError("nome deve ser texto")
    nome = valor.strip()
    if not nome:
        raise ValueError("nome nao pode ser vazio")
    if len(nome) > 50:
        raise ValueError("nome deve ter no maximo 50 caracteres")
    return nome


def _validar_macro_id(valor) -> int:
    # bool é subclasse de int em Python: sem isso, true viraria 1
    if isinstance(valor, bool) or not isinstance(valor, (int, str)):
        raise ValueError("categoria_macro_id deve ser inteiro")
    try:
        return int(valor)
    except ValueError:
        raise ValueError("categoria_macro_id deve ser inteiro") from None


ERRO_NOME_DUPLICADO = "ja existe uma subcategoria com esse nome nesta categoria"


@app.route("/categorias/macro")
def listar_categorias_macro():
    return jsonify(categorias.listar_macros_com_subcategorias())


@app.route("/subcategorias", methods=["POST"])
def criar_subcategoria():
    dados = _dados_da_requisicao()
    try:
        nome = _validar_nome(dados.get("nome"))
        categoria_macro_id = _validar_macro_id(dados.get("categoria_macro_id"))
    except ValueError as erro:
        return jsonify({"erro": str(erro)}), 400
    try:
        subcategoria = categorias.criar_subcategoria(nome, categoria_macro_id)
    except categorias.MacroNaoEncontrada:
        return jsonify({"erro": "categoria_macro_id nao existe"}), 400
    except categorias.NomeDuplicado:
        return jsonify({"erro": ERRO_NOME_DUPLICADO}), 409
    return jsonify(subcategoria), 201


@app.route("/subcategorias/<int:subcategoria_id>", methods=["PUT"])
def renomear_subcategoria(subcategoria_id):
    try:
        nome = _validar_nome(_dados_da_requisicao().get("nome"))
    except ValueError as erro:
        return jsonify({"erro": str(erro)}), 400
    try:
        subcategoria = categorias.renomear_subcategoria(subcategoria_id, nome)
    except categorias.SubcategoriaNaoEncontrada:
        return jsonify({"erro": "subcategoria nao encontrada"}), 404
    except categorias.NomeDuplicado:
        return jsonify({"erro": ERRO_NOME_DUPLICADO}), 409
    return jsonify(subcategoria)


@app.route("/subcategorias/<int:subcategoria_id>", methods=["DELETE"])
def deletar_subcategoria(subcategoria_id):
    try:
        categorias.deletar_subcategoria(subcategoria_id)
    except categorias.SubcategoriaNaoEncontrada:
        return jsonify({"erro": "subcategoria nao encontrada"}), 404
    except categorias.SubcategoriaEmUso as uso:
        return jsonify({
            "erro": (
                f"nao e possivel deletar: {uso.lancamentos} lancamentos e "
                f"{uso.aprendizados} aprendizados vinculados a esta subcategoria"
            ),
            "lancamentos_vinculados": uso.lancamentos,
            "aprendizados_vinculados": uso.aprendizados,
        }), 409
    return "", 204


if __name__ == "__main__":
    app.run(debug=True)

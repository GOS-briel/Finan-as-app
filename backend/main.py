import math
import os
import re
import tempfile
from datetime import date, timedelta

from flask import Flask, jsonify, request

from app.db import categorias, inicializar, lancamentos, tetos
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


# Validação no Python antes dos CHECKs do schema, para o erro sair com
# mensagem clara. Se mudar uma regra aqui, sincronizar com schema.sql.
ANO_MINIMO, ANO_MAXIMO = 2000, 2100

# Lançamento manual aceita de hoje até este número de dias no passado
# (hoje - 90 entra, hoje - 91 não; data futura nunca) — ADR-015
# TODO: ao deployar, usar ZoneInfo("America/Sao_Paulo") para evitar
# diferença de 1 dia na janela retroativa em horários noturnos
DIAS_RETROATIVO_MAXIMO = 90


def _validar_inteiro(valor, campo: str, minimo: int | None = None, maximo: int | None = None) -> int:
    """Aceita número ou texto numérico (form e query string mandam texto)."""
    if valor is None or valor == "":
        raise ValueError(f"{campo} e obrigatorio")
    # bool é subclasse de int em Python: sem isso, true viraria 1
    if isinstance(valor, bool) or not isinstance(valor, (int, str)):
        raise ValueError(f"{campo} deve ser inteiro")
    try:
        numero = int(valor)
    except ValueError:
        raise ValueError(f"{campo} deve ser inteiro") from None
    if minimo is not None and not minimo <= numero <= maximo:
        raise ValueError(f"{campo} deve estar entre {minimo} e {maximo}")
    return numero


def _validar_mes_ano(dados) -> tuple[int, int]:
    return (
        _validar_inteiro(dados.get("mes"), "mes", 1, 12),
        _validar_inteiro(dados.get("ano"), "ano", ANO_MINIMO, ANO_MAXIMO),
    )


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
    mes, ano = _validar_mes_ano(request.form)
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
        extraidos = extrair_lancamentos(caminho)
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
        salvos = lancamentos.salvar_lancamentos_fatura(
            extraidos, competencia["mes"], competencia["ano"]
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


def _validar_texto(valor, campo: str, maximo: int, obrigatorio: bool) -> str | None:
    """Tira espaços das pontas. Opcional vazio ou ausente vira None."""
    if valor is None and not obrigatorio:
        return None
    if not isinstance(valor, str):
        raise ValueError(f"{campo} deve ser texto")
    texto = valor.strip()
    if not texto:
        if obrigatorio:
            raise ValueError(f"{campo} nao pode ser vazio")
        return None
    if len(texto) > maximo:
        raise ValueError(f"{campo} deve ter no maximo {maximo} caracteres")
    return texto


def _validar_nome(valor) -> str:
    return _validar_texto(valor, "nome", 50, obrigatorio=True)


def _validar_macro_id(valor) -> int:
    return _validar_inteiro(valor, "categoria_macro_id")


def _validar_valor(valor) -> float:
    if valor is None or valor == "":
        raise ValueError("valor e obrigatorio")
    if isinstance(valor, bool) or not isinstance(valor, (int, float, str)):
        raise ValueError("valor deve ser numero")
    try:
        numero = float(valor)
    except ValueError:
        raise ValueError("valor deve ser numero") from None
    if not math.isfinite(numero):  # "nan", "inf"
        raise ValueError("valor deve ser numero")
    if numero < 0:
        raise ValueError("valor nao pode ser negativo")
    return round(numero, 2)


def _validar_formato_data(valor) -> str:
    """Só o formato AAAA-MM-DD; a janela de dias é checada à parte."""
    if valor is None or valor == "":
        raise ValueError("data e obrigatoria")
    # fromisoformat sozinho aceitaria "20261021" e "2026-W43-3"
    if not isinstance(valor, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", valor):
        raise ValueError("data deve estar no formato AAAA-MM-DD")
    try:
        return date.fromisoformat(valor).isoformat()
    except ValueError:  # ex: 2026-02-30
        raise ValueError("data invalida") from None


def _validar_janela_data(data_iso: str) -> None:
    dia, hoje = date.fromisoformat(data_iso), date.today()
    if dia > hoje:
        raise ValueError("data nao pode ser futura")
    if dia < hoje - timedelta(days=DIAS_RETROATIVO_MAXIMO):
        raise ValueError(f"data nao pode ser anterior a {DIAS_RETROATIVO_MAXIMO} dias atras")


def _validar_subcategoria_id(valor) -> int | None:
    if valor is None or valor == "":
        return None  # sem subcategoria (ou "descategorizar" no PUT)
    return _validar_inteiro(valor, "subcategoria_id")


# Um validador por campo editável (mesma lista de lancamentos.CAMPOS_EDITAVEIS)
VALIDADORES_LANCAMENTO = {
    "data": _validar_formato_data,
    "descricao": lambda valor: _validar_texto(valor, "descricao", 200, obrigatorio=True),
    "valor": _validar_valor,
    "subcategoria_id": _validar_subcategoria_id,
    "nota": lambda valor: _validar_texto(valor, "nota", 500, obrigatorio=False),
}


def _resposta_campos_nao_permitidos(dados):
    """400 se vier campo que ninguém pode editar (id, origem, parcelas...)."""
    nao_permitidos = sorted(set(dados) - set(lancamentos.CAMPOS_EDITAVEIS))
    if not nao_permitidos:
        return None
    return jsonify({
        "erro": f"campos nao permitidos: {', '.join(nao_permitidos)}",
        "campos_nao_permitidos": nao_permitidos,
    }), 400


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


@app.route("/tetos")
def listar_tetos():
    try:
        mes, ano = _validar_mes_ano(request.args)
    except ValueError as erro:
        return jsonify({"erro": str(erro)}), 400
    return jsonify(tetos.listar_tetos(mes, ano))


@app.route("/tetos", methods=["PUT"])
def definir_teto():
    dados = _dados_da_requisicao()
    try:
        categoria_macro_id = _validar_macro_id(dados.get("categoria_macro_id"))
        mes, ano = _validar_mes_ano(dados)
        valor = _validar_valor(dados.get("valor"))
    except ValueError as erro:
        return jsonify({"erro": str(erro)}), 400
    try:
        teto = tetos.definir_teto(categoria_macro_id, mes, ano, valor)
    except tetos.MacroNaoEncontrada:
        return jsonify({"erro": "categoria_macro_id nao existe"}), 400
    return jsonify(teto)


@app.route("/tetos", methods=["DELETE"])
def apagar_teto():
    try:
        categoria_macro_id = _validar_macro_id(request.args.get("categoria_macro_id"))
        mes, ano = _validar_mes_ano(request.args)
    except ValueError as erro:
        return jsonify({"erro": str(erro)}), 400
    try:
        tetos.apagar_teto(categoria_macro_id, mes, ano)
    except tetos.TetoNaoEncontrado:
        return jsonify({"erro": "nao existe teto definido para esta categoria/mes/ano"}), 404
    return "", 204


@app.route("/lancamentos")
def listar_lancamentos():
    try:
        mes, ano = _validar_mes_ano(request.args)
        categoria_macro_id = request.args.get("categoria_macro_id") or None
        if categoria_macro_id is not None:
            categoria_macro_id = _validar_macro_id(categoria_macro_id)
        origem = request.args.get("origem") or None
        if origem not in (None, "manual", "fatura"):
            raise ValueError("origem deve ser 'manual' ou 'fatura'")
    except ValueError as erro:
        return jsonify({"erro": str(erro)}), 400
    return jsonify(lancamentos.listar_lancamentos(mes, ano, categoria_macro_id, origem))


@app.route("/lancamentos", methods=["POST"])
def criar_lancamento():
    dados = _dados_da_requisicao()
    erro_campos = _resposta_campos_nao_permitidos(dados)
    if erro_campos:
        return erro_campos
    try:
        novo = {campo: validar(dados.get(campo)) for campo, validar in VALIDADORES_LANCAMENTO.items()}
        _validar_janela_data(novo["data"])
    except ValueError as erro:
        return jsonify({"erro": str(erro)}), 400
    try:
        criado = lancamentos.criar_lancamento_manual(**novo)
    except lancamentos.SubcategoriaNaoEncontrada:
        return jsonify({"erro": "subcategoria_id nao existe"}), 400
    return jsonify(criado), 201


@app.route("/lancamentos/<int:lancamento_id>", methods=["PUT"])
def atualizar_lancamento(lancamento_id):
    try:
        atual = lancamentos.buscar_lancamento(lancamento_id)
    except lancamentos.LancamentoNaoEncontrado:
        return jsonify({"erro": "lancamento nao encontrado"}), 404
    dados = _dados_da_requisicao()
    if not dados:
        return jsonify({"erro": "nenhum campo para atualizar"}), 400
    erro_campos = _resposta_campos_nao_permitidos(dados)
    if erro_campos:
        return erro_campos
    try:
        enviados = {campo: VALIDADORES_LANCAMENTO[campo](valor) for campo, valor in dados.items()}
    except ValueError as erro:
        return jsonify({"erro": str(erro)}), 400

    # Só conta como alteração o que difere do banco: reenviar o objeto
    # inteiro, com valores iguais, não dispara 403 nem a janela de datas
    alteracoes = {campo: valor for campo, valor in enviados.items() if valor != atual[campo]}
    # Janela de dias só se a data mudar. Em importado, mudar a data já é 403
    # (checado em lancamentos.atualizar_lancamento), que tem prioridade
    if "data" in alteracoes and atual["origem"] == "manual":
        try:
            _validar_janela_data(alteracoes["data"])
        except ValueError as erro:
            return jsonify({"erro": str(erro)}), 400

    try:
        atualizado = lancamentos.atualizar_lancamento(lancamento_id, alteracoes)
    except lancamentos.LancamentoNaoEncontrado:
        return jsonify({"erro": "lancamento nao encontrado"}), 404
    except lancamentos.EdicaoBloqueada as bloqueio:
        return jsonify({
            "erro": "lancamentos importados da fatura so permitem edicao de subcategoria e nota",
            "campos_bloqueados": bloqueio.campos,
        }), 403
    except lancamentos.SubcategoriaNaoEncontrada:
        return jsonify({"erro": "subcategoria_id nao existe"}), 400
    return jsonify(atualizado)


@app.route("/lancamentos/<int:lancamento_id>", methods=["DELETE"])
def apagar_lancamento(lancamento_id):
    try:
        lancamentos.apagar_lancamento(lancamento_id)
    except lancamentos.LancamentoNaoEncontrado:
        return jsonify({"erro": "lancamento nao encontrado"}), 404
    return "", 204


if __name__ == "__main__":
    app.run(debug=True)

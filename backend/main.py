import os
import tempfile

from flask import Flask, jsonify, request

from app.db import inicializar
from app.db.lancamentos import salvar_lancamentos_fatura
from app.fatura.leitor import (
    extrair_competencia,
    extrair_lancamentos,
    extrair_total_fatura,
)

app = Flask(__name__)


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

    if not inicializar.CAMINHO_BANCO.exists():
        inicializar.main()
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


if __name__ == "__main__":
    app.run(debug=True)

import os
import tempfile

from flask import Flask, jsonify, request

from app.fatura.leitor import extrair_lancamentos

app = Flask(__name__)


@app.route("/")
def index():
    return "Olá, controle financeiro"


@app.route("/fatura/importar", methods=["POST"])
def importar_fatura():
    arquivo = request.files.get("arquivo")
    if arquivo is None or arquivo.filename == "":
        return jsonify({"erro": "nenhum arquivo enviado"}), 400
    if not arquivo.filename.lower().endswith(".pdf"):
        return jsonify({"erro": "arquivo deve ser PDF"}), 400

    # mkstemp em vez de NamedTemporaryFile: no Windows o arquivo aberto
    # pelo NamedTemporaryFile não pode ser reaberto pelo pdfplumber
    descritor, caminho = tempfile.mkstemp(suffix=".pdf")
    os.close(descritor)
    try:
        arquivo.save(caminho)
        lancamentos = extrair_lancamentos(caminho)
    except Exception:
        app.logger.exception("Falha ao processar fatura")
        return jsonify({"erro": "falha ao processar fatura"}), 500
    finally:
        os.remove(caminho)

    return jsonify({
        "quantidade": len(lancamentos),
        "total_despesas": round(sum(item["valor"] for item in lancamentos), 2),
        "lancamentos": lancamentos,
    })


if __name__ == "__main__":
    app.run(debug=True)

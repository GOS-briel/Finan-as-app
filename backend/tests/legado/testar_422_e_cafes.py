# Testes que não podem sujar o banco real:
# 1) 422 via cliente de testes do Flask, simulando competência não detectada
# 2) dois "cafés" iguais (ADR-010) num banco temporário separado
import io
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, sys.argv[1])  # pasta backend
import main
from app.db import inicializar, lancamentos

pdf = Path(sys.argv[2]).read_bytes()

# 1) 422 -----------------------------------------------------------------
main.extrair_competencia = lambda caminho: None
cliente = main.app.test_client()
resposta = cliente.post(
    "/fatura/importar",
    data={"arquivo": (io.BytesIO(pdf), "fatura.pdf")},
    content_type="multipart/form-data",
)
print("422 ->", resposta.status_code, resposta.get_json())

# 2) dois cafés iguais, num banco temporário -----------------------------
pasta = tempfile.mkdtemp()
inicializar.CAMINHO_BANCO = Path(pasta) / "teste.db"  # conectar() lê esta variável
inicializar.criar_banco()

cafe = {"descricao": "CAFE DA ESQUINA NITEROI", "valor": 8.0,
        "parcela_atual": None, "parcela_total": None}
outro = {"descricao": "PADARIA NITEROI", "valor": 12.5,
         "parcela_atual": None, "parcela_total": None}

r1 = lancamentos.salvar_lancamentos_fatura([cafe, cafe, outro], 10, 2026)
print("1a importacao (2 cafes + padaria):", [i["status"] for i in r1])
r2 = lancamentos.salvar_lancamentos_fatura([cafe, cafe, outro], 10, 2026)
print("reimportacao:", [i["status"] for i in r2])
r3 = lancamentos.salvar_lancamentos_fatura([cafe, cafe, cafe, outro], 10, 2026)
print("3o cafe aparece depois:", [i["status"] for i in r3])
c = sqlite3.connect(inicializar.CAMINHO_BANCO)
print("cafes no banco:", c.execute(
    "SELECT COUNT(*) FROM lancamentos WHERE descricao LIKE 'CAFE%'").fetchone()[0])
c.close()
inicializar.CAMINHO_BANCO.unlink()
Path(pasta).rmdir()

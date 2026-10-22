import io
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, sys.argv[1])
import main
from app.db import inicializar

pasta = tempfile.mkdtemp()
inicializar.CAMINHO_BANCO = Path(pasta) / "teste.db"
cliente = main.app.test_client()
pdf = Path(sys.argv[2]).read_bytes()

casos = [
    ({"mes": "9", "ano": "2026"}, 200),
    ({"mes": "13", "ano": "2026"}, 400),
    ({"mes": "10"}, 400),
    ({"mes": "abc", "ano": "2026"}, 400),
    ({"mes": "10", "ano": "1999"}, 400),
]
for campos, esperado in casos:
    r = cliente.post("/fatura/importar",
                     data={"arquivo": (io.BytesIO(pdf), "f.pdf"), **campos},
                     content_type="multipart/form-data")
    d = r.get_json()
    resumo = d.get("competencia") or d.get("erro")
    print(f"{'OK    ' if r.status_code == esperado else 'FALHOU'} | form {campos} -> {r.status_code} {resumo}")
inicializar.CAMINHO_BANCO.unlink()
Path(pasta).rmdir()

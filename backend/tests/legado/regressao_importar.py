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
for vez in (1, 2):
    r = cliente.post("/fatura/importar", data={"arquivo": (io.BytesIO(pdf), "f.pdf")},
                     content_type="multipart/form-data")
    d = r.get_json()
    print(f"importacao {vez}: HTTP {r.status_code}, inseridos {d['inseridos']}, "
          f"ignorados {d['ignorados_duplicata']}, total_confere {d['total_confere']}")
inicializar.CAMINHO_BANCO.unlink()
Path(pasta).rmdir()

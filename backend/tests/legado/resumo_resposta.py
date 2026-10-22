import json
import sys

d = json.load(open(sys.argv[1], encoding="utf-8"))
if "erro" in d:
    print(d)
    sys.exit()
for chave in ("competencia", "quantidade_total", "inseridos", "ignorados_duplicata",
              "total_despesas", "total_fatura_pdf", "total_confere"):
    print(f"{chave}: {d[chave]}")
for item in d["lancamentos"][:2]:
    print(" ", json.dumps(item, ensure_ascii=False))

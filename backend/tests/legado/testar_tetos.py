# Testes da Etapa 7 num banco TEMPORÁRIO (o financas.db real não é tocado)
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, sys.argv[1])  # pasta backend
import main
from app.db import inicializar

pasta = tempfile.mkdtemp()
inicializar.CAMINHO_BANCO = Path(pasta) / "teste.db"
cliente = main.app.test_client()

MACROS = ["Alimentação", "Lazer", "Compras", "Saúde", "Educação", "Esporte", "Transporte", "Outros"]
falhas = 0


def checar(numero, descricao, condicao, detalhe=""):
    global falhas
    falhas += 0 if condicao else 1
    print(f"{'OK    ' if condicao else 'FALHOU'} | {numero:>3} | {descricao}" + (f"  -> {detalhe}" if detalhe else ""))


def get(mes, ano):
    return cliente.get(f"/tetos?mes={mes}&ano={ano}")


def alimentacao(mes, ano):
    linha = get(mes, ano).get_json()[0]
    return {k: linha[k] for k in ("valor", "herdado", "origem_mes", "origem_ano")}


def put(macro, mes, ano, valor, como_form=False):
    corpo = {"categoria_macro_id": macro, "mes": mes, "ano": ano, "valor": valor}
    return cliente.put("/tetos", data=corpo) if como_form else cliente.put("/tetos", json=corpo)


def delete(macro, mes, ano):
    return cliente.delete(f"/tetos?categoria_macro_id={macro}&mes={mes}&ano={ano}")


def linhas_no_banco():
    c = sqlite3.connect(inicializar.CAMINHO_BANCO)
    n = c.execute("SELECT COUNT(*) FROM tetos").fetchone()[0]
    c.close()
    return n


NULO = {"valor": None, "herdado": False, "origem_mes": None, "origem_ano": None}

# 1 ---------------------------------------------------------------------
r = get(10, 2026)
d = r.get_json()
checar(1, "GET sem tetos: 8 linhas, valor null, herdado false",
       r.status_code == 200 and len(d) == 8
       and all(l["valor"] is None and l["herdado"] is False for l in d)
       and [l["categoria_macro"]["nome"] for l in d] == MACROS, f"{r.status_code}, {len(d)} linhas")
print("        exemplo de linha:", d[0])

# 2 ---------------------------------------------------------------------
r = put(1, 10, 2026, 800)
checar(2, "PUT novo (Alimentacao=800, 10/2026) -> 200", r.status_code == 200
       and r.get_json() == {"valor": 800.0, "categoria_macro_id": 1, "mes": 10, "ano": 2026}, f"{r.status_code} {r.get_json()}")

# 3 ---------------------------------------------------------------------
a = alimentacao(10, 2026)
checar(3, "GET apos PUT: 800, herdado false, origem 10/2026",
       a == {"valor": 800.0, "herdado": False, "origem_mes": 10, "origem_ano": 2026}, a)

# 4 ---------------------------------------------------------------------
r = put(1, 10, 2026, 900)
checar(4, "PUT atualizando (900) -> 200", r.status_code == 200 and r.get_json()["valor"] == 900.0, r.status_code)
checar("4b", "upsert nao duplicou: 1 linha no banco", linhas_no_banco() == 1, linhas_no_banco())

# 5 ---------------------------------------------------------------------
a = alimentacao(10, 2026)
checar(5, "GET apos UPDATE: valor 900", a["valor"] == 900.0 and a["herdado"] is False, a)

# 6 ---------------------------------------------------------------------
a = alimentacao(11, 2026)
checar(6, "GET 11/2026: herdado de 10/2026",
       a == {"valor": 900.0, "herdado": True, "origem_mes": 10, "origem_ano": 2026}, a)
lazer = get(11, 2026).get_json()[1]
checar("6b", "outras macro continuam null em 11/2026", lazer["valor"] is None and lazer["herdado"] is False, lazer)

# 7 ---------------------------------------------------------------------
a = alimentacao(1, 2027)
checar(7, "GET 01/2027: herdado de 10/2026 (cruza o ano)",
       a == {"valor": 900.0, "herdado": True, "origem_mes": 10, "origem_ano": 2026}, a)
a = alimentacao(7, 2026)
checar("7b", "GET 07/2026: NAO herda do futuro -> null", a == NULO, a)
checar("7c", "GETs com heranca nao gravaram nada: 1 linha", linhas_no_banco() == 1, linhas_no_banco())

# 8 ---------------------------------------------------------------------
r = delete(1, 10, 2026)
checar(8, "DELETE 10/2026 -> 204", r.status_code == 204 and r.data == b"", r.status_code)

# 9 ---------------------------------------------------------------------
a = alimentacao(10, 2026)
checar(9, "GET apos DELETE: null (nada para herdar)", a == NULO, a)

# 10-12 -----------------------------------------------------------------
r = put(99, 10, 2026, 100)
checar(10, "PUT categoria_macro_id=99 -> 400", r.status_code == 400, f"{r.status_code} {r.get_json()}")
r = put(1, 13, 2026, 100)
checar(11, "PUT mes=13 -> 400", r.status_code == 400, f"{r.status_code} {r.get_json()}")
r = put(1, 10, 2026, -10)
checar(12, "PUT valor=-10 -> 400", r.status_code == 400, f"{r.status_code} {r.get_json()}")

# 13 --------------------------------------------------------------------
r = delete(1, 10, 2026)
checar(13, "DELETE inexistente -> 404", r.status_code == 404, f"{r.status_code} {r.get_json()}")

# Extras ----------------------------------------------------------------
put(1, 8, 2026, 500)
put(1, 10, 2026, 900)
a = alimentacao(11, 2026)
checar("E1", "com 08=500 e 10=900: 11/2026 herda o MAIS RECENTE (900, origem 10)",
       a["valor"] == 900.0 and a["origem_mes"] == 10, a)
a = alimentacao(9, 2026)
checar("E2", "09/2026 herda 500 de 08 (nao o 900 do futuro)",
       a == {"valor": 500.0, "herdado": True, "origem_mes": 8, "origem_ano": 2026}, a)
delete(1, 10, 2026)
a = alimentacao(10, 2026)
checar("E3", "apos apagar 10/2026: cai na heranca de 08 (500)",
       a == {"valor": 500.0, "herdado": True, "origem_mes": 8, "origem_ano": 2026}, a)

r = put(2, 10, 2026, 0)
checar("E4", "PUT valor=0 -> 200 (teto zero e valido)", r.status_code == 200 and r.get_json()["valor"] == 0.0, r.get_json())
lazer = get(10, 2026).get_json()[1]
checar("E4b", "GET mostra 0, nao null", lazer["valor"] == 0.0 and lazer["herdado"] is False, lazer)
r = put(3, 10, 2026, 123.456)
checar("E5", "PUT valor=123.456 -> arredonda 123.46", r.get_json()["valor"] == 123.46, r.get_json())

for valor in ("abc", True, None, "nan"):
    r = put(1, 10, 2026, valor)
    checar("E6", f"PUT valor={valor!r} -> 400", r.status_code == 400, f"{r.status_code} {r.get_json()}")
for mes, ano in ((0, 2026), (10, 1999), (10, 2101), ("x", 2026)):
    r = put(1, mes, ano, 100)
    checar("E7", f"PUT mes={mes!r} ano={ano!r} -> 400", r.status_code == 400, f"{r.status_code} {r.get_json()}")

r = put("4", "10", "2026", "350.5", como_form=True)
checar("E8", "PUT via form com campos em texto -> 200", r.status_code == 200
       and r.get_json() == {"valor": 350.5, "categoria_macro_id": 4, "mes": 10, "ano": 2026}, r.get_json())

r = cliente.get("/tetos?mes=10")
checar("E9", "GET sem ano -> 400", r.status_code == 400, f"{r.status_code} {r.get_json()}")
r = cliente.get("/tetos?mes=13&ano=2026")
checar("E9b", "GET mes=13 -> 400", r.status_code == 400, f"{r.status_code} {r.get_json()}")
r = cliente.delete("/tetos?categoria_macro_id=1&ano=2026")
checar("E10", "DELETE sem mes -> 400", r.status_code == 400, f"{r.status_code} {r.get_json()}")

# 14 --------------------------------------------------------------------
c = sqlite3.connect(inicializar.CAMINHO_BANCO)
macros = c.execute("SELECT id, nome FROM categorias_macro ORDER BY id").fetchall()
c.close()
checar(14, "8 macro intactas (ids 1-8, nomes canonicos)", macros == list(enumerate(MACROS, 1)), macros)

print()
print(f"falhas: {falhas}")
inicializar.CAMINHO_BANCO.unlink()
Path(pasta).rmdir()

# Testes da Etapa 6 num banco TEMPORÁRIO (o financas.db real não é tocado)
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, sys.argv[1])  # pasta backend
import main
from app.db import inicializar

pasta = tempfile.mkdtemp()
inicializar.CAMINHO_BANCO = Path(pasta) / "teste.db"  # before_request cria o banco
cliente = main.app.test_client()

MACROS = ["Alimentação", "Lazer", "Compras", "Saúde", "Educação", "Esporte", "Transporte", "Outros"]
falhas = 0


def checar(numero, descricao, condicao, detalhe=""):
    global falhas
    falhas += 0 if condicao else 1
    print(f"{'OK    ' if condicao else 'FALHOU'} | {numero:>3} | {descricao}" + (f"  -> {detalhe}" if detalhe else ""))


def post(nome, macro_id, como_form=False):
    corpo = {"nome": nome, "categoria_macro_id": macro_id}
    return cliente.post("/subcategorias", data=corpo) if como_form else cliente.post("/subcategorias", json=corpo)


# 1 ---------------------------------------------------------------------
r = cliente.get("/categorias/macro")
d = r.get_json()
checar(1, "GET sem subs: 8 macro, todas com []", r.status_code == 200 and len(d) == 8
       and all(m["subcategorias"] == [] for m in d), f"{r.status_code}, {len(d)} macro")

# 2 ---------------------------------------------------------------------
r = post("Delivery", 1)
delivery = r.get_json()
checar(2, "POST valido -> 201", r.status_code == 201 and delivery["nome"] == "Delivery"
       and delivery["categoria_macro_id"] == 1, f"{r.status_code} {delivery}")
r = post("  Restaurante  ", "1", como_form=True)
restaurante = r.get_json()
checar("2b", "POST via form, id em texto, nome com espacos -> 201 e strip",
       r.status_code == 201 and restaurante["nome"] == "Restaurante", f"{r.status_code} {restaurante}")

# 3 ---------------------------------------------------------------------
r = post("Delivery", 1)
checar(3, "POST nome duplicado na mesma macro -> 409", r.status_code == 409, f"{r.status_code} {r.get_json()}")
r = post("DELIVERY", 1)
checar("3b", "POST duplicado so mudando maiusculas -> 409", r.status_code == 409, r.status_code)
r = post("Delivery", 2)
checar("3c", "POST mesmo nome em OUTRA macro -> 201", r.status_code == 201, r.status_code)

# 4 ---------------------------------------------------------------------
r = post("Teste", 99)
checar(4, "POST categoria_macro_id=99 -> 400", r.status_code == 400, f"{r.status_code} {r.get_json()}")
for valor in ("abc", True, 2.5, None):
    r = post("Teste", valor)
    checar("4b", f"POST categoria_macro_id={valor!r} -> 400", r.status_code == 400, f"{r.status_code} {r.get_json()}")

# 5 ---------------------------------------------------------------------
for nome in ("", "   ", None, "x" * 51):
    r = post(nome, 1)
    rotulo = f"'x'*51" if nome and len(nome) > 50 else repr(nome)
    checar(5, f"POST nome={rotulo} -> 400", r.status_code == 400, f"{r.status_code} {r.get_json()}")
r = post("x" * 50, 8)
checar("5b", "POST nome com exatamente 50 chars -> 201", r.status_code == 201, r.status_code)

# 6 ---------------------------------------------------------------------
for nome in ("Zoológico", "açaí", "Água", "bar"):
    post(nome, 1)
r = cliente.get("/categorias/macro")
alimentacao = r.get_json()[0]
nomes = [s["nome"] for s in alimentacao["subcategorias"]]
esperado = ["açaí", "Água", "bar", "Delivery", "Restaurante", "Zoológico"]
checar(6, "GET com subs embutidas, ordem natural", nomes == esperado, nomes)
r = post("AÇAÍ", 1)
checar("6b", "POST 'AÇAÍ' quando existe 'açaí' -> 409 (acento + maiusculas)", r.status_code == 409, r.status_code)

# 7 ---------------------------------------------------------------------
r = cliente.put(f"/subcategorias/{restaurante['id']}", json={"nome": "Restaurantes"})
checar(7, "PUT renomeando -> 200", r.status_code == 200 and r.get_json()["nome"] == "Restaurantes",
       f"{r.status_code} {r.get_json()}")
r = cliente.put(f"/subcategorias/{restaurante['id']}", json={"nome": "RESTAURANTES"})
checar("7b", "PUT mudando so maiusculas do proprio nome -> 200", r.status_code == 200, r.status_code)

# 8 ---------------------------------------------------------------------
r = cliente.put(f"/subcategorias/{restaurante['id']}", json={"nome": "delivery"})
checar(8, "PUT com nome de outra sub da mesma macro -> 409", r.status_code == 409, f"{r.status_code} {r.get_json()}")
r = cliente.put("/subcategorias/9999", json={"nome": "Nada"})
checar("8b", "PUT id inexistente -> 404", r.status_code == 404, r.status_code)
r = cliente.put(f"/subcategorias/{restaurante['id']}", json={"nome": "  "})
checar("8c", "PUT nome vazio -> 400", r.status_code == 400, r.status_code)

# 9 ---------------------------------------------------------------------
bar_id = next(s["id"] for s in alimentacao["subcategorias"] if s["nome"] == "bar")
r = cliente.delete(f"/subcategorias/{bar_id}")
checar(9, "DELETE sem vinculos -> 204", r.status_code == 204 and r.data == b"", r.status_code)
r = cliente.delete(f"/subcategorias/{bar_id}")
checar("9b", "DELETE do mesmo id de novo -> 404", r.status_code == 404, r.status_code)

# 10 --------------------------------------------------------------------
conexao = inicializar.conectar()
with conexao:
    for _ in range(2):
        conexao.execute(
            "INSERT INTO lancamentos (data, descricao, valor, subcategoria_id, origem, criado_em) "
            "VALUES ('2026-10-18', 'IFOOD TESTE', 30.0, ?, 'manual', '2026-10-18T00:00:00')",
            (delivery["id"],),
        )
conexao.close()
r = cliente.delete(f"/subcategorias/{delivery['id']}")
d = r.get_json()
checar(10, "DELETE com 2 lancamentos -> 409 com contagem", r.status_code == 409
       and d["lancamentos_vinculados"] == 2 and d["aprendizados_vinculados"] == 0, f"{r.status_code} {d}")

zoo_id = next(s["id"] for s in alimentacao["subcategorias"] if s["nome"] == "Zoológico")
conexao = inicializar.conectar()
with conexao:
    conexao.execute(
        "INSERT INTO aprendizados (padrao_descricao, subcategoria_id, criado_em, atualizado_em) "
        "VALUES ('ZOO NITEROI', ?, '2026-10-18', '2026-10-18')", (zoo_id,))
conexao.close()
r = cliente.delete(f"/subcategorias/{zoo_id}")
d = r.get_json()
checar("10b", "DELETE com 1 aprendizado -> 409 com contagem", r.status_code == 409
       and d["lancamentos_vinculados"] == 0 and d["aprendizados_vinculados"] == 1, f"{r.status_code} {d}")
r = cliente.delete("/subcategorias/9999")
checar("10c", "DELETE id inexistente -> 404", r.status_code == 404, r.status_code)

# 11 --------------------------------------------------------------------
c = sqlite3.connect(inicializar.CAMINHO_BANCO)
macros = c.execute("SELECT id, nome FROM categorias_macro ORDER BY id").fetchall()
ainda_existem = c.execute("SELECT COUNT(*) FROM subcategorias WHERE id IN (?, ?)",
                          (delivery["id"], zoo_id)).fetchone()[0]
c.close()
checar(11, "8 macro intactas (ids 1-8, nomes canonicos)", macros == list(enumerate(MACROS, 1)), macros)
checar("11b", "subs bloqueadas continuam no banco", ainda_existem == 2, ainda_existem)

print()
print("RESPOSTA 409 DO TESTE 10:", cliente.delete(f"/subcategorias/{delivery['id']}").get_json())
print()
print(f"falhas: {falhas}")

inicializar.CAMINHO_BANCO.unlink()
Path(pasta).rmdir()

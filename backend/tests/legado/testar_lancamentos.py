# Testes da Etapa 8 num banco TEMPORÁRIO (o financas.db real não é tocado)
import io
import sqlite3
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, sys.argv[1])  # pasta backend
import main
from app.db import inicializar

pasta = tempfile.mkdtemp()
inicializar.CAMINHO_BANCO = Path(pasta) / "teste.db"
cliente = main.app.test_client()
falhas = 0
HOJE = date.today()


def dias_atras(n):
    return (HOJE - timedelta(days=n)).isoformat()


def checar(numero, descricao, condicao, detalhe=""):
    global falhas
    falhas += 0 if condicao else 1
    print(f"{'OK    ' if condicao else 'FALHOU'} | {numero:>4} | {descricao}" + (f"  -> {detalhe}" if detalhe else ""))


def post(**corpo):
    return cliente.post("/lancamentos", json=corpo)


def put(id_, **corpo):
    return cliente.put(f"/lancamentos/{id_}", json=corpo)


def get(query):
    return cliente.get(f"/lancamentos?{query}")


print(f"hoje = {HOJE}  |  89 dias = {dias_atras(89)}  |  90 = {dias_atras(90)}  |  91 = {dias_atras(91)}")

# Preparação: importa a fatura (23 lançamentos 'fatura' em 2026-10-01)
pdf = Path(sys.argv[2]).read_bytes()
r = cliente.post("/fatura/importar", data={"arquivo": (io.BytesIO(pdf), "f.pdf")},
                 content_type="multipart/form-data")
print(f"preparacao: importacao -> {r.status_code}, inseridos {r.get_json()['inseridos']}")
# Subcategorias para os testes
equipamento = cliente.post("/subcategorias", json={"nome": "Equipamento", "categoria_macro_id": 6}).get_json()
mercado = cliente.post("/subcategorias", json={"nome": "Mercado", "categoria_macro_id": 1}).get_json()
importados = get(f"mes=10&ano=2026&origem=fatura").get_json()
decathlon = next(l for l in importados if l["descricao"].startswith("DECATHLON"))
renner = next(l for l in importados if l["descricao"].startswith("RENNER"))
print()

# 1 ---------------------------------------------------------------------
r = post(data=HOJE.isoformat(), descricao="Padaria", valor=12.5, subcategoria_id=mercado["id"], nota="pao")
padaria = r.get_json()
checar(1, "POST manual valido -> 201, origem manual", r.status_code == 201 and padaria["origem"] == "manual"
       and padaria["parcela_atual"] is None and padaria["subcategoria_nome"] == "Mercado"
       and padaria["categoria_macro_nome"] == "Alimentação" and padaria["criado_em"], r.status_code)
print("         resposta:", padaria)

# 2-5: datas ------------------------------------------------------------
r = post(data=(HOJE + timedelta(days=1)).isoformat(), descricao="Futuro", valor=1)
checar(2, "POST data futura (amanha) -> 400", r.status_code == 400, f"{r.status_code} {r.get_json()}")
r = post(data=dias_atras(91), descricao="Velho", valor=1)
checar(3, "POST data hoje-91 -> 400", r.status_code == 400, f"{r.status_code} {r.get_json()}")
r = post(data=HOJE.isoformat(), descricao="Hoje", valor=1)
checar(4, "POST data = hoje -> 201", r.status_code == 201, r.status_code)
r = post(data=dias_atras(89), descricao="89 dias", valor=1)
checar(5, "POST data hoje-89 -> 201", r.status_code == 201, r.status_code)
r = post(data=dias_atras(90), descricao="90 dias", valor=1)
checar("5b", "POST data hoje-90 -> 201 (fronteira: '> 90' e recusado)", r.status_code == 201, r.status_code)
for invalida in ("21/10/2026", "20261021", "2026-W43-3", "2026-02-30", None):
    r = post(data=invalida, descricao="X", valor=1)
    checar("5c", f"POST data={invalida!r} -> 400", r.status_code == 400, f"{r.status_code} {r.get_json()}")

# 6-9: outros campos ----------------------------------------------------
for desc in ("", "   ", "x" * 201, None):
    r = post(data=HOJE.isoformat(), descricao=desc, valor=1)
    rotulo = "'x'*201" if desc and len(desc) > 200 else repr(desc)
    checar(6, f"POST descricao={rotulo} -> 400", r.status_code == 400, f"{r.status_code} {r.get_json()}")
r = post(data=HOJE.isoformat(), descricao="  Uber  ", valor=1)
checar("6b", "POST descricao com espacos -> strip", r.get_json()["descricao"] == "Uber", r.get_json()["descricao"])
r = post(data=HOJE.isoformat(), descricao="X", valor=-5)
checar(7, "POST valor negativo -> 400", r.status_code == 400, f"{r.status_code} {r.get_json()}")
r = post(data=HOJE.isoformat(), descricao="X", valor=1, subcategoria_id=999)
checar(8, "POST subcategoria_id inexistente -> 400", r.status_code == 400, f"{r.status_code} {r.get_json()}")
r = post(data=HOJE.isoformat(), descricao="Sem categoria", valor=7)
sem_cat = r.get_json()
checar(9, "POST sem subcategoria -> 201, campos de categoria null", r.status_code == 201
       and sem_cat["subcategoria_id"] is None and sem_cat["categoria_macro_nome"] is None, r.status_code)
r = post(data=HOJE.isoformat(), descricao="X", valor=1, nota="n" * 501)
checar("9b", "POST nota com 501 chars -> 400", r.status_code == 400, f"{r.status_code} {r.get_json()}")

# Ponto 2: campos nao permitidos ---------------------------------------
r = post(data=HOJE.isoformat(), descricao="X", valor=1, origem="fatura")
checar("P2a", "POST com origem -> 400 (nao permitido)", r.status_code == 400
       and r.get_json()["campos_nao_permitidos"] == ["origem"], f"{r.status_code} {r.get_json()}")
r = post(data=HOJE.isoformat(), descricao="X", valor=1, parcela_atual=1, parcela_total=3, id=50)
checar("P2b", "POST com parcelas e id -> 400 listando os 3", r.status_code == 400
       and r.get_json()["campos_nao_permitidos"] == ["id", "parcela_atual", "parcela_total"], r.get_json())
r = put(decathlon["id"], criado_em="2020-01-01")
checar("P2c", "PUT com criado_em -> 400", r.status_code == 400, f"{r.status_code} {r.get_json()}")
r = put(padaria["id"], origem="fatura")
checar("P2d", "PUT manual com origem -> 400 (nao 403)", r.status_code == 400, f"{r.status_code} {r.get_json()}")

# 10-13: PUT ------------------------------------------------------------
r = put(padaria["id"], valor=15)
checar(10, "PUT manual mudando valor -> 200", r.status_code == 200 and r.get_json()["valor"] == 15.0, r.get_json()["valor"])
r = put(decathlon["id"], valor=1, descricao="OUTRA", data="2026-10-02")
d = r.get_json()
checar(11, "PUT importado mudando valor/descricao/data -> 403 com lista", r.status_code == 403
       and d["campos_bloqueados"] == ["descricao", "valor", "data"], f"{r.status_code} {d}")
r = put(decathlon["id"], subcategoria_id=equipamento["id"])
d = r.get_json()
checar(12, "PUT importado mudando subcategoria -> 200", r.status_code == 200
       and d["subcategoria_nome"] == "Equipamento" and d["categoria_macro_nome"] == "Esporte", r.status_code)
r = put(decathlon["id"], nota="tenis de corrida")
checar(13, "PUT importado mudando nota -> 200", r.status_code == 200 and r.get_json()["nota"] == "tenis de corrida", r.status_code)

# Ponto 3: reenvio de valores iguais -------------------------------------
objeto = {k: decathlon[k] for k in ("data", "descricao", "valor")}
r = put(decathlon["id"], **objeto, subcategoria_id=equipamento["id"], nota="tenis de corrida")
checar("P3a", "PUT importado reenviando objeto inteiro igual -> 200 (nao 403)", r.status_code == 200, f"{r.status_code} {r.get_json()}")
r = put(renner["id"], **{k: renner[k] for k in ("data", "descricao", "valor")}, subcategoria_id=mercado["id"])
checar("P3b", "PUT importado: objeto igual + subcategoria nova -> 200 e categoriza", r.status_code == 200
       and r.get_json()["subcategoria_nome"] == "Mercado", r.status_code)
r = put(renner["id"], valor="48.63", descricao="  RENNER CABREUVA - Parcela 3/3  ")
checar("P3c", "PUT importado: valor '48.63' em texto e descricao com espacos = iguais -> 200",
       r.status_code == 200, f"{r.status_code} {r.get_json()}")
r = put(decathlon["id"], valor=66.67)
checar("P3d", "PUT importado: valor mudou 1 centavo -> 403 so com ['valor']", r.status_code == 403
       and r.get_json()["campos_bloqueados"] == ["valor"], r.get_json())

velho = post(data=dias_atras(90), descricao="Antigo", valor=10).get_json()
conexao = inicializar.conectar()
with conexao:  # simula um manual que "envelheceu" alem da janela
    conexao.execute("UPDATE lancamentos SET data = ? WHERE id = ?", (dias_atras(120), velho["id"]))
conexao.close()
r = put(velho["id"], data=dias_atras(120), descricao="Antigo", valor=11)
checar("P3e", "PUT manual de 120 dias reenviando a mesma data, mudando valor -> 200", r.status_code == 200
       and r.get_json()["valor"] == 11.0, f"{r.status_code} {r.get_json()}")
r = put(velho["id"], data=dias_atras(119))
checar("P3f", "PUT manual MUDANDO a data para fora da janela -> 400", r.status_code == 400, f"{r.status_code} {r.get_json()}")
r = put(padaria["id"], data=(HOJE + timedelta(days=1)).isoformat())
checar("P3g", "PUT manual mudando data para o futuro -> 400", r.status_code == 400, r.status_code)
r = put(padaria["id"], data=dias_atras(5), descricao="Padaria Nova")
checar("P3h", "PUT manual mudando data (dentro da janela) e descricao -> 200", r.status_code == 200
       and r.get_json()["data"] == dias_atras(5) and r.get_json()["descricao"] == "Padaria Nova", r.status_code)
r = put(padaria["id"], subcategoria_id=None, nota=None)
checar("P3i", "PUT subcategoria e nota null -> descategoriza e limpa", r.status_code == 200
       and r.get_json()["subcategoria_id"] is None and r.get_json()["nota"] is None, r.get_json())
r = put(padaria["id"])
checar("P3j", "PUT com corpo vazio -> 400", r.status_code == 400, f"{r.status_code} {r.get_json()}")
r = put(9999, valor=1)
checar("P3k", "PUT id inexistente -> 404", r.status_code == 404, r.status_code)
r = put(decathlon["id"], subcategoria_id=999)
checar("P3l", "PUT subcategoria inexistente -> 400", r.status_code == 400, r.status_code)

# 17-20: GET ------------------------------------------------------------
todos = get("mes=10&ano=2026").get_json()
manuais_out = [l for l in todos if l["origem"] == "manual"]
checar(17, "GET out/2026 sem filtros: 23 importados + manuais de outubro",
       len([l for l in todos if l["origem"] == "fatura"]) == 23 and len(manuais_out) >= 4, f"{len(todos)} itens")
ordem = [(l["data"], l["id"]) for l in todos]
checar("17b", "ordenado por data DESC, id DESC", ordem == sorted(ordem, reverse=True), ordem[:3])
checar("17c", "importados sem categoria aparecem (LEFT JOIN) com nulls",
       any(l["origem"] == "fatura" and l["categoria_macro_id"] is None for l in todos))
r = get("mes=10&ano=2026&origem=fatura")
checar(18, "GET origem=fatura -> so importados", all(l["origem"] == "fatura" for l in r.get_json())
       and len(r.get_json()) == 23, len(r.get_json()))
r = get("mes=10&ano=2026&categoria_macro_id=6")
checar(19, "GET categoria_macro_id=6 -> so Esporte (DECATHLON)",
       [l["descricao"] for l in r.get_json()] == ["DECATHLON NITEROI - Parcela 5/6"], [l["descricao"] for l in r.get_json()])
post(data=HOJE.isoformat(), descricao="Feira", valor=30, subcategoria_id=mercado["id"])
r = get("mes=10&ano=2026&categoria_macro_id=1&origem=manual")
checar(20, "GET macro=1 + origem=manual -> intersecao (so Feira, nao RENNER)",
       [l["descricao"] for l in r.get_json()] == ["Feira"], [l["descricao"] for l in r.get_json()])
r = get("mes=7&ano=2026")
checar("20b", "GET julho traz os manuais de 89/90 dias, nao os de outubro",
       {l["descricao"] for l in r.get_json()} >= {"89 dias", "90 dias"} and all(l["data"].startswith("2026-07") for l in r.get_json()),
       [l["descricao"] for l in r.get_json()])
for query, rotulo in (("ano=2026", "sem mes"), ("mes=10&ano=2026&origem=outra", "origem invalida"),
                      ("mes=10&ano=2026&categoria_macro_id=abc", "macro invalida")):
    r = get(query)
    checar("20c", f"GET {rotulo} -> 400", r.status_code == 400, f"{r.status_code} {r.get_json()}")

# 14-16: DELETE ---------------------------------------------------------
r = cliente.delete(f"/lancamentos/{sem_cat['id']}")
checar(14, "DELETE manual -> 204", r.status_code == 204 and r.data == b"", r.status_code)
r = cliente.delete(f"/lancamentos/{renner['id']}")
checar(15, "DELETE importado -> 204 (hard delete nao discrimina origem)", r.status_code == 204, r.status_code)
c = sqlite3.connect(inicializar.CAMINHO_BANCO)
some = c.execute("SELECT COUNT(*) FROM lancamentos WHERE id IN (?, ?)", (sem_cat["id"], renner["id"])).fetchone()[0]
c.close()
checar("15b", "linhas sumiram de verdade do banco", some == 0, some)
r = cliente.delete("/lancamentos/9999")
checar(16, "DELETE id inexistente -> 404", r.status_code == 404, r.status_code)

# 21: regressao da importacao (+ ponto 4: importado apagado volta) -------
r = cliente.post("/fatura/importar", data={"arquivo": (io.BytesIO(pdf), "f.pdf")},
                 content_type="multipart/form-data")
d = r.get_json()
checar(21, "reimportacao: so o RENNER apagado volta (1 inserido, 22 ignorados)",
       r.status_code == 200 and d["inseridos"] == 1 and d["ignorados_duplicata"] == 22 and d["total_confere"],
       f"{r.status_code} inseridos {d['inseridos']} ignorados {d['ignorados_duplicata']}")
checar("21b", "DECATHLON categorizado/com nota NAO duplicou na reimportacao",
       len([l for l in get("mes=10&ano=2026&origem=fatura").get_json() if l["descricao"].startswith("DECATHLON")]) == 1)

print()
print(f"falhas: {falhas}")
inicializar.CAMINHO_BANCO.unlink()
Path(pasta).rmdir()

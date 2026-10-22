# Testes da Etapa 9 num banco TEMPORÁRIO (o financas.db real não é tocado)
import io
import sqlite3
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, sys.argv[1])  # pasta backend
import main
from app.db import aprendizados, inicializar, lancamentos as db_lancamentos
from app.db.aprendizados import normalizar_padrao

pasta = tempfile.mkdtemp()
inicializar.CAMINHO_BANCO = Path(pasta) / "teste.db"
cliente = main.app.test_client()
falhas = 0
HOJE = date.today().isoformat()


def checar(numero, descricao, condicao, detalhe=""):
    global falhas
    falhas += 0 if condicao else 1
    print(f"{'OK    ' if condicao else 'FALHOU'} | {numero:>4} | {descricao}" + (f"  -> {detalhe}" if detalhe else ""))


def categorizar(id_, sub_id, como_form=False):
    if como_form:
        return cliente.post(f"/lancamentos/{id_}/categorizar", data={"subcategoria_id": sub_id})
    return cliente.post(f"/lancamentos/{id_}/categorizar", json={"subcategoria_id": sub_id})


def lista(query="mes=10&ano=2026"):
    return cliente.get(f"/lancamentos?{query}").get_json()


def item(id_, query="mes=10&ano=2026"):
    return next(l for l in lista(query) if l["id"] == id_)


def aprendizados_no_banco():
    c = sqlite3.connect(inicializar.CAMINHO_BANCO)
    linhas = c.execute("SELECT padrao_descricao, subcategoria_id, confianca FROM aprendizados ORDER BY id").fetchall()
    c.close()
    return linhas


# Normalização -----------------------------------------------------------
casos = [
    (1, "DECATHLON NITEROI - Parcela 5/6", "DECATHLON NITEROI"),
    (2, "DECATHLON NITEROI - Parcela 6/6", "DECATHLON NITEROI"),
    (3, "ACAI DA BARRA NITEROI", "ACAI DA BARRA NITEROI"),
    (4, "ANTHROPIC* CLAUDE SUB 110,00ANTHROPIC.C", "ANTHROPIC* CLAUDE SUB 110,00ANTHROPIC.C"),
    ("N1", "UBER 12,50", "UBER"),
    ("N2", "POSTO SHELL 1.234,56 789", "POSTO SHELL"),
    ("N3", "Padaria  Central ", "PADARIA CENTRAL"),
    ("N4", "99Food *KiDelicia Pizza e Rio de Janeir", "99FOOD *KIDELICIA PIZZA E RIO DE JANEIR"),
    ("N5", "LOJAS RIACHUELO SAO PAULO - Parcela 3/4", "LOJAS RIACHUELO SAO PAULO"),
]
for numero, entrada, esperado in casos:
    obtido = normalizar_padrao(entrada)
    checar(numero, f"normalizar({entrada!r})", obtido == esperado.casefold(), repr(obtido))
checar("N6", "'decathlon niteroi' != 'decathlon rio'",
       normalizar_padrao("DECATHLON RIO") != normalizar_padrao("DECATHLON NITEROI - Parcela 5/6"))

# Preparação --------------------------------------------------------------
pdf = Path(sys.argv[2]).read_bytes()
r = cliente.post("/fatura/importar", data={"arquivo": (io.BytesIO(pdf), "f.pdf")}, content_type="multipart/form-data")
print(f"\npreparacao: importacao -> {r.status_code}, inseridos {r.get_json()['inseridos']}")
sub = lambda nome, macro: cliente.post("/subcategorias", json={"nome": nome, "categoria_macro_id": macro}).get_json()["id"]
EQUIP, ROUPAS, MERCADO = sub("Equipamento", 6), sub("Roupas", 3), sub("Mercado", 1)
manual = lambda desc: cliente.post("/lancamentos", json={"data": HOJE, "descricao": desc, "valor": 10}).get_json()["id"]
M1, M2, M3, M4 = manual("DECATHLON NITEROI"), manual("Decathlon  Niteroi"), manual("DECATHLON RIO"), manual("DECATHLON NITEROI")
DEC = next(l["id"] for l in lista("mes=10&ano=2026&origem=fatura") if l["descricao"].startswith("DECATHLON"))
print()

# 11: GET sem aprendizados ------------------------------------------------
todos = lista()
checar(11, "GET com aprendizados vazio: chave presente e null em todos",
       len(todos) == 27 and all("subcategoria_sugerida" in l and l["subcategoria_sugerida"] is None for l in todos), len(todos))

# 13: 1 query em aprendizados -----------------------------------------------
queries = []
conectar_original = db_lancamentos.conectar


def conectar_com_rastreio():
    conexao = conectar_original()
    conexao.set_trace_callback(queries.append)  # registra cada SQL executado
    return conexao


db_lancamentos.conectar = conectar_com_rastreio
lista()
db_lancamentos.conectar = conectar_original
em_aprendizados = [q for q in queries if "aprendizados" in q]
checar(13, "GET de 27 lancamentos (27 sem categoria) -> exatamente 1 query em aprendizados",
       len(em_aprendizados) == 1, f"{len(em_aprendizados)} de {len(queries)} queries no total")

# 5-7: ciclo de aprendizado ---------------------------------------------
r = categorizar(DEC, EQUIP)
d = r.get_json()
checar(5, "categorizar DECATHLON importado -> criado, confianca 1",
       r.status_code == 200 and d["aprendizado"] == {"acao": "criado", "confianca": 1}, d["aprendizado"])
print("         resposta.lancamento:", {k: d["lancamento"][k] for k in ("id", "descricao", "subcategoria_nome", "categoria_macro_nome", "subcategoria_sugerida")})
checar("5b", "resposta.lancamento tem o mesmo formato do GET", set(d["lancamento"]) == set(todos[0]))
r = categorizar(DEC, EQUIP)
checar("5c", "categorizar DE NOVO o mesmo lancamento/sub -> inalterado (nao infla)",
       r.get_json()["aprendizado"] == {"acao": "inalterado", "confianca": 1}, r.get_json()["aprendizado"])

# 12: sugestão aparece em outro DECATHLON NITEROI
s = item(M4)["subcategoria_sugerida"]
checar(12, "GET: outro 'DECATHLON NITEROI' (manual M4) recebe sugestao Equipamento",
       s == {"id": EQUIP, "nome": "Equipamento", "categoria_macro_id": 6, "categoria_macro_nome": "Esporte", "confianca": 1}, s)
checar("12b", "'DECATHLON RIO' nao recebe sugestao de NITEROI", item(M3)["subcategoria_sugerida"] is None)
checar("12c", "'Decathlon  Niteroi' (maiusc./espacos) recebe a mesma sugestao",
       (item(M2)["subcategoria_sugerida"] or {}).get("id") == EQUIP)

r = categorizar(M1, EQUIP)
checar(6, "categorizar M1 (mesmo padrao, mesma sub) -> reforcado, confianca 2",
       r.get_json()["aprendizado"] == {"acao": "reforcado", "confianca": 2}, r.get_json()["aprendizado"])
checar("6b", "sugestao de M4 agora mostra confianca 2", item(M4)["subcategoria_sugerida"]["confianca"] == 2)

r = categorizar(M2, ROUPAS)
checar(7, "categorizar M2 (mesmo padrao, OUTRA sub) -> sobrescrito, confianca 1",
       r.get_json()["aprendizado"] == {"acao": "sobrescrito", "confianca": 1}, r.get_json()["aprendizado"])
s = item(M4)["subcategoria_sugerida"]
checar("7b", "sugestao de M4 passou para Roupas/Compras, confianca 1",
       s["nome"] == "Roupas" and s["categoria_macro_nome"] == "Compras" and s["confianca"] == 1, s)

# 14-15
checar(14, "lancamento JA categorizado (DEC) -> subcategoria_sugerida null",
       "subcategoria_sugerida" in item(DEC) and item(DEC)["subcategoria_sugerida"] is None)
acai = next(l for l in lista() if l["descricao"] == "ACAI DA BARRA NITEROI")
checar(15, "sem match em aprendizados (ACAI) -> subcategoria_sugerida null", acai["subcategoria_sugerida"] is None)

# 8: descategorizar ----------------------------------------------------------
r = categorizar(M2, None)
checar(8, "descategorizar M2 (estava em Roupas, aprendizado Roupas) -> apagado",
       r.get_json()["aprendizado"] == {"acao": "apagado", "confianca": None}
       and r.get_json()["lancamento"]["subcategoria_id"] is None, r.get_json()["aprendizado"])
checar("8b", "sem aprendizado, M4 volta a ter sugestao null", item(M4)["subcategoria_sugerida"] is None)
r = categorizar(M1, None)
checar("8c", "descategorizar M1 sem aprendizado existente -> nenhuma",
       r.get_json()["aprendizado"]["acao"] == "nenhuma", r.get_json()["aprendizado"])
categorizar(M1, EQUIP)  # recria: padrao -> Equipamento
cliente.put(f"/lancamentos/{M4}", json={"subcategoria_id": MERCADO})  # PUT silencioso
antes = aprendizados_no_banco()
r = categorizar(M4, None)
checar("8d", "descategorizar M4 (estava em Mercado, aprendizado aponta Equipamento) -> nenhuma, aprendizado preservado",
       r.get_json()["aprendizado"]["acao"] == "nenhuma" and aprendizados_no_banco() == antes, aprendizados_no_banco())

# 9-10 e validações --------------------------------------------------------------
r = categorizar(9999, EQUIP)
checar(9, "categorizar lancamento inexistente -> 404", r.status_code == 404, r.status_code)
r = categorizar(M3, 999)
checar(10, "categorizar com subcategoria inexistente -> 400", r.status_code == 400, f"{r.status_code} {r.get_json()}")
checar("10b", "...e nada mudou (M3 continua sem categoria)", item(M3)["subcategoria_id"] is None)
r = cliente.post(f"/lancamentos/{M3}/categorizar", json={})
checar("V1", "corpo sem subcategoria_id -> 400", r.status_code == 400, f"{r.status_code} {r.get_json()}")
r = cliente.post(f"/lancamentos/{M3}/categorizar", json={"subcategoria_id": EQUIP, "nota": "x"})
checar("V2", "campo extra (nota) -> 400 campos_nao_permitidos", r.status_code == 400
       and r.get_json().get("campos_nao_permitidos") == ["nota"], r.get_json())
r = categorizar(M3, "abc")
checar("V3", "subcategoria_id 'abc' -> 400", r.status_code == 400, r.status_code)
r = categorizar(M3, str(EQUIP), como_form=True)
checar("V4", "via form com id em texto -> 200 criado (padrao 'decathlon rio')",
       r.status_code == 200 and r.get_json()["aprendizado"]["acao"] == "criado", r.get_json()["aprendizado"])
r = categorizar(M3, "", como_form=True)
checar("V5", "via form com '' -> descategoriza (apagado)", r.get_json()["aprendizado"]["acao"] == "apagado", r.get_json()["aprendizado"])

# ADR-017: PUT continua silencioso -------------------------------------------
antes = aprendizados_no_banco()
renner = next(l["id"] for l in lista() if l["descricao"].startswith("RENNER"))
cliente.put(f"/lancamentos/{renner}", json={"subcategoria_id": ROUPAS})
checar("S1", "PUT com subcategoria NAO cria aprendizado (ADR-017)", aprendizados_no_banco() == antes)

# Filtro sem_categoria -----------------------------------------------------------
sc = lista("mes=10&ano=2026&sem_categoria=true")
checar("F1", "sem_categoria=true -> so os sem subcategoria", sc and all(l["subcategoria_id"] is None for l in sc)
       and len(sc) == len([l for l in lista() if l["subcategoria_id"] is None]), len(sc))
checar("F2", "sem_categoria=false -> todos", len(lista("mes=10&ano=2026&sem_categoria=false")) == 27)
r = cliente.get("/lancamentos?mes=10&ano=2026&sem_categoria=sim")
checar("F3", "sem_categoria=sim -> 400", r.status_code == 400, r.get_json())
checar("F4", "sem_categoria + origem=fatura combinados",
       all(l["origem"] == "fatura" and l["subcategoria_id"] is None for l in lista("mes=10&ano=2026&sem_categoria=true&origem=fatura")))

# Integração com outras etapas ------------------------------------------------
r = cliente.delete(f"/subcategorias/{EQUIP}")
checar("I1", "DELETE de subcategoria com aprendizado -> 409 (Etapa 6 protege a sugestao)",
       r.status_code == 409 and r.get_json()["aprendizados_vinculados"] == 1, r.get_json())
antes_apr, antes_dec = aprendizados_no_banco(), item(DEC)
r = cliente.post("/fatura/importar", data={"arquivo": (io.BytesIO(pdf), "f.pdf")}, content_type="multipart/form-data")
checar("I2", "reimportacao preserva: 0 inseridos, DEC continua categorizado, aprendizados intactos",
       r.get_json()["inseridos"] == 0 and item(DEC)["subcategoria_id"] == antes_dec["subcategoria_id"] == EQUIP
       and aprendizados_no_banco() == antes_apr, r.get_json()["inseridos"])

print("\naprendizados no fim:", aprendizados_no_banco())
print(f"falhas: {falhas}")
inicializar.CAMINHO_BANCO.unlink()
Path(pasta).rmdir()

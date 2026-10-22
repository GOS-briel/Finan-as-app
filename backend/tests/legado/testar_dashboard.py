# Testes da Etapa 10 (dashboard) num banco TEMPORÁRIO
# Uso: python backend/tests/legado/testar_dashboard.py backend <fatura.pdf>
import calendar
import io
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, sys.argv[1])  # pasta backend
import main
from app.db import dashboard as db_dashboard
from app.db import inicializar, lancamentos as db_lancamentos, tetos as db_tetos

pasta = tempfile.mkdtemp()
inicializar.CAMINHO_BANCO = Path(pasta) / "teste.db"
cliente = main.app.test_client()
falhas = 0


def checar(numero, descricao, condicao, detalhe=""):
    global falhas
    falhas += 0 if condicao else 1
    print(f"{'OK    ' if condicao else 'FALHOU'} | {numero:>4} | {descricao}" + (f"  -> {detalhe}" if detalhe else ""))


def dash(mes, ano):
    r = cliente.get(f"/dashboard?mes={mes}&ano={ano}")
    return r.get_json()


def por_macro(d, macro_id):
    return next(c for c in d["categorias"] if c["categoria_macro"] and c["categoria_macro"]["id"] == macro_id)


def inserir(data, descricao, valor, subcategoria_id, criado_em="2026-08-01T00:00:00"):
    conexao = inicializar.conectar()
    with conexao:
        conexao.execute(
            "INSERT INTO lancamentos (data, descricao, valor, subcategoria_id, origem, criado_em) "
            "VALUES (?, ?, ?, ?, 'manual', ?)", (data, descricao, valor, subcategoria_id, criado_em))
    conexao.close()


def teto(macro, mes, ano, valor):
    assert cliente.put("/tetos", json={"categoria_macro_id": macro, "mes": mes, "ano": ano, "valor": valor}).status_code == 200


# 1-3: validação -------------------------------------------------------------
for query, numero, rotulo in (("", 1, "sem mes/ano"), ("mes=13&ano=2026", 2, "mes=13"), ("mes=10&ano=1999", 3, "ano=1999")):
    r = cliente.get(f"/dashboard?{query}")
    checar(numero, f"GET {rotulo} -> 400", r.status_code == 400, f"{r.status_code} {r.get_json()}")

# 4: banco vazio --------------------------------------------------------------
d = dash(10, 2026)
virtual = d["categorias"][-1]
checar(4, "banco vazio: hero zerado, sem_teto, percentual null",
       d["hero"] == {"total_gasto": 0, "gasto_com_teto": 0, "gasto_sem_teto": 0, "total_teto": 0,
                     "percentual_uso": None, "status": "sem_teto"}, d["hero"])
checar("4b", "banco vazio: 8 macro com gasto 0, sem_teto, convite true",
       len(d["categorias"]) == 9 and all(c["gasto"] == 0 and c["status"] == "sem_teto" and c["convite_definir_teto"]
                                         for c in d["categorias"][:8]))
checar("4c", "banco vazio: 'Sem categoria' presente com gasto 0 e quantidade 0, convite false",
       virtual["categoria_virtual_nome"] == "Sem categoria" and virtual["gasto"] == 0 and virtual["quantidade"] == 0
       and virtual["convite_definir_teto"] is False, virtual)
checar("4d", "banco vazio: ultimos_lancamentos = []", d["ultimos_lancamentos"] == [])
checar("4e", "todos os 9 itens tem exatamente as mesmas chaves",
       len({tuple(sorted(c)) for c in d["categorias"]}) == 1, sorted(d["categorias"][0]))

# Cenário controlado: agosto/2026 ----------------------------------------------
sub = lambda nome, macro: cliente.post("/subcategorias", json={"nome": nome, "categoria_macro_id": macro}).get_json()["id"]
S = {macro: sub(f"Sub {macro}", macro) for macro in range(1, 9)}
inserir("2026-08-10", "TREINO", 850, S[6])      # Esporte    850 / 500 = 170%  estourado
inserir("2026-08-11", "MERCADO", 680, S[1])     # Alimentação 680 / 800 = 85%  quase_no_teto
inserir("2026-08-12", "ROUPA", 100, S[3])       # Compras    100 / 200 = 50%   folgado
inserir("2026-08-13", "CINEMA", 30, S[2])       # Lazer       30 / 300 (herdado de 07) = 10%  folgado
inserir("2026-08-14", "CURSO", 20, S[5])        # Educação    20 / 0 -> estourado, percentual null
inserir("2026-08-15", "ONIBUS", 40, S[7])       # Transporte  40 / sem teto
inserir("2026-08-16", "AVULSO A", 25, None)     # Sem categoria
inserir("2026-08-16", "AVULSO B", 15, None)     # Sem categoria
teto(6, 8, 2026, 500); teto(1, 8, 2026, 800); teto(3, 8, 2026, 200)
teto(2, 7, 2026, 300)                           # Lazer: só julho -> agosto herda
teto(4, 8, 2026, 0); teto(5, 8, 2026, 0)        # Saúde e Educação: teto zero

d = dash(8, 2026)
h = d["hero"]
print("\n         hero agosto:", h)
checar(6, "total_gasto = soma de tudo (1760)", h["total_gasto"] == 1760.0, h["total_gasto"])
checar("6b", "gasto_com_teto = macros com teto (1680) e gasto_sem_teto = 80 (Transporte + Sem categoria)",
       h["gasto_com_teto"] == 1680.0 and h["gasto_sem_teto"] == 80.0, (h["gasto_com_teto"], h["gasto_sem_teto"]))
checar(7, "total_teto inclui herdado de julho (500+800+200+300+0+0 = 1800)", h["total_teto"] == 1800.0, h["total_teto"])
checar(8, "percentual_uso = 1680/1800 = 93.33, status quase_no_teto",
       h["percentual_uso"] == 93.33 and h["status"] == "quase_no_teto", (h["percentual_uso"], h["status"]))

ordem = [c["categoria_macro"]["id"] if c["categoria_macro"] else "virtual" for c in d["categorias"]]
print("         ordem:", [(c["categoria_macro"] or {"nome": c["categoria_virtual_nome"]})["nome"] + f"({c['status']}, {c['percentual']})" for c in d["categorias"]])
checar(10, "estourados primeiro (Educacao teto 0 = infinito, depois Esporte 170%), depois quase (Alimentacao)",
       ordem[:3] == [5, 6, 1], ordem)
checar(11, "folgados por % DESC (Compras 50, Lazer 10, Saude 0) antes dos sem_teto (Transporte 7, Outros 8)",
       ordem[3:8] == [3, 2, 4, 7, 8], ordem)
checar(12, "'Sem categoria' e o ultimo item", ordem[-1] == "virtual" and len(ordem) == 9, ordem)

e = por_macro(d, 6)
checar(13, "Esporte 170% -> estourado, diferenca = teto - gasto = -350",
       e["percentual"] == 170.0 and e["status"] == "estourado" and e["diferenca"] == -350.0, e)
a = por_macro(d, 1)
checar(14, "Alimentacao 85% -> quase_no_teto, diferenca 120",
       a["percentual"] == 85.0 and a["status"] == "quase_no_teto" and a["diferenca"] == 120.0, a)
c = por_macro(d, 3)
checar(15, "Compras 50% -> folgado", c["percentual"] == 50.0 and c["status"] == "folgado", c)
t = por_macro(d, 7)
checar(16, "Transporte sem teto -> sem_teto, teto/percentual/diferenca null, convite true",
       t["status"] == "sem_teto" and t["teto"] is None and t["percentual"] is None and t["diferenca"] is None
       and t["convite_definir_teto"] is True and t["gasto"] == 40.0, t)
checar("16b", "macro COM teto tem convite_definir_teto false", e["convite_definir_teto"] is False)
ed = por_macro(d, 5)
checar("P2a", "teto 0 com gasto 20 -> estourado, percentual null, diferenca -20",
       ed["status"] == "estourado" and ed["percentual"] is None and ed["diferenca"] == -20.0, ed)
sa = por_macro(d, 4)
checar("P2b", "teto 0 sem gasto -> folgado, percentual 0", sa["status"] == "folgado" and sa["percentual"] == 0.0, sa)
checar("P3a", "macro sem nenhum lancamento aparece com gasto 0 e quantidade 0 (Outros)",
       por_macro(d, 8)["gasto"] == 0 and por_macro(d, 8)["quantidade"] == 0)
checar("P3b", "quantidade por categoria e da 'Sem categoria' (2), valor_sem_categoria 40",
       e["quantidade"] == 1 and d["categorias"][-1]["quantidade"] == 2 and d["quantidade_sem_categoria"] == 2
       and d["valor_sem_categoria"] == 40.0)

# Fronteiras do threshold (sem arredondamento no status) --------------------------
for gasto, teto_, esperado in ((79.99, 100, "folgado"), (80, 100, "quase_no_teto"), (100, 100, "quase_no_teto"),
                               (100.01, 100, "estourado"), (100.004, 100, "estourado"), (0, None, "sem_teto")):
    pct, status = db_dashboard.classificar(gasto, teto_)
    checar("B", f"classificar({gasto}, {teto_}) -> {esperado}", status == esperado, (pct, status))

# Hero sem tetos mas com gasto -----------------------------------------------------
inserir("2026-09-05", "SETEMBRO", 50, S[8])  # setembro herda os tetos de agosto
d = dash(9, 2026)
checar("P1", "setembro: tetos herdados, gasto so em Outros (sem teto) -> gasto_com_teto 0, percentual 0",
       d["hero"]["total_teto"] == 1800.0 and d["hero"]["gasto_com_teto"] == 0 and d["hero"]["gasto_sem_teto"] == 50.0
       and d["hero"]["percentual_uso"] == 0.0 and d["hero"]["status"] == "folgado", d["hero"])
d = dash(6, 2026)
checar("P2c", "junho (antes de qualquer teto) -> hero percentual null, status sem_teto",
       d["hero"]["percentual_uso"] is None and d["hero"]["status"] == "sem_teto", d["hero"])

# 9 e ponto 4: dias restantes ---------------------------------------------------
hoje = date.today()
esperado = calendar.monthrange(hoje.year, hoje.month)[1] - hoje.day
checar(9, f"dias_restantes do mes atual pelo endpoint ({hoje})", dash(hoje.month, hoje.year)["dias_restantes_no_mes"] == esperado, esperado)
for mes, ano, h_, esp, rotulo in ((10, 2026, date(2026, 10, 22), 9, "mes atual em 22/10"),
                                  (9, 2026, date(2026, 10, 22), 0, "mes passado"),
                                  (11, 2026, date(2026, 10, 22), 30, "mes futuro = mes inteiro"),
                                  (2, 2028, date(2026, 10, 22), 29, "fev/2028 futuro (bissexto)"),
                                  (12, 2026, date(2026, 12, 31), 0, "31/12 no proprio mes")):
    checar("P4", f"dias_restantes {rotulo} -> {esp}", db_dashboard.dias_restantes_no_mes(mes, ano, h_) == esp,
           db_dashboard.dias_restantes_no_mes(mes, ano, h_))

# 5 e 17-18: fatura real em outubro --------------------------------------------
pdf = Path(sys.argv[2]).read_bytes()
cliente.post("/fatura/importar", data={"arquivo": (io.BytesIO(pdf), "f.pdf")}, content_type="multipart/form-data")
d = dash(10, 2026)
checar(5, "outubro com a fatura: total_gasto 1699.21, 23 sem categoria",
       d["hero"]["total_gasto"] == 1699.21 and d["quantidade_sem_categoria"] == 23 and d["valor_sem_categoria"] == 1699.21,
       (d["hero"]["total_gasto"], d["quantidade_sem_categoria"]))
checar("5b", "outubro herda os tetos de agosto (1800); gasto_com_teto 0 com tudo sem categoria",
       d["hero"]["total_teto"] == 1800.0 and d["hero"]["gasto_com_teto"] == 0 and d["hero"]["gasto_sem_teto"] == 1699.21, d["hero"])

outubro = cliente.get("/lancamentos?mes=10&ano=2026").get_json()
decathlon = next(l for l in outubro if l["descricao"].startswith("DECATHLON"))
cliente.post(f"/lancamentos/{decathlon['id']}/categorizar", json={"subcategoria_id": S[6]})
d = dash(10, 2026)
checar(17, "categorizar DECATHLON (66.66) -> 22 sem categoria, valor 1632.55, Esporte 66.66",
       d["quantidade_sem_categoria"] == 22 and d["valor_sem_categoria"] == 1632.55 and por_macro(d, 6)["gasto"] == 66.66,
       (d["quantidade_sem_categoria"], d["valor_sem_categoria"]))
checar("17b", "total_gasto nao muda ao categorizar (1699.21)", d["hero"]["total_gasto"] == 1699.21)
for l in outubro:
    if l["id"] != decathlon["id"]:
        cliente.put(f"/lancamentos/{l['id']}", json={"subcategoria_id": S[1]})
d = dash(10, 2026)
v = d["categorias"][-1]
checar(18, "tudo categorizado -> 'Sem categoria' com gasto 0 e quantidade 0 (continua presente e no fim)",
       v["categoria_virtual_nome"] == "Sem categoria" and v["gasto"] == 0 and v["quantidade"] == 0
       and d["quantidade_sem_categoria"] == 0, v)
checar("18b", "Alimentacao 1632.55 / 800 -> estourado; hero soma Esporte+Alimentacao com teto",
       por_macro(d, 1)["status"] == "estourado" and d["hero"]["gasto_com_teto"] == 1699.21, d["hero"])

# 19-21: últimos lançamentos -------------------------------------------------------
inserir("2026-10-15", "MAIS NOVO (criado depois)", 5, S[2], criado_em="2026-10-15T10:00:00")
inserir("2026-10-15", "CRIADO ANTES (id maior)", 5, None, criado_em="2026-10-15T09:00:00")
d = dash(10, 2026)
u = d["ultimos_lancamentos"]
checar(19, "exatamente 3 itens", len(u) == 3, len(u))
checar(20, "data DESC, depois criado_em DESC (o de id maior mas criado antes vem depois), depois id DESC",
       [x["descricao"] for x in u[:2]] == ["MAIS NOVO (criado depois)", "CRIADO ANTES (id maior)"]
       and u[2]["data"] == "2026-10-01" and u[2]["id"] == max(l["id"] for l in outubro), [x["descricao"] for x in u])
checar(21, "inclui nomes de subcategoria e macro (JOIN) e o formato do GET",
       u[0]["subcategoria_nome"] == "Sub 2" and u[0]["categoria_macro_nome"] == "Lazer"
       and set(u[0]) == set(outubro[0]), {k: u[0][k] for k in ("subcategoria_nome", "categoria_macro_nome")})
checar("21b", "lancamento sem categoria no 'ultimos' traz subcategoria_sugerida (chave presente)",
       "subcategoria_sugerida" in u[1] and u[1]["subcategoria_id"] is None)
checar("19b", "mes com menos de 3 lancamentos (setembro: 1) -> 1 item", len(dash(9, 2026)["ultimos_lancamentos"]) == 1)

# Contagem de queries ------------------------------------------------------------
queries = []
originais = {m: m.conectar for m in (db_dashboard, db_lancamentos, db_tetos)}


def rastreando(original):
    def conectar():
        conexao = original()
        conexao.set_trace_callback(queries.append)
        return conexao
    return conectar


for modulo, original in originais.items():
    modulo.conectar = rastreando(original)
dash(10, 2026)
for modulo, original in originais.items():
    modulo.conectar = original
selects = [q for q in queries if q.lstrip().upper().startswith("SELECT")]
checar("Q", "queries por GET /dashboard (esperado ~20)", 15 <= len(selects) <= 22, f"{len(selects)} SELECTs")

print(f"\nfalhas: {falhas}")
inicializar.CAMINHO_BANCO.unlink()
Path(pasta).rmdir()

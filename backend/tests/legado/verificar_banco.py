import sqlite3
import sys

c = sqlite3.connect(sys.argv[1])
um = lambda sql: c.execute(sql).fetchone()[0]
print("total de linhas:", um("SELECT COUNT(*) FROM lancamentos"))
print("datas distintas:", c.execute("SELECT DISTINCT data FROM lancamentos").fetchall())
print("origens distintas:", c.execute("SELECT DISTINCT origem FROM lancamentos").fetchall())
print("soma dos valores:", round(um("SELECT SUM(valor) FROM lancamentos"), 2))
print("com parcela:", um("SELECT COUNT(*) FROM lancamentos WHERE parcela_total IS NOT NULL"))
print("sem parcela (NULL):", um("SELECT COUNT(*) FROM lancamentos WHERE parcela_atual IS NULL AND parcela_total IS NULL"))
print("subcategoria NULL:", um("SELECT COUNT(*) FROM lancamentos WHERE subcategoria_id IS NULL"))
print("exemplo:", c.execute("SELECT * FROM lancamentos WHERE parcela_total IS NOT NULL LIMIT 1").fetchone())
c.close()

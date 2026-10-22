import sqlite3
import sys

sys.path.insert(0, sys.argv[1])
from inicializar import conectar

c = conectar()
tabelas = c.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY rowid"
).fetchall()
print("tabelas:", [r[0] for r in tabelas])
print("foreign_keys:", c.execute("PRAGMA foreign_keys").fetchone()[0])
try:
    c.execute("INSERT INTO subcategorias (nome, categoria_macro_id) VALUES ('teste', 999)")
    print("ERRO: FK nao bloqueou")
except sqlite3.IntegrityError as e:
    print("FK bloqueou:", e)
c.rollback()
print("subcategorias no banco:", c.execute("SELECT COUNT(*) FROM subcategorias").fetchone()[0])
c.close()

import sqlite3
import sys

sys.path.insert(0, sys.argv[1])
from inicializar import conectar

c = conectar()
casos = [
    ("mes = 13", (1, 13, 2026, 500.0)),
    ("valor = -100", (1, 10, 2026, -100.0)),
    ("valido (mes 10, valor 500)", (1, 10, 2026, 500.0)),
]
for nome, params in casos:
    try:
        c.execute(
            "INSERT INTO tetos (categoria_macro_id, mes, ano, valor) VALUES (?, ?, ?, ?)",
            params,
        )
        print(f"{nome}: ACEITO")
    except sqlite3.IntegrityError as e:
        print(f"{nome}: REJEITADO -> {e}")
c.rollback()
print("tetos no banco apos rollback:", c.execute("SELECT COUNT(*) FROM tetos").fetchone()[0])
print("categorias_macro:", c.execute("SELECT * FROM categorias_macro").fetchall())
c.close()

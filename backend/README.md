# Backend

API REST (Flask + SQLite) do controle financeiro. A lista de endpoints está no [README da raiz](../README.md#api) e as regras de cada recurso no [DECISOES.md](../DECISOES.md).

## Como rodar

```powershell
# A partir da raiz do projeto: ativar o ambiente virtual
.\venv\Scripts\Activate.ps1

# Instalar dependências (se ainda não instaladas)
pip install -r requirements.txt

# Rodar o servidor
python backend/main.py
```

Acesse http://127.0.0.1:5000/ — deve exibir "Olá, controle financeiro". O banco é criado automaticamente na primeira requisição.

## Estrutura

```
backend/
├── main.py                 # Rotas Flask: validação de entrada e tradução de erros para HTTP
└── app/
    ├── fatura/
    │   └── leitor.py       # Parser da fatura Bradesco (lançamentos, parcelas, competência, total)
    └── db/                 # Um arquivo por recurso, SQL puro (ADR-004)
        ├── schema.sql      # 5 tabelas, foreign keys e CHECKs
        ├── inicializar.py  # Cria o banco, popula as 8 macro; conectar() liga as foreign keys
        ├── lancamentos.py  # Importação, CRUD de lançamentos, categorização
        ├── categorias.py   # Macro (leitura) e subcategorias (CRUD)
        ├── tetos.py        # Tetos por mês com herança
        ├── aprendizados.py # Normalização do padrão, sugestões e regras de aprendizado
        ├── dashboard.py    # Agregação do mês: hero, breakdown por status, últimos lançamentos
        └── financas.db     # Banco local (fora do Git)
```

**Divisão de responsabilidades:** o `main.py` valida formato e tipos e traduz exceções em status HTTP; os módulos de `app/db/` aplicam as regras de negócio e levantam exceções próprias (ex: `EdicaoBloqueada` → 403). Toda conexão passa por `inicializar.conectar()`, que ativa `PRAGMA foreign_keys = ON`.

## Parser isolado

O parser pode ser testado sem subir a API:

```powershell
python backend/app/fatura/leitor.py "caminho\da\fatura.pdf"
```

Mostra a competência, o total do cabeçalho, a contagem de lançamentos e parcelados, os 5 primeiros parcelados e a soma.

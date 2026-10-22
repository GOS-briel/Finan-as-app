# Finanças App

[![Testes](https://github.com/GOS-briel/Finan-as-app/actions/workflows/tests.yml/badge.svg)](https://github.com/GOS-briel/Finan-as-app/actions/workflows/tests.yml)

App de controle financeiro pessoal focado em fricção baixa (registrar um gasto em menos de 10 segundos) e controle por tetos macro de categorias.

## Estado atual

🚧 **Em desenvolvimento** — trilha PWA + Python (Flask). **Backend da v1 completo** (API REST); frontend PWA ainda não iniciado.

## Funcionalidades (v1)

- Dashboard com gasto vs orçamento do mês e tetos por categoria
- Registro rápido de gastos manuais
- Histórico agrupado por categoria
- Importação de fatura Bradesco (PDF) com categorização por sugestões aprendidas
- Compras parceladas: a parcela é registrada no mês da fatura, com "Parcela X/Y" identificada (ADR-002)

## Categorias

**Macro (fixas):** Alimentação, Lazer, Compras, Saúde, Educação, Esporte, Transporte, Outros
**Subcategorias:** customizáveis pelo usuário

## Stack

- **Backend:** Python 3.13+ + Flask
- **Leitura de PDF:** pdfplumber
- **Persistência:** SQLite com `sqlite3` puro, sem ORM (ADR-001, ADR-004)
- **Frontend:** HTML + CSS + JavaScript (PWA)
- **Testes:** pytest + pytest-cov; CI no GitHub Actions (Python 3.13)

## Como rodar (dev)

```powershell
# Criar e ativar o ambiente virtual
py -m venv venv
.\venv\Scripts\Activate.ps1  # Windows PowerShell

# Instalar dependências
pip install -r requirements.txt

# Rodar a API em http://127.0.0.1:5000
python backend/main.py
```

O banco (`backend/app/db/financas.db`) é criado automaticamente na primeira requisição, com as 8 categorias macro. Para criá-lo manualmente: `python backend/app/db/inicializar.py`. O arquivo fica fora do Git (dados pessoais).

### Testes

```powershell
# Dependências de teste (uma vez)
pip install -r requirements-dev.txt

# Suíte completa
pytest

# Com cobertura (falha abaixo de 80%)
pytest --cov=backend --cov-report=term-missing

# Incluindo os testes com a fatura real (o PDF não vai para o Git)
$env:FATURA_PDF_PATH = "caminho\da\fatura.pdf"; pytest
```

A suíte fica em `tests/` (`unit/`, `integration/`, `e2e/`) e usa sempre um banco SQLite temporário — o `financas.db` real nunca é tocado. Sem `FATURA_PDF_PATH`, os testes com a fatura real são pulados (como no CI). Detalhes na ADR-024.

## API

Todas as respostas são JSON; erros vêm como `{"erro": "..."}`. Corpos aceitam JSON ou formulário. Regras detalhadas de cada recurso estão nas ADRs indicadas ([DECISOES.md](DECISOES.md)).

| Método | Rota | Para que serve | ADRs |
|---|---|---|---|
| GET | `/` | Health check | — |
| POST | `/fatura/importar` | Upload do PDF (`arquivo`, `mes`/`ano` opcionais); grava os lançamentos sem duplicar | 007, 009, 010 |
| GET | `/categorias/macro` | As 8 macro com subcategorias embutidas, em ordem alfabética natural | 011, 012 |
| POST | `/subcategorias` | Cria subcategoria (`nome`, `categoria_macro_id`) | 011, 012 |
| PUT | `/subcategorias/<id>` | Renomeia subcategoria | 012 |
| DELETE | `/subcategorias/<id>` | Apaga, se não houver lançamentos nem aprendizados vinculados | 011 |
| GET | `/tetos?mes=&ano=` | Teto das 8 macro no mês, com herança do mês anterior | 013 |
| PUT | `/tetos` | Define ou atualiza um teto (upsert) | 014 |
| DELETE | `/tetos?categoria_macro_id=&mes=&ano=` | Remove o teto do mês (volta a herdar) | 014 |
| GET | `/lancamentos?mes=&ano=` | Lançamentos do mês, com `subcategoria_sugerida`. Filtros: `categoria_macro_id`, `origem`, `sem_categoria=true` | 018 |
| POST | `/lancamentos` | Cria lançamento manual (até 90 dias no passado) | 015 |
| PUT | `/lancamentos/<id>` | Edita; importados só aceitam `subcategoria_id` e `nota` | 016, 017 |
| DELETE | `/lancamentos/<id>` | Apaga definitivamente | 016 |
| POST | `/lancamentos/<id>/categorizar` | Categoriza **e** ensina o app (ou descategoriza com `null`) | 017, 019, 020 |
| GET | `/dashboard?mes=&ano=` | Visão do mês: hero (gasto vs orçamento), breakdown das 8 macro + "Sem categoria", últimos 3 lançamentos | 021, 022, 023 |

## Autor

Gabriel de Oliveira Silva — [GOS-briel](https://github.com/GOS-briel)

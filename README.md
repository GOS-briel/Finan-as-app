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

---

## 📌 Marcador de retomada (atualizado em 2026-10-22)

Esta seção serve para retomar o projeto rapidamente em sessões futuras sem reexplicar contexto.

### Status atual

**Backend — v1 completo (Etapas 1 a 10):**
- ✅ Parser Bradesco (extração, parcelas, competência pelo vencimento, conferência do total)
- ✅ Importação da fatura gravando no SQLite, com deduplicação por contagem
- ✅ Schema SQLite (5 tabelas) com foreign keys e CHECKs
- ✅ CRUD de subcategorias (macro fixas)
- ✅ CRUD de tetos com herança automática do mês anterior
- ✅ CRUD de lançamentos manuais, com proteção dos importados
- ✅ Categorização por aprendizado, com sugestões no GET
- ✅ Dashboard agregado (`GET /dashboard`) — Etapa 10, última do backend v1
- ✅ Suíte pytest (330 testes, 99% de cobertura) + CI no GitHub Actions — Etapa 11

**Frontend — não iniciado (começa na Etapa 12):**
- 4 telas definidas em mockups (Dashboard, Registrar, Histórico, Importar)
- Não existe código ainda

### Próxima etapa — Etapa 12: frontend PWA

As 4 telas dos mockups (Dashboard, Registrar, Histórico, Importar), consumindo a API. Antes da primeira tela que chama a API de outra origem: **configurar CORS** (pendência abaixo).

A suíte de testes (Etapa 11) roda a cada push: qualquer mudança no backend que o frontend exigir é validada pelo CI.

### Decisões já tomadas

Ver [DECISOES.md](DECISOES.md) (detalhes) e [BACKLOG.md](BACKLOG.md) (features adiadas):

| ADR | Decisão |
|---|---|
| 001 | SQLite no backend |
| 002 | Parcela registrada no mês da fatura |
| 003 | Transações internacionais: tratamento especial adiado |
| 004 | SQL puro (`sqlite3`), sem ORM |
| 005 | Categorias em duas tabelas (macro fixas + subcategorias) |
| 006 | Teto por mês/ano |
| 007 | Lançamento importado com data `AAAA-MM-01` |
| 008 | Aprendizado pela descrição limpa |
| 009 | Competência da fatura = mês/ano do vencimento |
| 010 | Deduplicação da importação por contagem |
| 011 | Endpoints de categorias (subs embutidas, DELETE bloqueado se em uso) |
| 012 | Nomes sem diferenciar maiúsculas e ordenação natural |
| 013 | Herança de tetos calculada em runtime |
| 014 | Tetos: PUT upsert e DELETE que volta à herança |
| 015 | Lançamento manual: até 90 dias no passado, nunca no futuro |
| 016 | Importados só editam subcategoria e nota; DELETE definitivo |
| 017 | PUT categoriza em silêncio; `categorizar` aprende |
| 018 | Sugestão embutida no GET, 1 query em lote |
| 019 | Regras de aprendizado (criado/reforçado/sobrescrito/apagado/...) |
| 020 | Sugestão a partir de 1 confirmação |
| 021 | Estrutura do dashboard e categoria virtual "Sem categoria" |
| 022 | Status por threshold (80%) e cálculo do hero |
| 023 | Ordenação do breakdown por status |
| 024 | Testes com pytest, cobertura mínima de 80% e CI no GitHub Actions |

### Pendências técnicas identificadas

- **CORS** — obrigatório antes do frontend consumir a API de outra origem
- **MAX_CONTENT_LENGTH** — limitar o tamanho do upload da fatura
- **Fuso horário** — TODO no `main.py`: usar `ZoneInfo("America/Sao_Paulo")` ao hospedar (ADR-015)
- **Validação duplicada** — regras no `main.py` e nos CHECKs do `schema.sql`: mudar uma exige sincronizar a outra
- **Transações internacionais** — adiadas (ADR-003)

### Ambientes de desenvolvimento

- Máquina principal: `D:\financas-app` (Python 3.13.15)
- Máquina trabalho: `C:\Users\br0098346777\Documents\Finan-as-app` (Python 3.14)
- Ambas sincronizadas via GitHub — sempre `git pull` antes de nova sessão
- Local pode ser Python 3.13 ou mais novo; o CI usa 3.13 (o menor suportado). Em cada máquina: `pip install -r requirements-dev.txt` para rodar os testes
- O `financas.db` não vai pelo Git: em cada máquina, ele é criado na primeira execução

### Fatura de referência para testes

Fatura Bradesco de 10/10/2026, utilizada para validar o parser:
- 23 lançamentos extraídos
- Total de despesas: R$ 1.699,21 (confere com o total do cabeçalho)
- 6 lançamentos parcelados identificados corretamente
- Competência detectada: 10/2026

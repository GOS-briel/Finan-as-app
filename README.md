# Finanças App

App de controle financeiro pessoal focado em fricção baixa (registrar um gasto em menos de 10 segundos) e controle por tetos macro de categorias.

## Estado atual

🚧 **Em desenvolvimento** — trilha PWA + Python (Flask), fase de setup inicial.

## Funcionalidades planejadas (v1)

- Dashboard com gasto vs orçamento do mês e tetos por categoria
- Registro rápido de gastos manuais
- Histórico agrupado por categoria
- Importação de fatura Bradesco (PDF) com categorização semi-automática
- Tratamento de compras parceladas (registra parcela atual + gera futuras)

## Categorias

**Macro (fixas):** Alimentação, Lazer, Compras, Saúde, Educação, Esporte, Transporte, Outros
**Subcategorias:** customizáveis pelo usuário

## Stack

- **Backend:** Python 3.13 + Flask
- **Leitura de PDF:** pdfplumber
- **Persistência:** SQLite (backend) — a definir
- **Frontend:** HTML + CSS + JavaScript (PWA)

## Como rodar (dev)

\\\ash
# Criar e ativar o ambiente virtual
py -m venv venv
.\venv\Scripts\Activate.ps1  # Windows PowerShell

# Instalar dependências
pip install -r requirements.txt

# Rodar (a implementar)
python backend/main.py
\\\

## Autor

Gabriel de Oliveira Silva — [GOS-briel](https://github.com/GOS-briel)

---

## 📌 Marcador de retomada (atualizado em 2026-10-15)

Esta seção serve para retomar o projeto rapidamente em sessões futuras sem reexplicar contexto.

### Status atual

**Backend — parcialmente completo:**
- ✅ Parser Bradesco funcional (extração + parcelas)
- ✅ API Flask com endpoint POST /fatura/importar
- ❌ Persistência SQLite (próxima etapa)
- ❌ CRUDs de lançamentos/categorias/tetos
- ❌ Categorização automática por aprendizado

**Frontend — não iniciado:**
- 4 telas definidas em mockups (Dashboard, Registrar, Histórico, Importar)
- Não existe código ainda

### Decisões já tomadas

Ver DECISOES.md:
- ADR-001: SQLite no backend
- ADR-002: Data de parcela = mês da fatura
- ADR-003: Transações internacionais adiadas

### Próxima etapa — Etapa 5

Criar o modelo de dados SQLite com tabelas:
- categorias (8 macro fixas + subcategorias customizáveis)
- tetos (orçamento mensal por categoria)
- lancamentos (dados extraídos ou registrados manualmente)
- aprendizados (dicionário interno para categorização automática)

### Pendências técnicas identificadas

A serem endereçadas em etapas futuras:
- MAX_CONTENT_LENGTH (limitar tamanho de upload)
- CORS (para o frontend consumir a API)
- Persistência no SQLite (etapa 5)

### Ambientes de desenvolvimento

- Máquina principal: `D:\financas-app` (Python 3.13.15)
- Máquina trabalho: `C:\Users\br0098346777\Documents\Finan-as-app` (Python 3.14)
- Ambas sincronizadas via GitHub — sempre `git pull` antes de nova sessão

### Fatura de referência para testes

Fatura Bradesco de 10/10/2026, utilizada para validar o parser:
- 23 lançamentos extraídos
- Total de despesas: R$ 1.699,21
- 6 lançamentos parcelados identificados corretamente

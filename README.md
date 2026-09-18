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

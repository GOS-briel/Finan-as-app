# Decisões Arquiteturais

Este arquivo registra as decisões técnicas tomadas durante o desenvolvimento do app, com contexto e justificativa. Serve como memória do projeto — "por que foi feito desse jeito e não de outro".

Formato inspirado em ADRs (Architecture Decision Records), simplificado.

---

## ADR-001 — Persistência: SQLite no backend

**Data:** 2026-10-15
**Status:** Decidido

### Contexto

O app precisa persistir lançamentos, categorias, tetos e metadados. Duas opções foram consideradas:
- **A:** SQLite num servidor Flask (dados centralizados, API REST)
- **B:** IndexedDB no navegador (dados locais no celular, sem servidor)

### Decisão

**SQLite no backend (Opção A).**

### Justificativa

1. Dados centralizados permitem acessar o app de múltiplos dispositivos do mesmo usuário (celular, outro celular, tablet).
2. Habilidade transferível: SQL + API REST são universais no mercado de dados/dev, enquanto IndexedDB é nichado.
3. Alinhamento com a futura trilha Flutter, que também usará SQLite (modelo de dados reaproveitável como referência).
4. Backup, exportação e debugging mais simples (basta copiar o arquivo .db).
5. Risco de perda por limpeza de cache do navegador fica eliminado.

### Trade-offs aceitos

- Precisa hospedar o backend em algum lugar (começa local; depois tiers gratuitos de Railway/Render/Fly.io quando for pro celular fora de casa).
- Mais código a escrever (API Flask com rotas CRUD).

---

## ADR-002 — Data de parcelas: mês atual da fatura

**Data:** 2026-10-15
**Status:** Decidido

### Contexto

Ao importar uma fatura que contém compras parceladas (ex: "MAGAZINE LUIZA 4/10"), a parcela daquele mês representa uma compra feita vários meses atrás. Qual data atribuir ao lançamento?

Opções consideradas:
- **A:** Data original da compra
- **B:** Mês atual da fatura
- **C:** Guardar as duas datas em colunas separadas

### Decisão

**Mês atual da fatura (Opção B)**, com proteção: campos parcela_atual e parcela_total adicionados ao lançamento, e descrição com sufixo " - Parcela X/Y" para rastreabilidade visual.

Exemplo de lançamento gerado:
- Descrição: "DECATHLON NITEROI - Parcela 5/6"
- Data: "08/05"
- Valor: 66.66
- parcela_atual: 5
- parcela_total: 6

### Justificativa

1. A pergunta principal do app é "estou no controle este mês?" — resolvida com data de cobrança, não data de compra.
2. Alinha com a realidade do bolso: o dinheiro sai no mês da fatura, não no mês da compra.
3. Dashboard de qualquer mês soma os lançamentos daquele mês diretamente, sem lógica extra.
4. A informação "foi parcelado" é preservada em campos dedicados (parcela_atual, parcela_total).

### Implementado em

Etapa 2 do parser Bradesco (backend/app/fatura/leitor.py).

### Trade-offs aceitos

- Perde a informação precisa da data original da compra (precisa consultar fatura antiga para auditoria).
- Análise anual tipo "quanto gastei em março" fica distorcida — ok para a v1.

### Reabrir se:

Análise histórica por data de compra virar necessidade real → migrar para ADR-002b com Opção C.

---

## ADR-003 — Transações internacionais: adiado (revisado com dados reais)

**Data original:** 2026-10-15
**Status:** Decidido → Revisto no mesmo dia após teste com fatura real, decisão adiada

### Contexto original (invalidado)

A ADR original assumia que a fatura Bradesco mostra transações internacionais em formato de "dupla moeda" (ex: USD 15,99 R$ 89,47), e que suas descrições seriam poluídas (ex: NETFLIX*.COM). A decisão foi: marcar essas linhas para revisão manual (chip de aviso na UI).

### Realidade descoberta ao testar o parser com fatura real (15/10/2026)

- A fatura Bradesco NÃO mostra transações internacionais em dupla moeda. O valor aparece já convertido em reais, sem indicação visual de moeda estrangeira na linha.
- A única compra internacional recorrente do usuário é a assinatura do Claude Pro (~R$ 110/mês).
- O IOF da transação internacional aparece como lançamento separado, com descrição clara: "IOF S/ TRANS INTER REAIS".
- Descrições de internacionais (ex: "ANTHROPIC* CLAUDE SUB 110,00ANTHROPIC.C") vêm com texto embutido, mas não com dupla moeda.

### Nova decisão

**Adiar o tratamento especial de transações internacionais até que:**
1. O volume de compras internacionais aumente significativamente, OU
2. Padrões reais de "ruído" na descrição sejam identificados após uso contínuo do app

**Enquanto isso:**
- Transações internacionais entram no app como lançamentos normais (sem flag especial)
- Usuário categoriza manualmente ao importar fatura (ex: "Assinaturas", "Outros")
- IOF entra como lançamento normal também (pode ser categorizado como "Outros" ou criada subcategoria "Impostos")

### Justificativa

Investir código para resolver um problema que afeta 1 lançamento recorrente por mês é desproporcional ao escopo da v1. O princípio do app é "fricção baixa + aprender com o uso" — a decisão certa aqui é aguardar dados reais antes de projetar solução.

### Reabrir quando:

- O usuário tiver 5+ transações internacionais/mês de origens variadas
- Padrões de descrição mal formatada forem identificados
- Houver demanda real por análise específica de gastos internacionais

---

## Convenções deste arquivo

- Decisões reabertas viram ADR-NNN-v2 com link pra versão anterior.
- Status possíveis: Proposto, Decidido, Substituído por ADR-XXX, Obsoleto, Adiado.
- Toda decisão nova entra no final, com data e número incremental.

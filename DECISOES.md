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

---

## ADR-004 — SQL puro em vez de ORM

**Data:** 2026-10-18
**Status:** Decidido

### Contexto

Para persistir dados no SQLite, duas abordagens foram consideradas:
- **A:** SQLAlchemy ou outro ORM (mapeamento objeto-relacional)
- **B:** SQL puro usando o módulo `sqlite3` nativo do Python

### Decisão

**SQL puro (Opção B).**

### Justificativa

1. SQL é habilidade universal no mercado de analista de dados (área que o usuário quer migrar). SQLAlchemy é específico de dev Python backend.
2. Transparência total: cada operação é explícita, sem "mágica" por baixo.
3. Zero dependência adicional (sqlite3 já vem com Python).
4. Escopo pequeno (4 tabelas) não justifica a complexidade de um ORM.
5. Alinhado com o aprendizado ativo — expor o SQL em vez de abstrai-lo.

### Trade-offs aceitos

- Mais linhas de código em operações CRUD repetitivas (INSERT, UPDATE, DELETE escritos manualmente).
- Risco de SQL injection se queries forem concatenadas manualmente (mitigado usando sempre `cursor.execute(sql, params)` com parâmetros).

### Reabrir se:

Projeto crescer para 15+ tabelas com relacionamentos complexos, OU houver necessidade de trocar o banco (PostgreSQL, MySQL).

---

## ADR-005 — Estrutura de categorias: duas tabelas separadas

**Data:** 2026-10-18
**Status:** Decidido

### Contexto

As categorias do app têm hierarquia fixa de 2 níveis: 8 categorias macro fixas (Alimentação, Lazer, Compras, Saúde, Educação, Esporte, Transporte, Outros) + subcategorias customizáveis pelo usuário.

Duas estruturas foram consideradas:
- **A:** Uma única tabela `categorias` com campo `tipo` ("macro" ou "sub") e campo `categoria_pai_id` auto-referente
- **B:** Duas tabelas separadas: `categorias_macro` e `subcategorias` com foreign key

### Decisão

**Duas tabelas separadas (Opção B).**

### Justificativa

1. Reflete a natureza real do domínio: hierarquia fixa de exatamente 2 níveis.
2. Impossível misturar macro com sub por engano (constraint estrutural).
3. Queries mais limpas (sem self-join, sem filtro `WHERE tipo = ...`).
4. Mais intuitivo para iniciante entender e manter.

### Trade-offs aceitos

- Se um dia precisar de sub-sub-categoria (nível 3), precisaria criar nova tabela. Isso é improvável para um app de controle financeiro pessoal.

---

## ADR-006 — Teto por mês (não fixo)

**Data:** 2026-10-18
**Status:** Decidido

### Contexto

Cada categoria macro tem um teto de orçamento mensal. Duas opções foram consideradas:
- **A:** Teto fixo (um valor por categoria, vale pra todo mês)
- **B:** Teto por mês/ano (cada mês pode ter seu próprio teto por categoria)

### Decisão

**Teto por mês/ano (Opção B).**

### Justificativa

1. Realidade do usuário: dezembro (festas, 13º) e janeiro (volta das férias) têm padrões financeiros diferentes do resto do ano.
2. Preserva histórico de evolução dos tetos ao longo do tempo.
3. Custo adicional de implementação é mínimo (2 colunas: `mes` e `ano`).
4. Migração futura de A para B seria custosa (reescrita, risco de perda de dados). Fazer certo na origem é mais barato.

### Trade-offs aceitos

- Setup inicial exige definir tetos para pelo menos o mês atual (não é "cria uma vez e esquece").
- Lógica da API precisa decidir o que fazer quando não há teto definido para um mês específico (herdar do anterior? mostrar vazio? default?). Essa decisão será feita na etapa de API, não na modelagem.

---

## ADR-007 — Data dos lançamentos importados: primeiro dia do mês da fatura

**Data:** 2026-10-18
**Status:** Decidido

### Contexto

Quando lançamentos são importados do PDF da fatura Bradesco, o parser extrai apenas `DD/MM` (sem ano) e podem representar compras parceladas de meses anteriores. É necessário decidir qual data (completa, com ano) atribuir ao campo `data` da tabela `lancamentos`.

Opções consideradas:
- **1:** Dia de fechamento da fatura
- **2:** Dia de vencimento da fatura
- **3:** Primeiro dia do mês de competência da fatura (ex: 2026-10-01 para fatura de outubro/2026)
- **4:** Preservar o dia original + apenas inferir o ano

### Decisão

**Opção 3 — primeiro dia do mês de competência da fatura.**

### Justificativa

1. Honra a ADR-002 (data = mês da fatura, não da compra original).
2. Dia específico dentro do mês é irrelevante para o controle de teto mensal — o que importa é "é um gasto deste mês".
3. Simples de calcular (não precisa parsear datas específicas).
4. Dashboard mostra "outubro/2026" sem precisar entrar em detalhe de dia.

### Regra consolidada de preenchimento do campo `data`

| Origem do lançamento | Formato da data |
|---|---|
| Importado da fatura | `AAAA-MM-01` (primeiro dia do mês de competência) |
| Registrado manualmente | Data real escolhida pelo usuário (default = hoje) |

### Trade-offs aceitos

- Perde a informação do dia específico da compra para lançamentos de fatura. Aceitável — já perdemos a data real da compra parcelada por decisão da ADR-002.

---

## ADR-008 — Matching de aprendizado: descrição completa limpa

**Data:** 2026-10-18
**Status:** Decidido

### Contexto

A tabela `aprendizados` guarda mapeamentos "padrão de descrição → subcategoria" para que o app sugira automaticamente a categoria em importações futuras. Precisa-se decidir como identificar que duas descrições diferentes são "do mesmo tipo" para fazer match.

Opções consideradas:
- **A:** Prefixo da descrição (primeira palavra)
- **B:** Descrição completa normalizada (remove sufixos variáveis como " - Parcela X/Y")
- **C:** Palavras-chave com LIKE SQL
- **D:** Usuário escolhe o padrão na interface no momento de categorizar

### Decisão

**Opção B — descrição completa limpa, com Opção D guardada como melhoria futura.**

### Regra de normalização para o campo `padrao_descricao`

Antes de salvar na tabela `aprendizados`, remover da descrição:
- Sufixo " - Parcela X/Y"
- Números soltos no final da string
- Mantém o resto como-está

Exemplos:
- `DECATHLON NITEROI - Parcela 5/6` → padrão: `DECATHLON NITEROI`
- `DECATHLON NITEROI - Parcela 6/6` → padrão: `DECATHLON NITEROI` → **match!**

### Justificativa

1. Menor risco de agrupar erroneamente lançamentos diferentes com mesmo prefixo (ex: "PÃO DE AÇÚCAR" vs "PÃO DE QUEIJO").
2. Simples de implementar na v1.
3. Especificidade suficiente para o caso comum (reconhecer repetições de mesmo lugar).

### Trade-offs aceitos

- Menos genérico que Opção A: se usuário comprar na DECATHLON de outra cidade, não reconhece automaticamente.
- Se usuário sentir que B é restritivo demais, considerar migrar para Opção D (deixar usuário escolher o padrão na UI).

### Reabrir se:

- Usuário relatar fricção com a Opção B em uso real (muitos aprendizados similares sendo criados para variações mínimas).
- Volume de aprendizados crescer e análise mostrar que a Opção B gera dicionário com muitos duplicados "semânticos".

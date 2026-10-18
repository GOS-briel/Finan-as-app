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

---

## ADR-009 — Competência da fatura: mês/ano do vencimento

**Data:** 2026-10-18
**Status:** Decidido

### Contexto

A ADR-007 define que lançamentos importados recebem a data `AAAA-MM-01` do mês de competência da fatura. O parser, porém, só extrai `DD/MM` de cada lançamento (sem ano), então é preciso descobrir o mês/ano de competência de outra forma.

Investigação no PDF real (fatura de 10/10/2026) mostrou que:
- Não existe "período de competência" nem "data de fechamento desta fatura" no texto.
- Existe a **data de vencimento** no cabeçalho da 1ª página (rótulo "Vencimento" numa linha, data `DD/MM/AAAA` na linha seguinte), repetida no boleto.
- Existe apenas a previsão de fechamento da **próxima** fatura (não serve).

Opções consideradas:
- **A:** Mês/ano do vencimento, extraído do PDF
- **B:** Sempre pedir mês/ano ao usuário no upload
- **C:** Inferir pelas datas dos lançamentos (ex: a data mais recente)

### Decisão

**Opção A, com o formulário como fallback e prioridade.**

- O endpoint lê o vencimento do cabeçalho e usa o seu mês/ano como competência.
- Se o formulário enviar `mes` e `ano`, eles têm prioridade sobre o detectado.
- Se não detectar e o formulário não enviar, o endpoint retorna 422 com `"pedir_do_usuario": true`, e o frontend pergunta ao usuário.
- A resposta informa a fonte (`"fonte": "pdf"` ou `"formulario"`).

### Justificativa

1. Vencimento é o momento em que o dinheiro sai — coerente com a ADR-002 ("o dinheiro sai no mês da fatura").
2. Está sempre presente no PDF (é um dado obrigatório do boleto).
3. Zero fricção no caso comum; o usuário só é consultado quando o PDF falha.
4. Opção C é frágil: parcelas antigas têm datas de meses anteriores.

### Proteção adicional

O total oficial do cabeçalho ("Total de fatura") também é extraído e comparado com a soma dos lançamentos (`total_confere` na resposta). Se o layout da fatura mudar e o parser perder linhas, a divergência aparece na hora.

### Trade-offs aceitos

- Depende do rótulo "Vencimento" no cabeçalho do Bradesco. Mudança de layout quebra a detecção (mitigado pelo fallback 422).
- Uma fatura com vencimento em dia 1º–5º pode concentrar gastos majoritariamente do mês anterior; aceito, pois o critério é a saída do dinheiro.

### Reabrir se:

- Outro banco/cartão for suportado (cada layout terá sua regra).
- O usuário preferir competência pelo mês de fechamento.

---

## ADR-010 — Deduplicação de lançamentos de fatura por contagem

**Data:** 2026-10-18
**Status:** Decidido

### Contexto

Reimportar a mesma fatura não pode duplicar lançamentos. A chave natural de um lançamento de fatura é: descrição + valor + data + parcela_atual + parcela_total.

Problema: pela ADR-007, todo lançamento importado recebe o dia `01`, então o dia original da compra se perde. Dois lançamentos **legítimos e diferentes** — ex: dois cafés de R$ 8,00 no mesmo lugar, em dias distintos — passam a ter **a mesma chave**.

Opções consideradas:
- **A:** Chave única (UNIQUE / SELECT simples): se a chave já existe, ignora
- **B:** Contagem: insere a diferença entre ocorrências no PDF e no banco
- **C:** Guardar o dia original (DD/MM) numa coluna extra e incluí-lo na chave

### Decisão

**Opção B — deduplicação por contagem.**

Para cada chave: `n` = ocorrências no PDF, `m` = ocorrências já no banco (`origem = 'fatura'`). Insere `max(0, n − m)`.

| Situação | n | m | Inseridos |
|---|---|---|---|
| 1ª importação com 2 cafés iguais | 2 | 0 | 2 |
| Reimportação da mesma fatura | 2 | 2 | 0 |
| Importação anterior interrompida | 2 | 1 | 1 |

### Justificativa

1. A Opção A **perde gastos reais silenciosamente** já na primeira importação — inaceitável num app financeiro.
2. Reimportação continua idempotente.
3. Toda a importação roda numa transação única: ou entra a fatura inteira, ou nada.
4. Custo igual ao da Opção A (um COUNT por chave).

### Detalhe de implementação

A comparação das parcelas usa `IS` em vez de `=`: em SQL, `NULL = NULL` não é verdadeiro, e com `=` os lançamentos não parcelados nunca seriam reconhecidos como duplicata.

### Trade-offs aceitos

- Se o banco emitir uma fatura **corrigida** com um lançamento a menos, a reimportação não apaga o excedente (só insere, nunca remove).
- Um lançamento manual idêntico não conta como duplicata (só `origem = 'fatura'` entra na contagem) — por design.

### Reabrir se:

- Surgirem faturas corrigidas/retificadas na prática.
- A Opção C for necessária por outro motivo (ex: análise por dia da compra, ver ADR-002 "Reabrir se").

---

## ADR-011 — Design dos endpoints CRUD de categorias

**Data:** 2026-10-18
**Status:** Decidido

### Contexto

A Etapa 6 expõe categorias e subcategorias via API para o frontend. Três questões de design precisavam de resposta: como entregar a hierarquia macro → sub, o que fazer ao deletar uma subcategoria em uso, e se macro podem ser deletadas.

### Decisões

**1. `GET /categorias/macro` devolve cada macro com as subcategorias embutidas.**
Uma única resposta com a árvore inteira (8 macro + suas subs), em vez de um endpoint para macro e outro para subs.

**2. DELETE de subcategoria em uso é bloqueado (409), nunca em cascata nem SET NULL.**
Se houver lançamentos ou aprendizados vinculados, a resposta informa as duas contagens (`lancamentos_vinculados`, `aprendizados_vinculados`) e nada é apagado.

**3. Não existe DELETE de categoria macro.**
Macro são fixas (ADR-005). A remoção excepcional foi movida para a Etapa de Admin pós-v1 (ver BACKLOG.md).

### Justificativa

1. **Embutir:** o volume é minúsculo (8 macro + poucas dezenas de subs), e toda tela que mostra categorias precisa das duas camadas juntas. Uma requisição só = menos round-trips e frontend mais simples.
2. **Bloquear:** princípio "nada é deletado silenciosamente". Cascata apagaria gastos reais; SET NULL "descategorizaria" lançamentos sem aviso, distorcendo o dashboard. O 409 com contagem deixa o usuário decidir (recategorizar antes, ou desistir).
3. **Sem DELETE de macro:** remover uma macro afeta tetos, subs e lançamentos em cadeia. Exige confirmação, auditoria e autenticação — escopo de uma etapa própria.

### Trade-offs aceitos

- Para apagar uma subcategoria em uso, o usuário precisa recategorizar os lançamentos antes (não há "mover tudo para X" nesta etapa).
- Se o número de subs crescer muito, a resposta embutida fica maior — irrelevante na escala de um app pessoal.

### Reabrir se:

- Usuário pedir "apagar e mover lançamentos para outra subcategoria" (endpoint de merge).
- A Etapa de Admin for iniciada (DELETE de macro).

---

## ADR-012 — Consistência de nomes e ordenação de subcategorias

**Data:** 2026-10-18
**Status:** Decidido

### Contexto

Três detalhes finos apareceram ao planejar o CRUD de subcategorias, todos com impacto direto na qualidade dos dados e na experiência de uso:

1. O `UNIQUE (nome, categoria_macro_id)` do SQLite diferencia maiúsculas/minúsculas: "Delivery" e "delivery" passariam como subcategorias distintas.
2. A tabela `aprendizados` também referencia `subcategorias` (com `NOT NULL`). Deletar uma sub com aprendizados geraria erro de foreign key (500).
3. O `ORDER BY nome` do SQLite compara bytes: "Água" vai depois de "Zoológico", e minúsculas depois de todas as maiúsculas.

### Decisões

**1. Duplicata detectada sem diferenciar maiúsculas/minúsculas, no Python (`casefold()`).**
Antes de inserir ou renomear, o nome é comparado (normalizado em NFC + `casefold()`) com as subs da mesma macro. "AÇAÍ" colide com "açaí". O UNIQUE do schema continua como rede de segurança para o nome exato. Renomear uma sub para o próprio nome com outra capitalização é permitido.

**2. Aprendizados vinculados também bloqueiam o DELETE (409).**
Mesma regra dos lançamentos (ADR-011). A resposta traz `aprendizados_vinculados` — sempre 0 até a Etapa 9, mas o código já está pronto.

**3. Subcategorias ordenadas no Python, sem acento e sem diferenciar maiúsculas.**
Chave de ordenação: decomposição Unicode (NFKD), remoção dos acentos, `casefold()`. Resultado: `açaí, Água, bar, Delivery, Restaurante, Zoológico`.

### Justificativa

1. **casefold no Python e não `COLLATE NOCASE`:** o NOCASE do SQLite só trata letras ASCII — "AÇAÍ" e "açaí" continuariam diferentes. Para um app em português, isso anula o propósito.
2. **Bloquear por aprendizados:** consistência com "nada é deletado silenciosamente" e evita um 500 por violação de foreign key.
3. **Ordenação natural:** listas são a interface principal de escolha de categoria; ordem errada degrada o app inteiro.

### Trade-offs aceitos

- A checagem de duplicata lê as subs da macro a cada inserção (custo irrelevante: poucas dezenas de linhas).
- Nomes que diferem só por acento ("Acai" vs "Açaí") **são** considerados diferentes na duplicata (só a ordenação ignora acentos).
- Ordenar no Python impede paginar/ordenar via SQL — irrelevante neste volume.

### Reabrir se:

- Usuário criar duplicatas "por acento" na prática (considerar ignorar acentos também na duplicata).
- O volume de subcategorias crescer a ponto de exigir paginação.

---

## Convenções deste arquivo

- Decisões reabertas viram ADR-NNN-v2 com link pra versão anterior.
- Status possíveis: Proposto, Decidido, Substituído por ADR-XXX, Obsoleto, Adiado.
- Toda decisão nova entra no final, com data e número incremental.

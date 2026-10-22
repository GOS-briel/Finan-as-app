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

## ADR-013 — Herança de tetos: mês anterior mais recente, calculada em runtime

**Data:** 2026-10-18
**Status:** Decidido

### Contexto

A ADR-006 definiu teto por mês/ano e deixou em aberto: "o que fazer quando não há teto definido para um mês específico (herdar do anterior? mostrar vazio? default?)". Sem uma regra, o usuário teria de recadastrar os 8 tetos todo mês — fricção alta para um app cujo princípio é "fricção baixa".

Opções consideradas:
- **A:** Mostrar vazio (usuário cadastra todo mês)
- **B:** Herdar do mês anterior mais recente, calculando na hora da consulta
- **C:** Herdar copiando (materializando) a linha no banco quando o mês é consultado ou virado
- **D:** Um teto "padrão" por categoria, sobrescrito por mês

### Decisão

**Opção B — herança do mês anterior mais recente, em runtime, sem gravar nada.**

Para cada categoria macro, no `GET /tetos?mes=&ano=`:
1. Procura o teto do mês/ano exato. Se existe → `herdado: false`, origem = o próprio mês.
2. Senão, procura o mais recente **estritamente anterior**: `(ano < ? OR (ano = ? AND mes < ?)) ORDER BY ano DESC, mes DESC LIMIT 1`. Se existe → `herdado: true`, origem = mês/ano do registro encontrado.
3. Senão → `valor: null`, `herdado: false`, origem `null`.

A resposta sempre traz as 8 macro, com `origem_mes`/`origem_ano` para o frontend mostrar "herdado de setembro/2026".

### Justificativa

1. Fricção mínima: define uma vez, vale até mudar — mas o histórico por mês da ADR-006 continua possível.
2. Runtime em vez de materializar: o banco guarda só o que o usuário **decidiu**. Mudar o teto de outubro reflete automaticamente em novembro, dezembro… sem rotina de "virada de mês" nem linhas copiadas para limpar depois.
3. Só olha para trás: um teto definido para dezembro não vale para outubro. Planejar o futuro não reescreve o passado.
4. O flag `herdado` deixa explícito na UI o que foi decidido e o que é automático.
5. Funciona cruzando o ano (01/2027 herda de 10/2026).

### Trade-offs aceitos

- Até 16 queries por GET (8 macro × 2) — desprezível neste volume; mantido pela legibilidade, passo a passo.
- Alterar um teto antigo muda retroativamente os meses seguintes que herdavam dele. Para "congelar" um mês, basta defini-lo explicitamente.
- `0` e `null` são diferentes: `0` = "não gastar nada" (decidido); `null` = "sem teto".

### Reabrir se:

- O usuário quiser que meses passados fiquem congelados automaticamente (considerar materializar ao fechar o mês).
- Surgir necessidade de teto padrão anual (Opção D).

---

## ADR-014 — Tetos: PUT como upsert e DELETE que devolve à herança

**Data:** 2026-10-18
**Status:** Decidido

### Contexto

Um teto é identificado pela combinação natural `(categoria_macro_id, mes, ano)` — já protegida pelo `UNIQUE` do schema. Era preciso definir os verbos HTTP e o significado do DELETE num modelo com herança (ADR-013).

Opções consideradas para escrita:
- **A:** POST para criar + PUT para atualizar (o cliente precisa saber se já existe)
- **B:** PUT único com semântica de upsert

### Decisão

**1. `PUT /tetos` único, com upsert.**
Corpo: `{categoria_macro_id, mes, ano, valor}`. Se a combinação existe, atualiza o valor; senão, cria. Sempre 200 com o teto gravado. Implementado como **uma única instrução atômica**:
`INSERT ... ON CONFLICT (categoria_macro_id, mes, ano) DO UPDATE SET valor = excluded.valor`

**2. `DELETE /tetos?categoria_macro_id=&mes=&ano=` apaga a linha do mês exato.**
204 se apagou, 404 se não havia teto definido naquele mês. Depois do DELETE, o GET daquele mês passa a mostrar a herança do anterior (ou `null`).

**3. PUT e DELETE agem só no mês/ano exato — nunca na herança.**
Não dá para "apagar um teto herdado" (404); para mudar um mês que herda, faz-se PUT nele.

### Justificativa

1. **PUT idempotente:** "o teto de Alimentação em 10/2026 é 800" — repetir a requisição dá o mesmo resultado. Encaixa perfeitamente em um recurso com chave natural.
2. **Frontend mais simples:** a tela de tetos só faz "salvar", sem precisar saber se a linha existe.
3. **ON CONFLICT em vez de SELECT + INSERT/UPDATE:** operação atômica, sem janela de corrida entre a checagem e a escrita; reaproveita o UNIQUE do schema.
4. **DELETE = "voltar a herdar":** com herança em runtime, apagar não deixa o mês "sem teto" — devolve-o à regra automática. É a forma natural de desfazer uma exceção pontual (ex: teto maior só em dezembro).

### Trade-offs aceitos

- PUT não distingue criação de atualização na resposta (sempre 200) — irrelevante para o frontend.
- PUT no corpo e DELETE em query string (DELETE com corpo é mal suportado por clientes HTTP e proxies).
- Para "zerar" um mês sem herdar, é preciso PUT com `valor: 0`; DELETE não serve para isso.

### Reabrir se:

- O frontend precisar saber se o PUT criou ou atualizou (considerar 201 na criação).
- Surgir necessidade de operações em lote (definir os 8 tetos de uma vez).

---

## ADR-015 — Data de lançamento manual: até 90 dias no passado, nunca no futuro

**Data:** 2026-10-21
**Status:** Decidido

### Contexto

A ADR-007 definiu que lançamentos manuais usam a data real escolhida pelo usuário. Faltava definir os limites: sem nenhum, um erro de digitação (2062 em vez de 2026, ou 2016) jogaria o gasto num mês que ninguém olha, distorcendo dashboards e tetos sem que o usuário perceba.

### Decisão

- **Futuro bloqueado:** data posterior a hoje → 400.
- **Até 90 dias no passado:** `hoje − 90` é aceito; `hoje − 91` → 400 (leitura literal de "mais de 90 dias").
- O limite é a constante `DIAS_RETROATIVO_MAXIMO = 90` no topo do `main.py`, fácil de ajustar.
- Formato estrito `AAAA-MM-DD` (regex + `date.fromisoformat`): recusa `21/10/2026`, `20261021`, `2026-W43-3` e datas impossíveis como `2026-02-30`.
- No PUT, a janela só é checada **se a data mudar** (ver ADR-016): editar o valor de um lançamento antigo, reenviando a mesma data, continua funcionando.

### Justificativa

1. Futuro não faz sentido para despesa já realizada; bloquear pega erro de digitação na hora.
2. 90 dias cobrem o caso real ("esqueci de lançar aquele almoço do mês passado") com folga, sem permitir reescrever o histórico antigo.
3. Constante nomeada torna a regra explícita e trivial de mudar.

### Trade-offs aceitos

- **Fuso horário:** "hoje" é `date.today()`, o relógio do servidor. Na máquina local é o horário de Brasília. Ao hospedar o backend (Railway/Render costumam usar UTC), entre 21h e 0h a fronteira dos 90 dias pode deslocar 1 dia. A data futura não é afetada (o servidor em UTC está sempre à frente do Brasil). Usar `ZoneInfo("America/Sao_Paulo")` exigiria o pacote `tzdata` no Windows; ficou como TODO no código, ao lado da constante, para resolver no deploy.
- Despesas com mais de 90 dias não podem ser lançadas manualmente — aceitável para v1; basta ajustar a constante se virar necessidade.

### Reabrir se:

- O backend for hospedado (resolver o TODO de fuso).
- O usuário precisar lançar gastos mais antigos com frequência.

---

## ADR-016 — Edição de lançamentos importados: só subcategoria e nota

**Data:** 2026-10-21
**Status:** Decidido

### Contexto

Lançamentos importados (`origem = "fatura"`) refletem a fatura do banco, que é a fonte da verdade. Lançamentos manuais pertencem ao usuário. O `PUT /lancamentos/<id>` precisava de regras diferentes para cada origem, e de um DELETE coerente com isso.

### Decisão

**1. Três níveis de campo:**

| Campo | Manual | Importado |
|---|---|---|
| `subcategoria_id`, `nota` | editável | editável |
| `data`, `descricao`, `valor` | editável | **403** `campos_bloqueados` |
| `id`, `origem`, `parcela_atual`, `parcela_total`, `criado_em` | **400** `campos_nao_permitidos` | **400** `campos_nao_permitidos` |

O 400 vale também para o POST: `origem` é sempre forçada como `"manual"` e parcelas sempre NULL — enviar esses campos é erro do cliente, não é ignorado em silêncio.

**2. Só conta como alteração o que difere do banco.**
Antes de bloquear ou validar, cada campo enviado é normalizado (`"48.63"` → `48.63`, espaços removidos) e comparado com o valor atual. Reenviar o objeto inteiro com valores iguais não dispara 403 nem a janela de datas da ADR-015. `campos_bloqueados` lista só os campos que de fato mudariam.

Por isso a ordem das checagens no PUT é: 404 → 400 (corpo vazio / campos não permitidos) → 400 (formato) → 400 (janela de data, só manual e só se a data mudou) → 403. O formato precisa vir antes do 403 porque a comparação exige valores já normalizados.

**3. DELETE é definitivo, para qualquer origem.**
`DELETE FROM lancamentos WHERE id = ?` — sem soft delete, sem lixeira, sem endpoint de restaurar. A proteção contra exclusão acidental fica na UI (confirmação), em etapa futura.

### Justificativa

1. **Fatura como fonte da verdade:** valor, data e descrição de um importado vêm do banco; mudá-los criaria divergência com o extrato real. Categorizar e anotar são enriquecimentos do usuário, não alterações do fato.
2. **Mantém a ADR-010 correta:** a chave de deduplicação é descrição + valor + data + parcelas. Se esses campos pudessem ser editados, a reimportação da mesma fatura não reconheceria o lançamento editado e criaria uma duplicata. O bloqueio é o que garante a idempotência da importação.
3. **400 vs 403:** 400 = "esse campo não existe para edição" (erro do cliente); 403 = "o campo existe, mas não é permitido para este lançamento" (regra de negócio). Mensagens distintas facilitam o tratamento no frontend.
4. **Comparação com o atual:** frontends costumam enviar o objeto inteiro; sem isso, categorizar um importado daria 403 e editar o valor de um manual antigo daria 400.
5. **Hard delete:** simplicidade; dados de um app pessoal, sem requisito de auditoria.

### Interação com a ADR-010 (registrada conscientemente)

Como o DELETE é definitivo e a deduplicação é por contagem, **apagar um lançamento importado e reimportar a mesma fatura faz ele voltar** (n = 1 no PDF, m = 0 no banco). Comportamento considerado correto: a fatura é a fonte da verdade; o DELETE remove o registro, não "desmente" a fatura. Lançamentos importados apenas categorizados ou anotados não duplicam na reimportação (testado).

### Trade-offs aceitos

- Um importado com erro do próprio banco não pode ser corrigido no app (só anotado); a correção virá na próxima fatura.
- Exclusão acidental não tem desfazer na API.
- Para "esconder" um importado de vez, não basta apagar se a fatura for reimportada.

### Reabrir se:

- Surgir necessidade de "ignorar" importados permanentemente (considerar flag de oculto em vez de DELETE).
- Exclusões acidentais virarem problema real mesmo com confirmação na UI (considerar soft delete).

---

## ADR-017 — Categorização: PUT silencioso agora, categorização com aprendizado na Etapa 9

**Data:** 2026-10-21
**Status:** Decidido

### Contexto

Há dois jeitos de atribuir uma subcategoria a um lançamento:
- **Silencioso:** só grava `subcategoria_id` no lançamento.
- **Aprendendo:** grava e também cria/atualiza uma entrada em `aprendizados` (ADR-008), para que lançamentos futuros com a mesma descrição limpa sejam sugeridos automaticamente.

### Decisão

- **Etapa 8:** `PUT /lancamentos/<id>` com `subcategoria_id` faz a categorização **silenciosa** — nunca toca na tabela `aprendizados`.
- **Etapa 9:** um endpoint próprio, `POST /lancamentos/<id>/categorizar`, fará a categorização **com aprendizado**.

### Justificativa

1. **Responsabilidade única:** o PUT edita campos de um recurso; aprender é um efeito colateral sobre *outro* recurso (`aprendizados`). Misturar os dois num PUT genérico esconderia esse efeito.
2. **Correções sem poluir o dicionário:** recategorizar um caso pontual (ex: uma compra atípica numa loja de sempre) não deve ensinar o app errado.
3. **PUT continua previsível e idempotente;** o POST de categorizar deixa explícito, no próprio verbo e na rota, que há uma ação com consequências.
4. **Entrega incremental:** a Etapa 8 já permite categorizar manualmente; a lógica de aprendizado (normalização da ADR-008, confiança, atualização) ganha uma etapa própria.

### Trade-offs aceitos

- Duas formas de categorizar: o frontend precisa escolher qual chamar (provavelmente "categorizar" como ação padrão na tela de importação, e PUT na edição avulsa).
- Até a Etapa 9, nada é aprendido — toda categorização é manual.

### Reabrir se:

- Na prática, o usuário sempre quiser aprender ao categorizar (considerar parâmetro `aprender=true` no PUT, ou unificar).

---

## ADR-018 — Sugestão de categoria embutida no GET, com 1 query em lote

**Data:** 2026-10-21
**Status:** Decidido

### Contexto

Com a tabela `aprendizados` (ADR-008) alimentada pela categorização, o app pode sugerir a subcategoria de lançamentos ainda não categorizados. Era preciso decidir onde a sugestão aparece e como buscá-la sem degradar o desempenho.

Opções consideradas:
- **A:** Endpoint separado (`GET /lancamentos/<id>/sugestao`) — o frontend faz 1 chamada por lançamento
- **B:** Campo embutido em cada lançamento do `GET /lancamentos`, buscado em lote
- **C:** Campo embutido, mas com 1 query por lançamento (N+1)

### Decisão

**Opção B.** Todo lançamento traz a chave `subcategoria_sugerida`:
- Sem categoria + padrão aprendido → `{id, nome, categoria_macro_id, categoria_macro_nome, confianca}`
- Sem categoria + nenhum aprendizado → `null`
- Já categorizado → `null` (não precisa de sugestão)

A busca é **uma única query** para a lista inteira: os padrões dos lançamentos sem categoria são normalizados, deduplicados e consultados com `WHERE padrao_descricao IN (?, ?, …)`, já com JOIN em `subcategorias` e `categorias_macro` (os nomes vêm na mesma ida ao banco). O resultado vira um dict em memória e é distribuído para os lançamentos.

O mesmo enriquecimento é aplicado nas respostas de lançamento único (POST, PUT, categorizar), para que o lançamento tenha **o mesmo formato em qualquer endpoint**.

### Justificativa

1. **Uma requisição só** para a tela de importação/histórico: o frontend recebe a lista pronta para exibir "sugerido: Equipamento".
2. **Evita o N+1:** com 1 query por lançamento, um mês com 80 lançamentos faria 80 consultas. Medido nos testes: um GET de 27 lançamentos executa 2 queries no total, 1 em `aprendizados`.
3. **Chave sempre presente** (mesma convenção dos campos de parcela): o frontend não precisa checar existência, só `null`.

### Trade-offs aceitos

- O GET faz trabalho extra mesmo quando o frontend não exibe sugestões (custo: 1 query).
- Respostas de lançamento único fazem 1 query extra para manter o formato uniforme.
- A lista do `IN (...)` cresce com o número de padrões distintos do mês — muito abaixo do limite de variáveis do SQLite (32 766).

### Reabrir se:

- O volume de lançamentos por consulta crescer a ponto de a lista do `IN` pesar (considerar JOIN direto com uma coluna de padrão materializada em `lancamentos`).

---

## ADR-019 — Regras de aprendizado e normalização do padrão

**Data:** 2026-10-21
**Status:** Decidido

### Contexto

O endpoint `POST /lancamentos/<id>/categorizar` (ADR-017) atribui a subcategoria **e** alimenta `aprendizados`. Era preciso definir o que acontece em cada combinação de estado, e consolidar a normalização do padrão prevista na ADR-008.

### Decisão

**1. Normalização do padrão** (`normalizar_padrao`), estendendo a ADR-008:
- Remove o sufixo `" - Parcela X/Y"` (o que o parser grava, Etapa 2).
- Remove números **soltos** no final, inclusive com `.` e `,`: regex `(\s+\d[\d.,]*)+\s*$` — `"UBER 12,50"` → `"uber"`. Exigir espaço antes evita cortar `"...SUB 110,00ANTHROPIC.C"`.
- **Extensão:** junta espaços repetidos e aplica `casefold()` (com normalização Unicode NFC). Só na chave de aprendizado; a descrição do lançamento não muda.

**2. Ações ao categorizar** (`acao` na resposta, em português como o resto da API):

| Situação | `acao` | `confianca` |
|---|---|---|
| Padrão sem aprendizado | `criado` | 1 |
| Aprendizado na **mesma** subcategoria | `reforcado` | +1 |
| Aprendizado em **outra** subcategoria | `sobrescrito` | volta a 1 |
| Lançamento **já estava** nessa subcategoria e o aprendizado já aponta para ela | `inalterado` | sem mudança |
| `subcategoria_id: null` e o aprendizado aponta para a subcategoria **que o lançamento tinha** | `apagado` | null |
| `subcategoria_id: null` sem aprendizado, ou aprendizado de **outra** subcategoria | `nenhuma` | null |

**3. Implementação atômica:**
- Criar/reforçar/sobrescrever é **uma única instrução**: `INSERT … ON CONFLICT (padrao_descricao) DO UPDATE SET confianca = CASE WHEN aprendizados.subcategoria_id = excluded.subcategoria_id THEN confianca + 1 ELSE 1 END, …  RETURNING confianca`.
- Atualizar o lançamento e o aprendizado acontece **numa só transação**: nunca fica um lançamento categorizado sem o aprendizado correspondente, nem o contrário.

### Justificativa

1. **casefold e espaços:** importados vêm sempre em maiúsculas do banco, mas manuais são digitados à mão — sem isso, "Padaria", "padaria" e "Padaria  Central" seriam padrões diferentes. Cumpre o "Reabrir se" da ADR-008 (muitos aprendizados quase iguais).
2. **`reforcado` / `sobrescrito`:** a confiança mede quantas confirmações seguidas o padrão tem; uma troca de opinião do usuário zera a contagem na nova subcategoria.
3. **`inalterado`:** clique duplo, ou recategorizar para a mesma subcategoria, não traz informação nova — não deve inflar a confiança. A confiança conta **lançamentos distintos** que confirmam o padrão.
4. **`apagado` só do que o lançamento alimentou:** descategorizar um lançamento que estava em "Mercado" (por PUT silencioso) não deve apagar um aprendizado "Equipamento" com confiança 5 construído por outros lançamentos.
5. **Atomicidade:** a mesma filosofia do upsert de tetos (ADR-014) — sem janela entre ler e escrever.

### Trade-offs aceitos

- `casefold()` funde padrões que só diferem em maiúsculas — desejado. Acentos **não** são ignorados ("ACAI" ≠ "AÇAÍ"), mantendo a mesma regra das subcategorias (ADR-012).
- Um padrão tem uma única subcategoria (UNIQUE em `padrao_descricao`): lojas que vendem de tudo (ex: supermercado com roupas) vão alternar entre `sobrescrito` e confiança baixa.
- Remover números finais pode juntar lançamentos distintos de uma mesma loja (ex: filiais "LOJA X 01" e "LOJA X 02") — desejado na maioria dos casos.

### Reabrir se:

- Padrões ambíguos (lojas multi-categoria) gerarem sugestões erradas com frequência (considerar várias subcategorias por padrão, com contagem).
- Surgir necessidade de ignorar acentos também no padrão.

---

## ADR-020 — Sugestão a partir de 1 confirmação (threshold = 1 na v1)

**Data:** 2026-10-21
**Status:** Decidido

### Contexto

Com a `confianca` registrada por padrão (ADR-019), era preciso decidir a partir de quantas confirmações uma sugestão aparece.

Opções consideradas:
- **A:** Threshold fixo maior (ex: só sugere com confiança ≥ 3)
- **B:** Sugerir sempre que o padrão existir (threshold = 1) e deixar o frontend decidir a apresentação pela `confianca`
- **C:** Auto-categorizar (aplicar sem perguntar) acima de um threshold

### Decisão

**Opção B.** A sugestão aparece sempre que existe aprendizado para o padrão, com a `confianca` no payload. O backend **nunca categoriza sozinho**: a sugestão só vira categoria quando o usuário confirma (via `categorizar`, o que reforça o aprendizado).

### Justificativa

1. **Utilidade imediata:** num app pessoal, a maioria dos padrões aparece poucas vezes por mês; exigir 3 confirmações faria a sugestão demorar meses para surgir.
2. **Separação de responsabilidades:** o backend informa (`confianca`), o frontend decide a forma (ex: confiança 1 = sugestão discreta; ≥ 3 = destaque com "aceitar" em um toque).
3. **Sem risco de erro silencioso:** como nada é aplicado automaticamente, uma sugestão errada custa um toque, não um gasto mal categorizado sem o usuário perceber.
4. **Ajustável sem migração:** mudar o threshold é uma regra no frontend (ou um filtro no backend), sem tocar no banco.

### Trade-offs aceitos

- Sugestões com confiança 1 podem estar erradas (uma categorização atípica vira sugestão). Mitigado pela exibição graduada e pelo `sobrescrito`, que corrige na próxima confirmação diferente.
- Toda sugestão exige uma ação do usuário — sem auto-categorização na v1.

### Reabrir se:

- Sugestões de confiança baixa gerarem ruído na prática (subir o threshold).
- O usuário quiser auto-categorização para padrões muito confiáveis (Opção C, com limite alto e possibilidade de desfazer).

---

## ADR-021 — Dashboard agregado e categoria virtual "Sem categoria"

**Data:** 2026-10-22
**Status:** Decidido

### Contexto

A tela principal do app responde "estou no controle este mês?". Ela precisa de total gasto, orçamento, situação de cada categoria e os lançamentos recentes. Montar isso no frontend exigiria várias chamadas (lançamentos, tetos, categorias) e duplicaria regras de cálculo no cliente.

### Decisão

**Um endpoint agregado, `GET /dashboard?mes=&ano=`**, que devolve tudo calculado:

- `dias_restantes_no_mes` — mês passado: 0; mês atual: último dia − hoje (sem contar hoje); mês futuro: o mês inteiro.
- `hero` — total do mês vs orçamento (cálculo na ADR-022).
- `quantidade_sem_categoria` / `valor_sem_categoria` — atalho para o aviso "X lançamentos para categorizar".
- `categorias` — breakdown com **9 itens sempre**: as 8 macro + a categoria **virtual** "Sem categoria".
- `ultimos_lancamentos` — os 3 mais recentes, no mesmo formato do `GET /lancamentos` (JOIN + sugestão), ordenados por data, `criado_em` e id (DESC).

**Formato uniforme dos itens:** todos têm as mesmas chaves — `categoria_macro`, `categoria_virtual_nome`, `gasto`, `quantidade`, `teto`, `percentual`, `status`, `diferenca` (`teto − gasto`: positivo sobrou, negativo estourou), `convite_definir_teto`.
- Macro reais: `categoria_virtual_nome: null`; `convite_definir_teto: true` só quando não há teto (nem herdado).
- "Sem categoria": `categoria_macro: null`, `categoria_virtual_nome: "Sem categoria"`, `status: "sem_teto"`, `convite_definir_teto: false` (não é possível definir teto para ela). **Sempre presente**, mesmo com gasto 0 e quantidade 0.
- Macro sem lançamentos no mês aparecem com `gasto: 0` e `quantidade: 0`.

**"Sem categoria" é virtual:** não existe em `categorias_macro`; é montada em memória a partir da linha `NULL` do `GROUP BY`.

### Justificativa

1. **Uma requisição por tela**, com os números já consistentes entre si (o frontend não faz conta e não diverge).
2. **"Sem categoria" no breakdown:** o hero mostra o total real (tudo que saiu); sem a categoria virtual, a soma das barras não fecharia com o total, e o usuário não veria quanto ainda falta categorizar. Virtual, e não uma 9ª macro, para não violar a ADR-005 (8 macro fixas) nem aceitar teto.
3. **Formato fixo e item sempre presente:** o frontend renderiza sem `if` de existência — uniformidade vale mais que economizar um item vazio.

### Desempenho

Cerca de 20 queries por chamada (medido: 20 SELECTs): 1 agregada para gasto/quantidade por macro, 17 para tetos efetivos (reaproveitando `tetos.listar_tetos`, que calcula a herança da ADR-013 com 2 queries por macro) e 2 para os últimos lançamentos. Aceitável: é uma chamada por tela, num SQLite local, e não um N+1 por item. Reaproveitar `listar_tetos` mantém a regra de herança num único lugar.

### Trade-offs aceitos

- ~20 queries quando uma versão dedicada faria ~4.
- A lista inline dos lançamentos sem categoria (alternativa "D3") ficou de fora: o dashboard traz só contagem e valor; a lista vem de `GET /lancamentos?sem_categoria=true`.
- "Hoje" é o relógio do servidor (mesmo TODO de fuso da ADR-015).

### Reabrir se:

- O dashboard ficar lento (otimizar `listar_tetos` para uma query única com window function).
- O frontend precisar da lista de não categorizados no próprio dashboard (opção D3).

---

## ADR-022 — Status por threshold e cálculo do hero

**Data:** 2026-10-22
**Status:** Decidido

### Contexto

Cada categoria (e o hero) precisa de um status visual simples. E o hero tem uma armadilha: o total gasto inclui categorias sem teto, mas o orçamento só soma os tetos existentes — dividir um pelo outro mistura grandezas diferentes (ex: só Alimentação com teto de 800 e R$ 1.699 gastos no total daria "212% estourado", com Alimentação dentro do teto).

### Decisão

**1. Status de uma categoria** (`classificar(gasto, teto)`), com `THRESHOLD_QUASE_NO_TETO = 0.80` no topo de `dashboard.py`:

| Situação | `status` | `percentual` |
|---|---|---|
| teto `null` (nem definido nem herdado) | `sem_teto` | `null` |
| teto `0` e gasto `0` | `folgado` | `0` |
| teto `0` e gasto `> 0` | `estourado` | `null` (seria infinito) |
| gasto/teto `> 1` | `estourado` | gasto/teto × 100 |
| `0,80 ≤` gasto/teto `≤ 1` | `quase_no_teto` | idem |
| gasto/teto `< 0,80` | `folgado` | idem |

O status usa a razão **sem arredondar**; o `percentual` (2 casas) é só exibição. Assim, 100,004% é `estourado` mesmo aparecendo como `100.0`. Exatamente 100% é `quase_no_teto` (gastou tudo, mas não passou).

**2. Cálculo do hero (fluxo):**

1. `total_gasto` = soma de **todos** os lançamentos do mês (tudo que saiu, inclusive sem categoria)
2. `gasto_com_teto` = soma do gasto **só das macro com teto** (definido ou herdado; teto 0 conta)
3. `total_teto` = soma **só dos tetos existentes** (definidos ou herdados)
4. `gasto_sem_teto` = `total_gasto − gasto_com_teto` (macro sem teto + "Sem categoria")
5. **SE** `total_teto == 0`: `percentual_uso = null`, `status = "sem_teto"`
6. **SENÃO**: `percentual_uso = gasto_com_teto / total_teto × 100`, `status` pela mesma regra do item 1

Todos os valores em reais são arredondados a 2 casas; `gasto_sem_teto` é calculado no backend para o frontend não precisar derivá-lo (e divergir).

### Justificativa

1. **80%** dá tempo de reagir antes de estourar; constante nomeada para ajustar com o uso.
2. **Comparar só o comparável:** `percentual_uso` relaciona o gasto que *tem* orçamento com o orçamento — o indicador continua honesto mesmo com tetos incompletos. O total real continua visível em `total_gasto`, e o que está fora do orçamento, em `gasto_sem_teto`.
3. **Teto 0** é uma decisão válida ("não gastar nada", ADR-013): sem gasto está ok; qualquer gasto é estouro, sem percentual infinito no JSON.
4. **Razão sem arredondar** evita status incoerente com o valor real nas fronteiras.

### Trade-offs aceitos

- **O hero agrega e pode esconder um estouro:** com Alimentação em 204% e outras macro com teto sobrando, o hero mostra ~94% (`quase_no_teto`). O breakdown (ordenado pela ADR-023, estourados primeiro) é onde o estouro aparece; o frontend deve exibir os dois.
- Se todos os tetos definidos forem 0, `total_teto == 0` e o hero fica `sem_teto`, mesmo havendo decisão explícita de "não gastar" — caso raro, aceito pela simplicidade do fluxo.

### Reabrir se:

- O usuário achar 80% cedo ou tarde demais (ajustar a constante).
- O hero esconder estouros na prática (considerar status do hero = pior status entre as categorias).

---

## ADR-023 — Ordenação do breakdown por status

**Data:** 2026-10-22
**Status:** Decidido

### Contexto

O breakdown tem 9 itens. A ordem canônica (ADR-005) é estável, mas não responde "o que precisa da minha atenção agora?".

### Decisão

Ordenar por grupo de status e, dentro dele, por urgência:

1. **`estourado`** — percentual DESC (teto 0 com gasto, percentual `null`, conta como infinito e vem primeiro)
2. **`quase_no_teto`** — percentual DESC
3. **`folgado`** — percentual DESC (o menos folgado primeiro, perto dos "quase")
4. **`sem_teto`** — por `categoria_macro.id` (ordem canônica da ADR-005)
5. **"Sem categoria"** — sempre o último item

Empates de percentual são desempatados pelo id da macro (ordem determinística).

### Justificativa

1. **Atenção primeiro:** o que estourou ou está perto aparece no topo, sem o usuário procurar.
2. **Folgados em DESC** formam uma gradação contínua a partir dos "quase" — o próximo a virar problema fica logo abaixo deles.
3. **`sem_teto` no fim**, com o convite para definir teto (`convite_definir_teto`): é configuração pendente, não alerta.
4. **"Sem categoria" por último:** não é uma categoria de orçamento, é um lembrete de trabalho pendente.
5. **Ordem determinística** (desempate por id): a lista não "pula" entre recarregamentos com valores iguais.

### Trade-offs aceitos

- A posição de cada macro muda ao longo do mês conforme o gasto — o usuário não decora "Lazer é a 2ª linha". Para quem prefere posição fixa, a ordem canônica fica disponível em `GET /tetos` e `GET /categorias/macro`.

### Reabrir se:

- O usuário preferir posição fixa no dashboard (oferecer as duas ordens, com a escolha no frontend).

---

## Convenções deste arquivo

- Decisões reabertas viram ADR-NNN-v2 com link pra versão anterior.
- Status possíveis: Proposto, Decidido, Substituído por ADR-XXX, Obsoleto, Adiado.
- Toda decisão nova entra no final, com data e número incremental.

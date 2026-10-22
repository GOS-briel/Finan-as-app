# Testes legados (Etapas 5 a 10)

Scripts de teste usados durante o desenvolvimento das Etapas 5.2 a 10, preservados **sem alteração** (o da Etapa 10 já nasceu aqui). Ainda **não são pytest**: cada um é executado direto com o Python e imprime `OK`/`FALHOU` por caso, terminando com `falhas: N`.

Servem de base para a **Etapa 11** (ver marcador de retomada no README da raiz): converter para `pytest` em `backend/tests/`, um arquivo por recurso. Depois da conversão, esta pasta pode ser apagada.

## Como rodar

Sempre **a partir da raiz do projeto**, com o venv ativo. O primeiro argumento é a pasta `backend` (os scripts a colocam no `sys.path`); o segundo, quando existe, é o PDF da fatura de referência (10/10/2026), que **não está no repositório**.

```powershell
$pdf = "caminho\da\Bradesco Fatura - 10.10.2026.pdf"

python backend/tests/legado/testar_categorias.py backend
python backend/tests/legado/testar_tetos.py backend
python backend/tests/legado/testar_lancamentos.py backend $pdf
python backend/tests/legado/testar_aprendizados.py backend $pdf
python backend/tests/legado/testar_dashboard.py backend $pdf
python backend/tests/legado/testar_422_e_cafes.py backend $pdf
python backend/tests/legado/regressao_importar.py backend $pdf
python backend/tests/legado/regressao_competencia_form.py backend $pdf
```

Esses usam um **banco temporário** (trocam `inicializar.CAMINHO_BANCO`) e o `app.test_client()` do Flask: não tocam no `financas.db` real.

## O que cada script cobre

| Script | Etapa | Cobre |
|---|---|---|
| `testar_fk.py` | 5.2 | 5 tabelas criadas; `PRAGMA foreign_keys` ativo; FK inválida bloqueada |
| `testar_checks.py` | 5.2 | CHECKs de `tetos` (mês 1–12, valor ≥ 0) |
| `regressao_importar.py` | 5.3 | Importação: 23 inseridos, reimportação com 23 ignorados, `total_confere` |
| `regressao_competencia_form.py` | 5.3 / 7 | `mes`/`ano` pelo formulário (prioridade e validação) |
| `testar_422_e_cafes.py` | 5.3 | 422 quando a competência não é detectada; deduplicação por contagem (dois cafés iguais) |
| `testar_categorias.py` | 6 | CRUD de subcategorias, duplicata sem diferenciar maiúsculas, ordenação natural, DELETE bloqueado |
| `testar_tetos.py` | 7 | CRUD de tetos, herança do mês anterior, upsert |
| `testar_lancamentos.py` | 8 | CRUD de lançamentos, janela de 90 dias, proteção de importados, comparação com o valor atual |
| `testar_aprendizados.py` | 9 | Normalização do padrão, ciclo de aprendizado, sugestões em 1 query, filtro `sem_categoria` |
| `testar_dashboard.py` | 10 | Hero, status por threshold (fronteiras), ordenação do breakdown, "Sem categoria", dias restantes, últimos lançamentos, contagem de queries |

Auxiliares (usados nos testes da Etapa 5.3 feitos com o servidor rodando e `curl`):
- `resumo_resposta.py <arquivo.json>` — resume uma resposta de `/fatura/importar`
- `verificar_banco.py <caminho.db>` — confere datas, origem, soma e parcelas dos lançamentos gravados

## Atenção

- **`testar_fk.py` e `testar_checks.py` usam o banco REAL** (`backend/app/db/financas.db`) via `conectar()`. As inserções de teste são desfeitas com `rollback`, mas na conversão para pytest devem passar a usar o banco temporário. Rodar com: `python backend/tests/legado/testar_fk.py backend/app/db`.
- `testar_lancamentos.py` calcula as datas a partir de `date.today()` (fronteiras de 89/90/91 dias) e consulta outubro/2026 para os lançamentos manuais de "hoje": rodado em outro mês, os testes de GET por mês precisam ser ajustados.
- Os testes que dependem da fatura real esperam os valores dela (23 lançamentos, 6 parcelados, R$ 1.699,21, competência 10/2026).

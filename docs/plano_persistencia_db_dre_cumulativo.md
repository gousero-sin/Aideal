# Plano de Persistência DB para DRE Cumulativo (Template Apenas Visual)

Data de referência: 02/04/2026  
Versão: v1.0  
Workspace: `/Users/gousero/Abiente Dev/ScriptPyAiDeal`

## 1) Objetivo

Implementar persistência em banco para que o processo funcione assim:

1. Sempre que chegar o relatório DRE do mês `X`, o sistema salva os lançamentos no banco.
2. O DRE final da competência `X/AAAA` é montado consultando o banco de `jan..X`.
3. O template Excel passa a ser usado apenas como estrutura visual, não como fonte de dados histórica.

Resultado esperado:
- não depender de arquivo de entrada cumulativo;
- não depender de cache de tabela dinâmica para fechar números;
- permitir reprocessamento de mês com rastreabilidade.

## 2) Inventário de Arquivos (Fonte de Verdade)

### Entradas e template DRE
- Relatório bruto (exemplo):  
  `/Users/gousero/Abiente Dev/ScriptPyAiDeal/RELATORIO DRE MES 05.xls`
- Template visual DRE oficial:  
  `/Users/gousero/Abiente Dev/ScriptPyAiDeal/templates/dre/DRE AIDEAL - 05 2025  - obra.xlsx`
- Configuração atual de mapeamento DRE:  
  `/Users/gousero/Abiente Dev/ScriptPyAiDeal/backend/config/dre_mapping.json`
- Diretório de saída atual:  
  `/Users/gousero/Abiente Dev/ScriptPyAiDeal/output`

### Arquivo de fluxo de caixa (fora do escopo desta entrega, apenas referência)
- `/Users/gousero/Abiente Dev/ScriptPyAiDeal/templates/fluxo_caixa/Fluxo de Caixa A Ideal - 07 2025.xlsx`

## 3) Estrutura Relevante do Template DRE

Sheets detectadas:
- `Painel`
- `DRE`
- `BD_FLUXO`
- `PLANO_CONTAS`
- `APOIO`

Áreas críticas:
- `BD_FLUXO`: `A2:G4964` para dados de lançamento.
- `BD_FLUXO`: `H:R` deve permanecer estrutural/fórmulas.
- `DRE`: tabela visual já formatada (usar como painel final).
- `APOIO`: usado pelas fórmulas da aba `DRE` (lookup por conta pai e mês).

Tabelas detectadas:
- `DRE!DRE`
- `BD_FLUXO!BD_FLUXO1`
- `PLANO_CONTAS!PLANO_CONTAS`
- `PLANO_CONTAS!Meses`

## 4) Regra de Negócio Proposta (Nova)

Regra central:
- O arquivo enviado para `X/AAAA` é tratado como **carga mensal**.
- O cumulativo é montado pelo banco, não pelo arquivo.

Comportamento:
1. Recebe DRE do mês `X`.
2. Persiste mês `X` no banco com política de substituição por competência.
3. Para gerar o DRE de `X`, consulta banco com `ano = AAAA` e `mes <= X`.
4. Renderiza Excel final usando template visual.

## 5) Arquitetura de Persistência

## 5.1 Banco alvo (Cloudflare + Local)

Padrão recomendado:
- Cloudflare: `D1` (custo baixo/zero no MVP).
- Local/servidor próprio: `SQLite` com mesmo schema SQL.

Abstração recomendada:
- camada `repository` no backend para isolar engine SQL.
- mesmo contrato para `D1` e `SQLite`.

## 5.2 Modelo de dados (DDL base)

```sql
CREATE TABLE IF NOT EXISTS dre_uploads (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  arquivo_nome TEXT NOT NULL,
  arquivo_sha256 TEXT NOT NULL,
  competencia_ano INTEGER NOT NULL,
  competencia_mes INTEGER NOT NULL,
  status TEXT NOT NULL,
  total_linhas INTEGER NOT NULL DEFAULT 0,
  linhas_validas INTEGER NOT NULL DEFAULT 0,
  linhas_rejeitadas INTEGER NOT NULL DEFAULT 0,
  observacao TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_dre_uploads_sha256
ON dre_uploads (arquivo_sha256);

CREATE TABLE IF NOT EXISTS dre_lancamentos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  upload_id TEXT NOT NULL,
  competencia_ano INTEGER NOT NULL,
  competencia_mes INTEGER NOT NULL,
  data_lancamento TEXT NOT NULL,
  historico TEXT NOT NULL,
  valor_bruto REAL NOT NULL DEFAULT 0,
  credito REAL NOT NULL DEFAULT 0,
  debito REAL NOT NULL DEFAULT 0,
  natureza_raw TEXT,
  natureza_norm TEXT,
  centro_custo TEXT,
  rubrica TEXT,
  conta_pai TEXT,
  linha_origem INTEGER,
  hash_linha TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(upload_id) REFERENCES dre_uploads(id)
);

CREATE INDEX IF NOT EXISTS idx_dre_lancamentos_periodo
ON dre_lancamentos (competencia_ano, competencia_mes);

CREATE INDEX IF NOT EXISTS idx_dre_lancamentos_conta_mes
ON dre_lancamentos (conta_pai, competencia_ano, competencia_mes);

CREATE UNIQUE INDEX IF NOT EXISTS idx_dre_lancamentos_hash_linha_upload
ON dre_lancamentos (upload_id, hash_linha);
```

## 5.3 Política de upsert por competência

Para evitar duplicidade ao reenviar o mesmo mês:

1. Iniciar transação.
2. Remover `dre_lancamentos` do mês `X/AAAA`.
3. Inserir novos lançamentos validados do mês `X/AAAA`.
4. Marcar `dre_uploads.status = completed`.
5. Commit.

## 6) Pipeline Operacional Proposto

## 6.1 Ingestão do mês X

Entrada:
- arquivo bruto `.xls/.xlsx`
- competência `MM/AAAA`

Regras:
- validar estrutura mínima (data, histórico, valor, natureza).
- normalizar data e valores.
- aplicar regra de crédito/débito por classificação.
- validar que o lançamento pertence à competência alvo.
- linhas fora do mês alvo: rejeitar e logar.

Saída:
- dados persistidos em `dre_uploads` + `dre_lancamentos`.

## 6.2 Consulta cumulativa YTD

Query base para geração do DRE:

```sql
SELECT *
FROM dre_lancamentos
WHERE competencia_ano = :ano
  AND competencia_mes <= :mes
ORDER BY data_lancamento, id;
```

Filtros opcionais:
- `centro_custo`/obra.
- natureza.

## 6.3 Renderização do Excel final

Princípio:
- template apenas visual.

Passos:
1. Clonar template base.
2. Limpar `BD_FLUXO!A2:G4964`.
3. Escrever lançamentos cumulativos do banco em `A:G`.
4. Preencher `APOIO` com agregados por `conta_pai x mês` para alimentar `DRE`.
5. Não usar cache de pivot como fonte de verdade.
6. Salvar em `output` com nome padrão.

Observação importante:
- O objetivo é eliminar dependência de dados herdados no template.
- O dado exibido deve ser sempre reprodutível a partir do banco.

## 7) Endpoints Recomendados

### Ingestão mensal
- `POST /api/dre/ingestoes`
- payload: `arquivo`, `competencia`, `replace=true|false`

### Status de ingestão
- `GET /api/dre/ingestoes/{id}`

### Geração cumulativa
- `POST /api/dre/gerar`
- payload: `competencia`, `obra?`, `modo_teste?`

### Auditoria
- `GET /api/dre/lancamentos?ano=2025&mes=5`
- `GET /api/dre/resumo?ano=2025&mes=5`

## 8) Fases de Implementação (para outra IA)

## Fase A - Fundação DB
- criar migrations SQL;
- criar camada repository;
- implementar transações e upsert por competência;
- criar testes de unidade para insert/substituição/deduplicação.

## Fase B - Ingestão Mensal
- adaptar parser/validador para modo mensal;
- persistir upload + lançamentos;
- bloquear erro estrutural e registrar rejeições de linha.

## Fase C - Motor Cumulativo por DB
- criar consultas YTD;
- montar lote cumulativo diretamente do banco;
- desacoplar geração da necessidade de arquivo cumulativo.

## Fase D - Renderer Visual
- manter layout/template;
- escrever `BD_FLUXO` com dados cumulativos;
- preencher `APOIO` por agregação do banco;
- validar consistência com `DRE`.

## Fase E - QA e Handover
- testes E2E (ingestão mês 1, mês 2, reprocessamento mês 2);
- verificação de regressão visual;
- documentação de operação.

## 9) Testes de Aceite

1. Ingerir `01/2025` e gerar DRE `01/2025`.
2. Ingerir `02/2025` e gerar DRE `02/2025` com acumulado `jan+fev`.
3. Reenviar `02/2025` corrigido e confirmar substituição sem duplicidade.
4. Gerar `05/2025` sem arquivo cumulativo e confirmar que busca `jan..mai` do banco.
5. Confirmar que `Painel`, `DRE`, `PLANO_CONTAS`, `APOIO` mantêm estrutura visual.

## 10) Riscos e Mitigações

Risco: divergência entre `conta_pai` do banco e labels esperados no template.  
Mitigação: tabela de mapeamento canônico de contas + validação bloqueante.

Risco: duplicidade por reupload.  
Mitigação: upsert transacional por competência.

Risco: dependência de pivot cache legado.  
Mitigação: gerar valores de apoio a partir do banco e não confiar em cache.

Risco: diferença Cloudflare D1 vs SQLite local.  
Mitigação: SQL compatível, repositório único e testes em ambos ambientes.

## 11) Definições Operacionais

Padrão recomendado de execução:
- ingestão mensal sempre obrigatória antes da geração;
- geração final sempre via consulta cumulativa no banco;
- template usado exclusivamente para apresentação/formatação.

Resultado final esperado:
- DRE cumulativo consistente por ano/competência, reproduzível em qualquer ambiente (Cloudflare, local, servidor próprio) sem dependência de histórico embutido na planilha.

## 12) Evidências de Diff (baseline para próxima IA)

Arquivos de evidência recebidos:
- `/Users/gousero/Downloads/relatorio_diff_obra_vs_alternativo.md`
- `/Users/gousero/Downloads/diff_DRE_style_ids_only.csv`
- `/Users/gousero/Downloads/diff_BD_FLUXO_obra_vs_alternativo.csv`
- `/Users/gousero/Downloads/diff_APOIO_obra_vs_alternativo.csv`

Resumo objetivo das evidências:
- Estrutura global preservada (abas, nomes definidos, fórmulas, casca visual).
- Divergência massiva de conteúdo em `BD_FLUXO` (`26481` células de conteúdo).
- Divergência relevante em `APOIO` (`555` células).
- Em `DRE`, divergência apenas de `style_id` interno, com estilo renderizado equivalente.

Interpretação para implementação:
- O problema atual não é layout.
- O problema é origem de dados/cálculo (dataset não cumulativo + dependência de cache/apoio).
- A correção deve migrar a fonte de verdade para DB e gerar cumulativo `jan..competência` por consulta.

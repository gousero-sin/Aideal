# Plano — Etapa 2: módulo de Orçamento do GoFlowOS

Criado em: 2026-08-27

## Contexto e decisões de entrada

O Orçamento é a primeira aba criada depois que o controle de acesso (Etapa 1) entrou em vigor.
Duas decisões do usuário orientam o desenho e resolvem ambiguidades da especificação em
`Obsidian Vault/Projetos AIDEAL/Orc_*.md`:

1. **"Sem API e sem banco de dados" refere-se ao Obra Prima** — o mini-ERP da AIDEAL — e aos
   demais sistemas externos (GoFlow Aideal, ERP, GoFlowPrime). Não restringe o backend nem o
   banco do próprio GoFlowOS.
2. **O Orçamento terá banco próprio, vinculado ao GoFlow.** Isso supera o trecho de `Orc_Techs.md`
   sobre "não usar armazenamento persistente interno" e o RNF-09.

Permanecem válidas as regras que não dependiam de ser ferramenta avulsa: revisões imutáveis,
nenhuma exclusão no fluxo normal, memória de cálculo gravada junto da revisão, exportação de
artefato versionado e nenhuma sincronização automática com sistemas externos.

## O que está bloqueado e por quê

`Orc_Backlog.md` lista 15 decisões pendentes e condiciona o desenvolvimento dos cálculos à
aprovação de **D-01 a D-04**, todas de negócio, não técnicas:

| ID | Decisão pendente | Bloqueia |
| --- | --- | --- |
| D-01 | Margem é sobre faturamento, markup sobre custo ou outra regra? Relação com o BDI do DFP. | Preço de venda, RF-12 |
| D-02 | Unidade do saldo de mão de obra e comportamento no estouro. | RF-06 |
| D-03 | Como `HH` e `Spot` alteram composição, cálculo e saída. | RF-02, RF-13 |
| D-04 | Regra inicial da distribuição mensal. | RF-07 |
| D-05 | Estrutura de etapas e se etapa tem margem/prazo próprios. | Modelagem de itens |

Por isso o plano separa o que é estrutural (independente dessas decisões) do que é cálculo.

## Fases

### Auditoria de conclusão em 2026-08-29

A auditoria do código confirmou que **somente a Fase 1 está concluída**. Durante a
verificação, foram corrigidas quatro lacunas do núcleo documental:

- o cabeçalho da revisão atual pode ser completado ou editado enquanto ela estiver em
  `rascunho`;
- uma revisão deixa de ser editável assim que avança no ciclo de vida;
- a herança do cabeçalho ao criar nova revisão passou a ser garantida pelo backend, sem
  depender do navegador; e
- um rascunho com cabeçalho incompleto não pode avançar para `em_revisao`.

A revisão de segurança também separou leitura, edição e transição nas permissões
`orcamento.view`, `orcamento.edit` e `orcamento.transition`; tornou a troca de situação
atômica; recusou valores numéricos não finitos ou acima do limite do domínio; protegeu
revisões históricas contra alteração; validou as chaves estrangeiras após migrações; e
removeu identificadores internos de usuário das respostas públicas.

Na validação final de 2026-08-29, passaram:

- `backend/tests/test_orcamento_service.py`
- `backend/tests/test_orcamento_migrations.py`
- `backend/tests/test_access_control_api.py`
- `backend/tests/test_identity_migrations.py`
- `frontend` build de produção
- `frontend/e2e/orcamento.spec.js`
- `frontend/e2e/access-control.spec.js`

O Playwright da interface foi ajustado para rodar com `workers: 1`, porque os fluxos
compartilham o mesmo backend temporário e a execução paralela gerava contenção em
SQLite e no carregamento do painel DRE, produzindo falso negativo fora do domínio de
Orçamento.

As Fases 2 a 6 **não estão concluídas**. O desenvolvimento permanece bloqueado pelas
decisões de negócio registradas em `Orc_Backlog.md`: D-01 a D-05, D-07 a D-15. Em
especial, não deve ser adotada uma fórmula de margem, unidade de mão de obra, regra de
`HH`/`Spot`, distribuição mensal, estrutura de etapas ou formato de proposta/artefato sem
aprovação explícita. A saída auxiliar EP-07 continua posterior e depende de D-06.

### Incremento DFP e goflow-ORC em 2026-08-31

O pedido explícito de reproduzir todas as entradas da aba válida `MODELO DFP` autorizou
uma entrega de captura e cálculo em perfil de compatibilidade, sem transformar os valores
do exemplo em política comercial universal. Foram adicionados:

- snapshot DFP completo por revisão na migração aditiva V4, herdado por cópia profunda e
  editável somente na revisão atual em `rascunho`;
- catálogo dirigido por `/api/orcamento/schema`, com cabeçalho, localização estruturada,
  mão de obra direta e indireta, veículos/hospedagem, alimentação, equipamentos, EPI/EPC,
  materiais, ferramental, outros custos diretos, custos indiretos, BDI e impostos;
- cálculo canônico com `Decimal` e arredondamento `ROUND_HALF_UP`, validação estrita de
  números e gross-up tributário;
- defaults financeiros neutros: alíquotas, encargos e BDI do arquivo de exemplo não são
  copiados automaticamente para novos orçamentos;
- interface goflow-ORC em `goflow-window`, com abertura por clique/teclado, editor em
  janela própria, minimizar/maximizar/fechar, histórico somente leitura e diálogo próprio
  para mudança de situação; e
- visual Apple Liquid Glass responsivo, com alternativas para movimento e transparência
  reduzidos.

Os cinco orçamentos de teste permanecem no banco e cobrem Norte, Nordeste, Centro-Oeste,
Sudeste e Sul. O parsing de região só preenche município/UF/macrorregião quando o texto
segue o padrão reconhecido; dados ambíguos continuam vazios para revisão humana.

Este incremento não resolve D-01 a D-05 como regras universais. `HH`/`Spot`, saldo de mão
de obra, distribuição mensal, etapas e a política comercial de BDI continuam metadados ou
perfil compatível até decisão formal. `Planilha1` e `Planilha2`, que contêm `#REF!`, não
foram usadas como fonte de verdade.

### Fase 1 — Módulo de acesso e núcleo de revisões  *(concluída em 2026-08-27)*

> Revisada em 2026-08-27 após a leitura integral dos documentos do vault e do DFP
> 0055-26 (AMBEV Anápolis). Três divergências foram corrigidas: o ciclo de vida do
> orçamento tem cinco estados, não três; a validade conta da emissão e o último dia
> ainda é válido; e o cabeçalho canônico exige campos que estavam ausentes.

Independe integralmente de D-01 a D-05. Entrega a aba registrada como módulo de acesso e o ciclo
documental do orçamento, que já está decidido em `Orc_Backlog.md` ("Decisões confirmadas em
2026-08-26").

Escopo:

- banco próprio `data/orcamento.db`, com migrações versionadas, espelhando `backend/app/identity/`;
- cabeçalho canônico completo de `Orçamento.md`: contratante, dados da contratante, escopo,
  modalidade (`HH` ou `Spot`), prazo, saldo de mão de obra, região, mobilização,
  desmobilização, área/unidade-base e regime tributário;
- revisões imutáveis numeradas por orçamento, herdando o cabeçalho inteiro da anterior;
- ciclo de vida `rascunho` → `em_revisao` → `pronto_para_proposta` → `emitido` → `inativo`;
- avanço além de rascunho bloqueado enquanto faltar campo obrigatório do cabeçalho;
- inativação com motivo, data/hora e responsável, sem exclusão;
- sem reativação direta: sair de `inativo` exige nova revisão;
- validade comercial de 30 dias corridos contada da **emissão**, com o último dia ainda
  válido e o vencimento passando a valer no dia seguinte;
- vínculo com o GoFlow pela identidade (`autor_user_id` de `identity.db`);
- registro completo do módulo de acesso conforme o checklist de `CLAUDE.md`;
- painel React de listagem, criação, nova revisão e mudança de situação.

Fora do escopo da Fase 1: itens de custo, tabela salarial, impostos, margem, preço, distribuição
mensal, proposta técnica, importação e exportação de artefato.

### Fase 2 — Composição de custos  *(depende de D-05)*

Etapas do orçamento e itens de custo direto nos blocos válidos do `MODELO DFP`: mão de obra
direta e indireta, veículos e hospedagem, alimentação, equipamentos, EPI, materiais de consumo,
ferramental e outros. Cálculo de linha por quantidade × custo unitário, subtotais e percentual de
participação por bloco. Tabela salarial da sessão com fonte, vigência e revisão.

### Fase 3 — Precificação  *(depende de D-01, D-02, D-03)*

Custos indiretos por alíquota, margem/BDI conforme a regra aprovada, impostos por tipo e alíquota,
preço de custo, preço de faturamento e métricas derivadas. Toda regra identificada por versão e
gravada na revisão.

### Fase 4 — Distribuição mensal  *(depende de D-04)*

Toggle, alocação por mês dentro do prazo de execução e reconciliação com o total.

### Fase 5 — Proposta técnica vinculada  *(depende de D-07, D-09, D-13 a D-15)*

Área separada habilitada apenas para revisão `pronto_para_proposta`, cinco tópicos obrigatórios,
documento gerado, validade de 30 dias e vínculo imutável com a revisão de origem.

### Fase 6 — Artefatos e homologação  *(depende de D-09, D-11, D-12)*

Exportação e importação do pacote versionado, memória de cálculo legível e comparação com cenários
autorizados do DFP.

## Modelo de dados da Fase 1

```
orcamentos                      1 ─── N  orcamento_revisoes
  id, codigo (único),                      id, orcamento_id, numero,
  contratante,                             situacao, escopo, modalidade,
  criado_por_user_id,                      regiao, prazo_execucao_dias,
  created_at, updated_at                   saldo_mao_de_obra, versao_regras,
                                           autor_user_id, motivo,
                                           valido_ate, created_at
                                             │
                                             │ 1 ─── N
                                             ▼
                                    orcamento_situacao_eventos
                                      id, revisao_id, situacao,
                                      motivo, responsavel_user_id,
                                      created_at
```

`orcamento_situacao_eventos` é a trilha append-only que substitui a exclusão: toda transição de
situação vira um evento com motivo e responsável, e a revisão nunca é apagada.

## Contrato HTTP da Fase 1

Todas as rotas exigem `orcamento.view`; as de escrita também exigem CSRF e uma permissão
específica de edição ou transição.

| Método | Rota | Dependência |
| --- | --- | --- |
| GET | `/api/orcamento/orcamentos` | `require_permission("orcamento.view")` |
| POST | `/api/orcamento/orcamentos` | `orcamento.view` + `orcamento.edit` + CSRF |
| GET | `/api/orcamento/orcamentos/{id}` | `require_permission("orcamento.view")` |
| POST | `/api/orcamento/orcamentos/{id}/revisoes` | `orcamento.view` + `orcamento.edit` + CSRF |
| PATCH | `/api/orcamento/revisoes/{id}` | `orcamento.view` + `orcamento.edit` + CSRF |
| POST | `/api/orcamento/revisoes/{id}/situacao` | `orcamento.view` + `orcamento.transition` + CSRF |

## Checklist de módulo de acesso — Fase 1

| # | Ponto | Situação |
| --- | --- | --- |
| 1 | `INSERT` das permissões em migrações de identidade | feito em `V1` e `V3` |
| 2 | `DEFAULT_PERMISSIONS` em `identity/service.py` | já existe |
| 3 | `MODULE_CATALOG` em `access_control.py` | feito |
| 4 | Rotas protegidas | feito |
| 5 | `accessControlModel.js` (`MODULE_CATALOG` + `PERMISSION_OPTIONS`) | já existe |
| 6 | `App.jsx` (`VIEW_META` + branch) | feito |
| 7 | `test_access_control_api.py` (403 sem permissão, 200 com) | feito |
| 8 | `frontend/e2e/access-control.spec.js` | feito |

## Arquivos da Fase 1

| Camada | Arquivos |
| --- | --- |
| Domínio | `backend/app/orcamento/` — `database.py`, `models.py`, `repository.py`, `service.py`, `exceptions.py` e migrações versionadas |
| HTTP | `backend/app/main.py` (6 rotas + readiness), `backend/app/access_control.py` (`MODULE_CATALOG`, permissões e `get_orcamento_service`) |
| Config | `backend/app/config.py` (`orcamento_db_path`), `.gitignore` |
| Frontend | `frontend/src/components/OrcamentoPanel.jsx`, `orcamentoModel.js`, `frontend/src/App.jsx` |
| Testes | `backend/tests/test_orcamento_service.py`, `test_orcamento_migrations.py`, `test_access_control_api.py`, testes dos modelos frontend e E2E dedicados |

## Riscos

- Adicionar `orcamento` ao `MODULE_CATALOG` do backend quebra a asserção de conjunto de módulos em
  `test_access_control_api.py`; atualizar junto.
- Congelar cedo o esquema de custos antes de D-01 a D-05 geraria migração descartável; por isso a
  Fase 1 não cria tabelas de item de custo.
- `codigo` do orçamento é **gerado pelo sistema** a partir de um sequencial contínuo
  (`ORC-0001`, `ORC-0002`, ...), decidido pelo usuário em 2026-08-27. O sequencial vive em coluna
  própria com índice único; `MAX+1` roda dentro de `BEGIN IMMEDIATE`, então não há colisão.
  O prefixo e o número de dígitos ficam em `CODIGO_PREFIXO`/`CODIGO_DIGITOS`; o formato exato não
  estava nos documentos que consegui ler e precisa de confirmação contra o DFP.

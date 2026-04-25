# Handoff Completo — DRE (AIDEAL GoFlowOS)

## 1) Objetivo deste handoff
Este documento é a instrução operacional completa para o Claude continuar o desenvolvimento **somente da parte DRE**, a partir do estado atual do projeto em **2026-04-17**.

Use este handoff como fonte principal para:
- manter o fluxo DRE estável sem quebrar template/slicers;
- evoluir regras de geração por meses sem exigir histórico completo;
- evitar regressões de arquivo “corrompido/reparado” no Excel.

## 2) Escopo e limites
Escopo permitido:
- Ingestão DRE;
- Geração DRE a partir do banco;
- Escrita/preservação do template DRE (`.xlsx`);
- UI de DRE no frontend;
- Testes do domínio DRE.

Fora de escopo neste handoff:
- Fluxo de Caixa;
- Refactors gerais sem impacto direto no DRE;
- Mudanças cosméticas sem relação com a estabilidade funcional DRE.

## 3) Estado atual (resumo executivo)
Hoje o DRE está com as seguintes garantias já implementadas:
- **Não é obrigatório ter meses anteriores completos** para gerar DRE.
- A geração aceita gaps (ex.: meses `01, 02, 06`) e usa os meses realmente disponíveis.
- Slicers/slicers-like (“sliders” na linguagem do usuário) foram protegidos no pipeline de escrita.
- Erro de arquivo corrompido foi tratado em dois pontos centrais:
  - remoção consistente de `pivotCacheRecords` (payload + referências);
  - preservação de metadados de compatibilidade da worksheet (ex.: `mc:Ignorable`, namespaces `x14`, etc.).
- Competência inválida com mês fora de `01..12` (ex.: `00/2025`) agora é rejeitada explicitamente.

## 4) Problema real encontrado em produção/local
Arquivo reportado com erro ao abrir:
- `/Users/gousero/Downloads/DRE_AIDEAL_00-2025_20260417_104404.xlsx`

Diagnóstico técnico:
- O pacote ZIP estava íntegro (`testzip` ok), mas a worksheet principal da aba DRE (`xl/worksheets/sheet2.xml`) foi serializada sem metadados de compatibilidade importantes.
- Quando o Excel abre, isso pode acionar “reparo” e efeitos colaterais em slicers/pivot.
- Além disso, competência `00/2025` era aceita indevidamente, o que gerava saídas inválidas do ponto de vista de negócio.

## 5) Mudanças já aplicadas

### 5.1 TemplateWriter (preservação OOXML)
Arquivo:
- `/Users/gousero/Abiente Dev/ScriptPyAiDeal/backend/app/templates/writer.py`

Mudanças principais:
- Adicionados namespaces explícitos de compatibilidade:
  - `NS_MC`, `NS_X14`, `NS_X14AC`, `NS_XR`, `NS_XR2`, `NS_XR3`.
- Novo método para registro estável de namespaces antes de serializar XML:
  - `_registrar_namespaces_xml()`.
- Na mesclagem de sheet (`_mesclar_sheet_com_template`), os atributos da raiz da sheet do template são preservados no XML final quando ausentes no editado:
  - ex.: `mc:Ignorable`, `xr:uid` e demais atributos da raiz.
- Remoção de referências órfãs de pivot cache records em `[Content_Types].xml`:
  - `_remover_content_type_pivot_cache_records()`.
- Continuidade da remoção de relacionamento `pivotCacheRecords` em `pivotCacheDefinition*.rels`:
  - `_remover_rel_pivot_cache_records()`.
- `salvar()` já garante criação de `settings.temp_dir` antes do `NamedTemporaryFile`.

### 5.2 Validação rígida de competência (mês válido)
Arquivos:
- `/Users/gousero/Abiente Dev/ScriptPyAiDeal/backend/app/processamento/dre_geracao_completa.py`
- `/Users/gousero/Abiente Dev/ScriptPyAiDeal/backend/app/ingestao/dre_ingestao.py`
- `/Users/gousero/Abiente Dev/ScriptPyAiDeal/backend/app/processamento/dre_geracao.py`

Mudança:
- `parse_competencia` agora rejeita mês `<1` ou `>12` com erro claro:
  - `Mês da competência inválido: XX. Use valores entre 01 e 12.`

## 6) Arquitetura DRE relevante (mapa rápido)

Backend (núcleo):
- API DRE: `/Users/gousero/Abiente Dev/ScriptPyAiDeal/backend/app/main.py`
- Ingestão DRE: `/Users/gousero/Abiente Dev/ScriptPyAiDeal/backend/app/ingestao/dre_ingestao.py`
- Geração completa DRE (DB + template): `/Users/gousero/Abiente Dev/ScriptPyAiDeal/backend/app/processamento/dre_geracao_completa.py`
- Geração legada DRE: `/Users/gousero/Abiente Dev/ScriptPyAiDeal/backend/app/processamento/dre_geracao.py`
- Repositório/persistência: `/Users/gousero/Abiente Dev/ScriptPyAiDeal/backend/app/repository/dre_repository.py`
- Escrita de template OOXML: `/Users/gousero/Abiente Dev/ScriptPyAiDeal/backend/app/templates/writer.py`

Frontend (DRE):
- Painel principal: `/Users/gousero/Abiente Dev/ScriptPyAiDeal/frontend/src/App.jsx`
- Upload/ingestão/geração DRE: `/Users/gousero/Abiente Dev/ScriptPyAiDeal/frontend/src/components/UploadPanel.jsx`
- Status/retorno de geração: `/Users/gousero/Abiente Dev/ScriptPyAiDeal/frontend/src/components/StatusPanel.jsx`

Template oficial DRE:
- `/Users/gousero/Abiente Dev/ScriptPyAiDeal/templates/dre/DRE AIDEAL - 05 2025  - obra.xlsx`

## 7) Regras de negócio DRE que DEVEM permanecer
- Regra 1: geração **não exige cumulativo completo** mês a mês.
- Regra 2: modo padrão da geração usa meses disponíveis `<= competência`.
- Regra 3: `ano_todo=true` usa todos os meses disponíveis do ano.
- Regra 4: `meses_incluir` usa apenas meses explicitamente escolhidos, desde que existam com upload `completed`.
- Regra 5: competência deve respeitar mês `01..12`.
- Regra 6: preservar slicers e pivots do template (não destruir estrutura visual).

## 8) Endpoints DRE (contrato funcional)
- `POST /api/dre/ingestoes`
  - Persiste dados do mês no banco.
- `POST /api/dre/gerar`
  - Gera arquivo DRE via banco + template.
  - Aceita `competencia`, `meses_incluir`, `ano_todo`, `centro_custo`, `modo_teste`.
- `POST /api/dre/admin/limpar`
  - Limpa base DRE (global/ano/mês).
- `GET /api/dre/ingestoes`
  - Lista ingestos, usado pelo frontend para descobrir meses disponíveis.
- `GET /api/dre/download/{arquivo_nome}`
  - Download da planilha gerada.

## 9) Fluxo recomendado de operação
1. Validar estrutura do arquivo DRE bruto.
2. Ingerir mês via `/api/dre/ingestoes`.
3. Carregar meses disponíveis no ano da competência.
4. Gerar via `/api/dre/gerar` no modo padrão ou com seleção explícita.
5. Abrir `.xlsx` e verificar ausência de prompt de reparo no Excel.

## 10) Testes relevantes e status
Arquivos de teste prioritários:
- `/Users/gousero/Abiente Dev/ScriptPyAiDeal/backend/tests/test_template_writer.py`
- `/Users/gousero/Abiente Dev/ScriptPyAiDeal/backend/tests/test_dre_geracao_completa_service.py`
- `/Users/gousero/Abiente Dev/ScriptPyAiDeal/backend/tests/test_dre_geracao_api.py`

Comando de regressão principal:
```bash
cd "/Users/gousero/Abiente Dev/ScriptPyAiDeal/backend"
PYTHONPATH=. pytest -q tests/test_dre_geracao_completa_service.py tests/test_dre_geracao_api.py tests/test_template_writer.py
```

Status atual de referência:
- `17 passed`.

Warnings esperados:
- `openpyxl`: “Slicer List extension is not supported and will be removed” durante leitura.
- `fastapi`: depreciação de `on_event` (não bloqueante para este escopo).

## 11) Checklist de não regressão (obrigatório)
Antes de concluir qualquer tarefa DRE, confirmar:
- Geração com apenas 1 mês disponível (ex.: somente mês 06) funciona.
- Geração com gaps (ex.: 01, 02, 06) funciona.
- Competência inválida (`00/2025`) é rejeitada com 400/mensagem clara.
- Saída `.xlsx` não contém referência órfã a `pivotCacheRecords` em `[Content_Types].xml`.
- `sheet2.xml` final mantém `mc:Ignorable` e namespaces necessários (`mc`, `x14`) além de `extLst/slicerList`.
- Abertura no Excel sem prompt de reparo.

## 12) Prioridades para próximas iterações (DRE)
Prioridade Alta:
- Adicionar teste de API explícito para `competencia=00/2025` em `/api/dre/gerar`.
- Adicionar validação preventiva no frontend para impedir submissão de competência fora do range (defesa em profundidade).

Prioridade Média:
- Consolidar parse/validação de competência em util único reutilizável (evitar duplicação entre serviços).
- Criar teste de integração que inspecione XML de saída para namespaces mínimos da sheet DRE.

Prioridade Baixa:
- Melhorar observabilidade do pipeline de geração (logs estruturados por etapa: BD_FLUXO, APOIO, visibilidade DRE, merge OOXML).
- Endurecer validação de compatibilidade do pacote OOXML em util de auditoria.

## 13) Riscos técnicos que exigem cuidado
- Qualquer alteração no `TemplateWriter` pode quebrar slicers/pivots silenciosamente.
- Reescrita agressiva de XML com parser pode mudar prefixes/namespaces e acionar reparo no Excel.
- Mudanças em estratégia de remoção de pivot cache exigem coerência entre:
  - payload removido,
  - `.rels` atualizados,
  - `[Content_Types].xml` sem referências órfãs.

## 14) Regra operacional para editar `TemplateWriter`
- Não recriar workbook/sheets do zero.
- Não remover `extLst` da aba DRE.
- Preservar atributos de raiz da worksheet do template quando não existirem no XML editado.
- Manter serialização com namespaces registrados.
- Sempre rodar testes de writer + geração completa após qualquer ajuste.

## 15) Instrução direta para o Claude (prompt operacional)
Use o texto abaixo como instrução interna de execução:

```md
Continuar o desenvolvimento APENAS do domínio DRE no projeto AIDEAL GoFlowOS.

Objetivo:
- manter geração DRE sem exigir meses anteriores completos;
- preservar template e slicers sem corromper arquivo Excel;
- impedir competência inválida (mês fora de 01..12).

Regras mandatórias:
- Não tocar em Fluxo de Caixa.
- Não fazer refactor amplo sem impacto direto no DRE.
- Em qualquer mudança de TemplateWriter, validar XML final de sheet2 + Content_Types + pivots.
- Garantir que testes DRE principais passem.

Arquivos foco:
- backend/app/processamento/dre_geracao_completa.py
- backend/app/ingestao/dre_ingestao.py
- backend/app/processamento/dre_geracao.py
- backend/app/templates/writer.py
- backend/tests/test_template_writer.py
- backend/tests/test_dre_geracao_completa_service.py
- backend/tests/test_dre_geracao_api.py
- frontend/src/components/UploadPanel.jsx

Critério de pronto:
- geração com gaps funciona;
- 00/2025 rejeitado;
- arquivo abre no Excel sem reparo;
- suíte de testes DRE passa.
```

## 16) Evidência de geração válida após correção
Arquivo gerado após ajustes:
- `/Users/gousero/Abiente Dev/ScriptPyAiDeal/output/DRE_AIDEAL_06-2025_20260417_105307.xlsx`

Sinais verificados nesse arquivo:
- `sheet2.xml` com `mc:Ignorable`, `xmlns:mc`, `xmlns:x14`;
- `slicerList` presente;
- ausência de `pivotCacheRecords` em `[Content_Types].xml`;
- sem referência órfã de `pivotCacheRecords` em rels de pivot cache.

---
Fim do handoff DRE.

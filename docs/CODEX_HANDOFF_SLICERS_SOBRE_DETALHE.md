# Handoff para Codex — Operação Sem Slicers (`DETALHE_MENSAL_DB` + GoFlowOS)

**Atualizado em:** 21/04/2026  
**Projeto:** `ScriptPyAiDeal`  
**Endpoint principal:** `POST /api/dre/gerar`  
**Serviço:** `backend/app/processamento/dre_geracao_completa.py`  
**Writer OOXML:** `backend/app/templates/writer.py`

---

## 1. Decisão Oficial (21/04/2026)

Foi aprovada a **remoção completa dos slicers** do arquivo final gerado pelo DRE.

A estratégia do produto passa a ser:
1. Manter a aba secundária `DETALHE_MENSAL_DB` como base de dados operacional.
2. Manter o painel DRE estável, sem dependência de slicer OOXML.
3. Fazer a separação por obra/centro de custo/etc **diretamente no GoFlowOS** (camada de aplicação), usando os dados detalhados.

---

## 2. Objetivo Atual

Garantir que o pipeline de geração:
1. **Não injete slicers** novos.
2. **Não preserve slicers legados** do template.
3. Continue gerando `DETALHE_MENSAL_DB` com table OOXML válida.
4. Continue abrindo no Excel Desktop sem prompt de reparo.
5. Entregue dados completos para o GoFlowOS aplicar filtros por obra e demais dimensões.

---

## 3. Arquitetura Alvo (Sem Slicers)

### 3.1 O que deve existir no `.xlsx` final
- `xl/tables/table5.xml` para `DETALHE_MENSAL_DB`.
- `xl/worksheets/sheet6.xml` com `<tableParts>` apontando para `table5`.
- `xl/worksheets/_rels/sheet6.xml.rels` com target relativo `../tables/table5.xml`.
- `BD_FLUXO1` ajustada ao volume real e sem `calculatedColumnFormula` inconsistente.

### 3.2 O que NÃO deve existir
- `xl/slicers/*`
- `xl/slicerCaches/*`
- `x14:slicerList` em worksheets
- `x14/x15:slicerCaches` no `workbook.xml`
- relacionamentos `.../relationships/slicer` e `.../relationships/slicerCache`

---

## 4. Plano de Implementação (Atualizado)

### 4.1 Etapa A — Remover dependência de slicer no serviço
- Remover chamadas `writer.registrar_slicer(...)` do fluxo `gerar_arquivo`.
- Manter `writer.remover_slicers()` ativo para limpar qualquer artefato legado do template.

### 4.2 Etapa B — Preservar detalhamento para GoFlowOS
- Continuar criando/atualizando `DETALHE_MENSAL_DB`.
- Continuar promovendo a área granular para table OOXML via `registrar_table_ooxml(...)`.
- Garantir metadados e colunas necessárias para filtro por obra/centro no frontend.

### 4.3 Etapa C — Ajustar testes para política sem slicers
- Atualizar testes de integração para validar ausência de partes e relacionamentos de slicer.
- Manter validações de integridade da table `DETALHE_MENSAL_DB`.
- Manter validações de abertura/estrutura (recalc, pivot removido, content-types).

### 4.4 Etapa D — Entrega no GoFlowOS
- Consumir a aba/tabela de detalhamento para filtros por obra, centro de custo, conta pai, rubrica etc.
- Tratar filtro na aplicação (API/UI), não no OOXML do Excel.

### 4.5 Etapa E — Validação final
- `pytest` dos testes relevantes.
- Smoke de geração real (`/api/dre/gerar`) com inspeção estrutural do zip.
- Verificação no Excel Desktop (sem prompt de reparo).

### 4.6 Status das Etapas (21/04/2026)
1. Etapa A: **CONCLUIDA** no backend.
2. Etapa B: **CONCLUIDA** no backend (detalhamento em `DETALHE_MENSAL_DB` mantido).
3. Etapa C: **CONCLUIDA** (testes atualizados para politica sem slicers).
4. Etapa D: **PENDENTE/EM EXECUCAO** no GoFlowOS (filtros por obra/centro na camada de aplicacao).
5. Etapa E: **PARCIAL** (testes automatizados ok; validacao manual final no Excel Desktop e no fluxo GoFlowOS deve ser concluida).

---

## 5. Arquivos de Referência

- `backend/app/processamento/dre_geracao_completa.py`  
  Fluxo principal de geração e registro da aba `DETALHE_MENSAL_DB`.

- `backend/app/templates/writer.py`  
  Limpeza de slicers legados, materialização de table OOXML, normalização de relações.

- `backend/tests/test_dre_geracao_completa_service.py`  
  Deve validar geração final **sem slicers** e com `DETALHE_MENSAL_DB` íntegra.

- `backend/tests/test_template_writer.py`  
  Continua cobrindo mecanismos OOXML de remoção de slicer e materialização de table.

---

## 6. Checklist de Aceite (Atualizado)

- [x] Arquivo final não contém `xl/slicers/` nem `xl/slicerCaches/`.
- [x] `sheet2.xml` (DRE) não contém `slicerList`.
- [x] `workbook.xml` não contém `slicerCaches`.
- [x] `DETALHE_MENSAL_DB` permanece como table OOXML (`table5.xml` + `tableParts` + rel válida).
- [x] Relação da table em `sheet6.xml.rels` usa target relativo `../tables/table5.xml`.
- [ ] Excel Desktop abre sem reparo.
- [ ] GoFlowOS consegue filtrar por obra/centro com base no detalhamento.
- [x] Testes relevantes passam.

---

## 7. Armadilhas a Evitar

1. Reintroduzir `registrar_slicer(...)` no fluxo principal.
2. Confiar em slicers para lógica de negócio de filtro (filtro deve ficar no GoFlowOS).
3. Voltar a carregar artefatos legados de pivot/slicer do template original.
4. Quebrar a table `DETALHE_MENSAL_DB` (isso impacta diretamente os filtros no app).

---

## 8. TL;DR para a Próxima Iteração

1. **Sem slicers no XLSX final.**  
2. **`DETALHE_MENSAL_DB` é a fonte de filtro operacional.**  
3. **Separação por obra/etc acontece no GoFlowOS, não no Excel OOXML.**

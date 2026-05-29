# Brief Técnico para Claude Opus — Corrigir XLSX DRE que Excel Desktop não abre

## Objetivo
Corrigir **definitivamente** a geração do arquivo DRE para que o Excel Desktop abra sem erro/reparo.

Hoje o backend gera arquivo com sucesso pela API, mas o usuário reporta que o Excel ainda acusa problema ao abrir.

---

## Contexto do Projeto
- Projeto: `ScriptPyAiDeal`
- Stack principal: `FastAPI + openpyxl + patch OOXML manual`
- Fluxo afetado: `POST /api/dre/gerar`
- Template base:
  - `/Users/gousero/Abiente Dev/ScriptPyAiDeal/templates/dre/DRE AIDEAL - 05 2025  - obra.xlsx`
- Arquivo bruto de ingestão (caso de teste principal):
  - `/Users/gousero/Abiente Dev/ScriptPyAiDeal/exemplos/base_dados_planilhas/dre/MES 06 - DRE /Relatorio DRE MES 06-2025.xls`

---

## Estado Atual (já implementado)
### Backend
- Remoção de slicers no pipeline final.
- Geração de aba nova `DETALHE_MENSAL_DB` com:
  - resumo mensal
  - agregado por centro/conta/rubrica
  - granular de lançamentos
- Normalização de `workbook.xml.rels` para targets relativos.
- Ajustes de `sharedStrings` relationship e `[Content_Types]`.

### Arquivos principais alterados
- `/Users/gousero/Abiente Dev/ScriptPyAiDeal/backend/app/templates/writer.py`
- `/Users/gousero/Abiente Dev/ScriptPyAiDeal/backend/app/processamento/dre_geracao_completa.py`
- `/Users/gousero/Abiente Dev/ScriptPyAiDeal/backend/app/main.py`
- `/Users/gousero/Abiente Dev/ScriptPyAiDeal/backend/app/processamento/dre_from_xls.py`

### Testes locais
- `PYTHONPATH=backend pytest -q backend/tests/test_template_writer.py backend/tests/test_dre_geracao_completa_service.py backend/tests/test_dre_geracao_api.py`
- Resultado atual: **passando**.

---

## Problema
Mesmo com testes passando, o usuário final relata:
- “ainda com problemas”
- Excel Desktop não abre corretamente (ou tenta reparar e falha).

Ou seja: temos um gap entre validação técnica local e compatibilidade real no Excel do usuário.

---

## Como reproduzir do zero (pipeline limpo)
1. Limpar base:
```bash
curl -sS -X POST 'http://127.0.0.1:8000/api/dre/admin/limpar' -F 'confirmar=true'
```

2. Reingestir bruto:
```bash
curl -sS -X POST 'http://127.0.0.1:8000/api/dre/ingestoes' \
  -F "arquivo=@/Users/gousero/Abiente Dev/ScriptPyAiDeal/exemplos/base_dados_planilhas/dre/MES 06 - DRE /Relatorio DRE MES 06-2025.xls" \
  -F 'competencia=06/2025' -F 'replace=true'
```

3. Gerar DRE:
```bash
curl -sS -X POST 'http://127.0.0.1:8000/api/dre/gerar' \
  -F 'competencia=06/2025' -F 'ano_todo=false'
```

4. Último arquivo gerado (exemplo recente):
- `/Users/gousero/Abiente Dev/ScriptPyAiDeal/output/DRE_AIDEAL_06-2025_20260420_114001.xlsx`

---

## Pedido para Opus (escopo objetivo)
Você deve:
1. Encontrar a causa raiz de incompatibilidade com Excel Desktop.
2. Implementar correção robusta no backend.
3. Garantir que a geração:
   - mantenha DRE funcional,
   - mantenha aba `DETALHE_MENSAL_DB`,
   - não dependa de slicers,
   - abra no Excel sem reparo.

### Importante
- Não fazer apenas “mais heurística regex”.
- Se necessário, simplificar arquitetura de saída para um modo **Excel-safe**:
  - preservar o mínimo de OOXML legado complexo,
  - remover artefatos avançados potencialmente corrompíveis (extLst/problemáticos),
  - priorizar compatibilidade de abertura em Excel Desktop.

---

## Estratégia recomendada (se precisar pivotar)
Se continuar instável:
1. Implementar um modo de saída “safe workbook”:
   - abrir template base,
   - copiar somente abas essenciais e conteúdo final,
   - evitar transportar partes OOXML antigas de slicer/pivot/extensões que causam corrupção.
2. Garantir consistência entre:
   - workbook.xml
   - workbook.xml.rels
   - [Content_Types].xml
   - drawings / worksheet rels / calcChain / sharedStrings / definedNames.
3. Validar que não há referências órfãs em qualquer `.rels`.

---

## Critério de aceite
1. Arquivo gerado via `/api/dre/gerar` abre no Excel Desktop sem prompt de reparo.
2. Aba `DETALHE_MENSAL_DB` existe e está preenchida.
3. Testes backend relevantes passam.
4. Entregar no final:
   - lista dos arquivos alterados,
   - causa raiz identificada,
   - evidência de validação.

---

## Onde investigar primeiro
- `/Users/gousero/Abiente Dev/ScriptPyAiDeal/backend/app/templates/writer.py`
- `/Users/gousero/Abiente Dev/ScriptPyAiDeal/backend/app/processamento/dre_geracao_completa.py`
- `/Users/gousero/Abiente Dev/ScriptPyAiDeal/backend/tests/test_template_writer.py`
- `/Users/gousero/Abiente Dev/ScriptPyAiDeal/backend/tests/test_dre_geracao_completa_service.py`

---

## Observações finais para execução
- Tratar como bug crítico de produção.
- Não encerrar com “parece correto”; precisa evidência concreta de abertura no Excel real.
- Se necessário, adicionar teste de regressão estrutural novo para evitar retorno do bug.

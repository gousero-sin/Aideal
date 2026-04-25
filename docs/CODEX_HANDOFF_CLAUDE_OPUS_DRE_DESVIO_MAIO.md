# Handoff para Claude Opus - Desvio de Valores no DRE (Maio/2025)

## 1) Contexto rapido

Projeto: `ScriptPyAiDeal`  
Objetivo: entender por que o DRE gerado para `05/2025` diverge do arquivo de referencia.

Arquivos principais analisados:
- Gerado: `/Users/gousero/Downloads/DRE_AIDEAL_05-2025_20260421_151514.xlsx`
- Referencia: `/Users/gousero/Abiente Dev/ScriptPyAiDeal/DRE AIDEAL - 05 2025  - obra.xlsx`
- Fonte de entrada: `/Users/gousero/Documents/AIDEAL/MES 05 - DRE /RELATORIO DRE MES 05.xls`

## 2) O que ja foi confirmado (fatos)

1. **Nao ha influencia de meses passados no arquivo gerado 05/2025**.
   - Em `BD_FLUXO`, somente `(ano=2025, mes=5)`.
   - Em `DETALHE_MENSAL_DB`, somente resumo de Maio.
   - Em `APOIO`, nao ha valores nao-zero fora de Maio.

2. **O desvio principal nao e slicer**.
   - Slicers foram removidos por decisao de produto.
   - A logica de filtro operacional esta no GoFlowOS.

3. **Existe diferenca real na base de dados usada para gerar o DRE**.
   - Gerado (BD_FLUXO maio): `923` linhas, credito `1.178.879,22`, debito `2.064.559,17`.
   - Referencia (BD_FLUXO maio): `1067` linhas, credito `1.789.092,17`, debito `2.452.700,34`.

4. **No arquivo de entrada bruto (`RELATORIO DRE MES 05.xls`) existe 1 linha de junho na aba Sheet**.
   - Essa linha e filtrada pela competencia em ingestao (nao entra no DRE de maio).

## 3) Mudancas ja aplicadas no codigo

### 3.1 Ajuste da aba APOIO (estabilidade de lookup do DRE)

Arquivo:
- [/Users/gousero/Abiente Dev/ScriptPyAiDeal/backend/app/processamento/dre_geracao_completa.py](/Users/gousero/Abiente%20Dev/ScriptPyAiDeal/backend/app/processamento/dre_geracao_completa.py)

Mudanca:
- Estrutura fixa `Jan..Dez + Total Geral` na APOIO.
- Limpeza da faixa inteira usada pelo lookup.

Linhas:
- header/meses fixos: `251-259`, `277-284`

Objetivo:
- Evitar resquicio de colunas antigas do template contaminando `MATCH/VLOOKUP`.

### 3.2 Expansao de impostos na ingestao (IR/ISS/INSS/PIS/COFINS/CSLL/Tarifa)

Arquivo:
- [/Users/gousero/Abiente Dev/ScriptPyAiDeal/backend/app/transformacao/engine.py](/Users/gousero/Abiente%20Dev/ScriptPyAiDeal/backend/app/transformacao/engine.py)

Mudanca:
- Adicionado `_IMPOSTOS_ENTRADA`.
- Para cada linha base valida, cria lancamentos de debito para impostos > 0.

Linhas:
- definicao impostos: `15-23`
- expansao no loop principal: `117-131`
- funcao nova `_converter_impostos_linha`: `148-188`

Teste novo:
- [/Users/gousero/Abiente Dev/ScriptPyAiDeal/backend/tests/test_transformer.py](/Users/gousero/Abiente%20Dev/ScriptPyAiDeal/backend/tests/test_transformer.py)
- caso `test_expande_impostos_em_lancamentos_de_debito` (linhas `101-122`)

Status dos testes executados:
- `tests/test_transformer.py tests/test_dre_ingestao_service.py` -> **12 passed**
- `tests/test_dre_geracao_api.py tests/test_dre_geracao_completa_service.py` -> **12 passed**

## 4) O que ainda explica o desvio

Mesmo apos expandir impostos, o desvio continua relevante.

Ponto mais forte observado:
- Na natureza `1.1.1 - Recebimento de Clientes`:
  - referencia: `1.789.092,17` (26 linhas)
  - gerado: `1.176.432,63` (25 linhas)
  - delta: `-612.659,54`

Isso indica que **falta uma entrada de receita** no dataset atual em relacao ao arquivo de referencia.

## 5) Possivel causa estrutural adicional (ainda nao implementada)

A ingestao atual do transformer processa **uma aba principal so**:
- [/Users/gousero/Abiente Dev/ScriptPyAiDeal/backend/app/transformacao/engine.py:108](/Users/gousero/Abiente%20Dev/ScriptPyAiDeal/backend/app/transformacao/engine.py:108)

O parser usa `linha_cabecalho` fixa do mapping (`1`) para todas as abas:
- [/Users/gousero/Abiente Dev/ScriptPyAiDeal/backend/app/ingestao/parser.py:54](/Users/gousero/Abiente%20Dev/ScriptPyAiDeal/backend/app/ingestao/parser.py:54)
- [/Users/gousero/Abiente Dev/ScriptPyAiDeal/backend/config/dre_mapping.json](/Users/gousero/Abiente%20Dev/ScriptPyAiDeal/backend/config/dre_mapping.json)

No `.xls` real:
- `Sheet` tem cabecalho numa linha.
- `Planilha1` usa outra linha de cabecalho (na pratica, `header=4` para pandas).

Logo, ha risco de perda de dados quando a aba nao segue a linha de cabecalho padrao.

## 6) Diferenca entre arquivos de mesma nomenclatura e hash

Foram encontradas copias diferentes de `RELATORIO DRE MES 05.xls` com hashes distintos.

Exemplos:
- hash no DB para upload de maio: `1f44394e...bcfa`
- hash do arquivo em `Documents/AIDEAL/...`: `4d76312c...06be`

Importante:
- Apesar do hash binario diferente, em testes locais parser+transformer produziram o mesmo conjunto normalizado para o fluxo atual de ingestao.
- Isso nao elimina a necessidade de auditoria; apenas mostra que o parse atual extraiu os mesmos campos utilitarios dessas duas copias.

## 7) Proximo plano recomendado para Claude Opus

1. Implementar leitura robusta por aba com deteccao de cabecalho dinamica (scan das primeiras linhas).
2. Transformar **multi-aba** no DRE:
   - processar `Sheet` e `Planilha1` quando aplicavel;
   - consolidar e deduplicar por hash de linha normalizada.
3. Definir regra explicita para classificacao de `Planilha1` (saida) quando `CLASSIFICACAO` vier vazia.
4. Adicionar endpoint/relatorio de auditoria de ingestao:
   - hash binario do arquivo;
   - hash normalizado do dataset parseado;
   - contagem e soma por aba;
   - contagem e soma por natureza/conta pai.
5. Criar fixture de teste de regressao com `.xls` de duas abas e cabecalhos em linhas diferentes.
6. Regenerar `05/2025` apos limpar base e comparar com referencia por:
   - `BD_FLUXO` (fonte de verdade),
   - nao apenas cache de formula da aba DRE.

## 8) Comandos uteis para validacao (pos-fix)

### 8.1 Conferir meses no arquivo gerado
```bash
python3 - <<'PY'
from openpyxl import load_workbook
from collections import defaultdict
wb=load_workbook('/Users/gousero/Downloads/DRE_AIDEAL_05-2025_20260421_151514.xlsx', data_only=True)
ws=wb['BD_FLUXO']
agg=defaultdict(int)
for r in range(2,8000):
    ano,mes=ws.cell(r,8).value,ws.cell(r,9).value
    if ano and mes:
        agg[(int(ano),int(mes))]+=1
print(dict(agg))
PY
```

### 8.2 Conferir totais de maio no banco
```bash
sqlite3 '/Users/gousero/Abiente Dev/ScriptPyAiDeal/data/aideal.db' <<'SQL'
.headers on
.mode column
SELECT competencia_ano, competencia_mes, COUNT(*) qtd,
       ROUND(SUM(credito),2) credito,
       ROUND(SUM(debito),2) debito,
       ROUND(SUM(credito-debito),2) saldo
FROM dre_lancamentos
WHERE competencia_ano=2025 AND competencia_mes=5
GROUP BY competencia_ano, competencia_mes;
SQL
```

### 8.3 Comparar natureza-chave com referencia
```bash
python3 - <<'PY'
from openpyxl import load_workbook
from collections import defaultdict
def agg(path):
    wb=load_workbook(path,data_only=True); ws=wb['BD_FLUXO']
    s=defaultdict(float)
    for r in range(2,7000):
        m=ws.cell(r,9).value
        if not m: continue
        if int(m)!=5: continue
        nat=(ws.cell(r,6).value or '').strip()
        s[nat]+=float(ws.cell(r,13).value or 0)
    return s
ref=agg('/Users/gousero/Abiente Dev/ScriptPyAiDeal/DRE AIDEAL - 05 2025  - obra.xlsx')
new=agg('/Users/gousero/Downloads/DRE_AIDEAL_05-2025_20260421_151514.xlsx')
for k in ['1.1.1 - Recebimento de Clientes','IR','ISS','INSS','COFINS','CSLL','Tarifa de Antecipação']:
    print(k, round(ref.get(k,0),2), round(new.get(k,0),2), round(new.get(k,0)-ref.get(k,0),2))
PY
```

## 9) Resumo executivo

- **Meses passados nao estao contaminando o DRE de maio**.
- Havia bug na geracao/ingestao (impostos nao expandidos), ja corrigido.
- Ainda resta desvio estrutural de dados vs referencia, com destaque para uma receita faltante de `612.659,54`.
- Proxima etapa de alto impacto: ingestao multi-aba com deteccao robusta de cabecalho e auditoria forte.


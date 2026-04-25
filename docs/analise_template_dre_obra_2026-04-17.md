# Análise do Template DRE Obra

Arquivo analisado:
- `templates/dre/DRE AIDEAL - 05 2025  - obra.xlsx`

Data da análise:
- `2026-04-17`

## Visão geral do workbook

O template não é uma planilha simples preenchida célula a célula. Ele é um workbook OOXML com:

- 5 abas: `Painel`, `DRE`, `BD_FLUXO`, `PLANO_CONTAS`, `APOIO`
- 4 tables:
  - `DRE` em `A5:AI185`
  - `BD_FLUXO1` em `A1:R4964`
  - `PLANO_CONTAS` em `A1:E207`
  - `Meses` em `G1:H13`
- 1 pivot cache:
  - `xl/pivotCache/pivotCacheDefinition1.xml`
  - fonte: `worksheetSource name="BD_FLUXO1"`
- 3 pivot tables na aba `APOIO`
- 5 slicer caches
- 2 arquivos de slicer:
  - `slicer1.xml` na aba `Painel`
  - `slicer2.xml` na aba `DRE`
- drawings, charts, imagens e âncoras posicionadas em `Painel`, `DRE` e `APOIO`

Conclusão:
- a geração correta precisa preservar a estrutura OOXML do template e alimentar o workbook nos pontos certos;
- recriar abas, reserializar agressivamente XML ou desmontar pivots/slicers tende a quebrar a abertura/renderização no Excel.

## Papel de cada aba

### `BD_FLUXO`

É a tabela fato principal do workbook.

Tabela:
- `BD_FLUXO1`
- range físico do template: `A1:R4964`

Cabeçalho:
- `A`: `Data`
- `B`: `Histórico`
- `C`: `Crédito`
- `D`: `Débito`
- `E`: `Saldo`
- `F`: `Natureza`
- `G`: `Centro de Custo - Obra`
- `H`: `Ano Fluxo`
- `I`: `C. Mês`
- `J`: `Mês`
- `K`: `Banco`
- `L`: `Empresa`
- `M`: `Valor`
- `N`: `Rubrica`
- `O`: `Conta Filho`
- `P`: `Conta Pai`
- `Q`: `Cod`
- `R`: `Ano`

Observação crítica:
- o pivot cache usa `BD_FLUXO1` como fonte, não um range solto de worksheet;
- isso significa que o `ref` da table precisa acompanhar o volume real de linhas.

Colunas derivadas por fórmula no template:
- `H = YEAR(Ax)`
- `I = MONTH(Ax)`
- `J = INDEX(Meses[], BD_FLUXO!Ix, 2)`
- `M = Cx-Dx`
- `N = VLOOKUP(Fx, PLANO_CONTAS!A:D, 2, 0)`
- `O = VLOOKUP(Fx, PLANO_CONTAS!A:D, 3, FALSE)`
- `P = VLOOKUP(Fx, PLANO_CONTAS!A:D, 4, FALSE)`
- `Q = VLOOKUP(Fx, PLANO_CONTAS!A:E, 5, FALSE)`
- `R = YEAR(BD_FLUXO1[[#This Row],[Data]])`

Base operacional:
- `A:G` são dados reais de entrada;
- `H:R` são estrutura/fórmulas auxiliares do template;
- a geração deve alimentar `A:G` e preservar o comportamento de `H:R`.

### `PLANO_CONTAS`

É a camada estática de mapeamento usada pelas fórmulas de `BD_FLUXO`.

Tabela `PLANO_CONTAS` (`A1:E207`):
- `Classificação da empresa`
- `Rubrica`
- `Conta Filho`
- `Conta Pai`
- `Cod`

Tabela `Meses` (`G1:H13`):
- `C.M`
- `Mês`

Base operacional:
- essa aba é referência, não destino principal de escrita;
- se ela mudar, mudam rubricas e agrupamentos dos pivots.

### `APOIO`

É uma aba de pivots.

Relacionamentos:
- `sheet5.xml.rels` aponta para:
  - `pivotTable1.xml`
  - `pivotTable2.xml`
  - `pivotTable3.xml`

Pivots encontrados:
- `TB_dre`
- `tb_despesas`
- `Tabela dinâmica3`

Trecho observado no layout:
- `Conta Pai` em linhas
- meses em colunas
- totais agregados usados como base da DRE

Base operacional:
- `APOIO` não deve ser tratado como planilha “livre” para sobrescrita manual;
- ela é o resultado dos pivots que leem `BD_FLUXO1`.

### `DRE`

É a camada de apresentação final.

Tabela:
- `DRE` em `A5:AI185`

O conteúdo não vem direto de `BD_FLUXO`.
Ele vem principalmente de fórmulas contra `APOIO`, por exemplo:

- `=IFERROR(VLOOKUP($A6,APOIO!$B:$N,MATCH(B$5,APOIO!$B$5:$N$5,0),FALSE),0)`

O padrão da aba é:
- colunas mensais: `Jan`, `%Jan`, `Fev`, `%Fev`, ...
- colunas de trimestre calculadas por soma
- colunas de ano no fim
- várias linhas da DRE buscam valores agregados por `Conta Pai`

Base operacional:
- a DRE não deve ser “recalculada” no backend linha a linha;
- o ideal é preservar a tabela/fórmulas do template e apenas controlar a visibilidade das colunas conforme os meses usados.

### `Painel`

É a camada visual com charts e slicers de navegação/visão gerencial.

Relacionamentos:
- `sheet1.xml.rels` contém:
  - drawing
  - image
  - slicer

## Slicers

### Aba `Painel`

`slicer1.xml` contém 4 slicers:
- `Empresa`
- `Ano`
- `Mês`
- `Conta Pai`

Esses slicers usam caches:
- `SegmentaçãodeDados_Empresa`
- `SegmentaçãodeDados_Ano`
- `SegmentaçãodeDados_Mês`
- `SegmentaçãodeDados_Conta_Pai`

### Aba `DRE`

`slicer2.xml` contém 1 slicer:
- `Centro de Custo - Obra`

Esse slicer usa o cache:
- `SegmentaçãodeDados_Centro_de_Custo___Obra`

Conclusão operacional:
- os slicers não filtram a `DRE` diretamente por fórmulas;
- eles filtram pivots ligados ao pivot cache que nasce de `BD_FLUXO1`.

## Pivot cache

Fonte do cache:
- `worksheetSource name="BD_FLUXO1"`

Campos do cache:
- 18 campos, espelhando a tabela `BD_FLUXO1`

Ponto crítico:
- o template original carrega `pivotCacheRecords1.xml`
- também existe relação explícita em:
  - `xl/pivotCache/_rels/pivotCacheDefinition1.xml.rels`

Isso indica que o Excel espera consistência entre:
- `pivotCacheDefinition`
- `pivotCacheRecords`
- relacionamento `.rels`
- `[Content_Types].xml`

## Drawings e âncoras

Há desenhos ancorados em:
- `drawing1.xml` para `Painel`
- `drawing2.xml` para `DRE`
- `drawing3.xml` para `APOIO`

Indício importante:
- na aba `DRE`, o drawing está ancorado no topo da sheet;
- isso reforça o cuidado em não colapsar a região inicial da aba nem reescrever XML de forma que remova `extLst`, `drawing`, `slicer` ou namespaces de compatibilidade.

## Leitura correta do template

O encadeamento funcional do workbook é:

1. gravar lançamentos reais em `BD_FLUXO1`
2. manter as colunas derivadas da própria table funcionando
3. deixar o pivot cache/pivots da aba `APOIO` apontarem para essa table
4. deixar a aba `DRE` puxar os agregados de `APOIO`
5. preservar slicers, drawings e charts do `Painel` e da `DRE`

## Estratégia correta de geração

Com base no template `obra`, a geração deve seguir esta lógica:

1. Abrir o template original preservando OOXML.
2. Limpar apenas a faixa de dados reais de `BD_FLUXO`.
3. Escrever apenas as colunas de entrada reais na table.
4. Ajustar o `ref` da tabela `BD_FLUXO1` para a última linha real.
5. Não recriar pivots/slicers via biblioteca.
6. Preservar `APOIO` como aba de pivots do template.
7. Preservar `DRE` como aba de fórmulas e apresentação.
8. Controlar apenas a visibilidade de colunas na `DRE` quando necessário.
9. Forçar refresh/recalc na abertura com o mínimo de reserialização OOXML.

## Implicações práticas para implementação

Se o objetivo é “gerar igual ao template”, o contrato técnico implícito é:

- `BD_FLUXO1` é a fonte de verdade do Excel;
- `APOIO` é derivado por pivot;
- `DRE` é derivado por fórmula;
- slicers dependem de pivot cache íntegro;
- qualquer alteração em `sheet2.xml`, `sheet5.xml`, `pivotCacheDefinition1.xml`, `.rels` de cache, `slicer*.xml` ou `tables/table2.xml` precisa ser tratada como sensível.

## Resumo executivo

O template foi construído para ser alimentado por `BD_FLUXO1`.
Não é um arquivo para “montar a DRE diretamente”.

A base segura de geração é:
- preencher `BD_FLUXO1` corretamente;
- preservar `PLANO_CONTAS` e `Meses`;
- não destruir pivots de `APOIO`;
- não destruir fórmulas/tabela da `DRE`;
- não quebrar o pacote OOXML de slicers/drawings/pivot cache.

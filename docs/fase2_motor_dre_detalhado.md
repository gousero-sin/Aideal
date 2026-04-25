# Fase 2 - Motor DRE AIDEAL

## Resumo executivo

Esta fase implementa o fluxo completo do DRE no padrão AIDEAL, da entrada da planilha bruta ao arquivo final `.xlsx` preservando o template oficial.

O objetivo operacional desta etapa é:
- validar a estrutura do arquivo de origem;
- transformar os lançamentos em linhas compatíveis com o template;
- escrever o resultado no workbook oficial sem destruir fórmulas, tabelas e demais elementos do modelo;
- entregar uma UI mínima para executar, acompanhar e baixar o resultado final.

O arquivo `RELATORIO DE MOVIMENTO BI ITAU.xlsx` foi validado com sucesso na Etapa 1 e permanece como referência estrutural para a expansão futura do fluxo de caixa.

## Inventário de Caminhos

### Entradas e referências do workspace
- `RELATORIO DRE MES 05.xls`
- `RELATORIO DE MOVIMENTO BI ITAU.xlsx`
- `templates/dre/DRE AIDEAL - 05 2025  - obra.xlsx`
- `templates/fluxo_caixa/Fluxo de Caixa A Ideal - 07 2025.xlsx`
- `backend/config/dre_mapping.json`
- `goflow-core/goflow-core-1.1.0.tgz`
- `output`

### Caminhos completos
- `/Users/gousero/Abiente Dev/ScriptPyAiDeal/RELATORIO DRE MES 05.xls`
- `/Users/gousero/Abiente Dev/ScriptPyAiDeal/RELATORIO DE MOVIMENTO BI ITAU.xlsx`
- `/Users/gousero/Abiente Dev/ScriptPyAiDeal/templates/dre/DRE AIDEAL - 05 2025  - obra.xlsx`
- `/Users/gousero/Abiente Dev/ScriptPyAiDeal/templates/fluxo_caixa/Fluxo de Caixa A Ideal - 07 2025.xlsx`
- `/Users/gousero/Abiente Dev/ScriptPyAiDeal/backend/config/dre_mapping.json`
- `/Users/gousero/Abiente Dev/ScriptPyAiDeal/goflow-core/goflow-core-1.1.0.tgz`
- `/Users/gousero/Abiente Dev/ScriptPyAiDeal/output`

## Escopo da Fase 2

### Inclui
- processamento DRE ponta a ponta;
- execução por API;
- interface mínima no frontend;
- download do arquivo final;
- logs e rastreabilidade do processamento;
- geração de documentação executiva e técnica.

### Não inclui
- consolidação de fluxo de caixa multi-banco;
- expansão do painel GoFlow para métricas além do DRE;
- refatoração estrutural do backend de fluxo de caixa;
- mudanças no template oficial fora da faixa de dados aprovada.

## Contrato funcional do DRE

### Entrada
- um arquivo `.xls` ou `.xlsx`;
- competência no formato `MM/AAAA`;
- planilha com estrutura compatível com o mapeamento vigente.

### Regras de negócio
- 1 linha no template final para cada lançamento útil da planilha de origem;
- modo cumulativo obrigatório: competência `MM/AAAA` exige dados do mesmo ano com meses `01..MM`;
- quando a classificação indicar saída, o valor vai para débito;
- nos demais casos, o valor vai para crédito;
- o processamento deve bloquear apenas erros estruturais, preservando warnings de qualidade quando o dado for recuperável.

### Saída
- workbook final `.xlsx` com dados escritos no template oficial;
- arquivo salvo em `output`;
- log estruturado com status, contagens, warnings e erros;
- link de download consumível pela UI.

## Pipeline técnico

### 1. Validação
- confirmar formato do arquivo;
- detectar aba principal;
- mapear colunas por alias;
- identificar cabeçalhos repetidos e linhas estruturais;
- validar data, crédito e natureza;
- registrar warnings sem bloquear quando o problema não comprometer a geração.

### 2. Transformação
- converter cada linha útil em um lançamento normalizado;
- calcular crédito e débito por regra de classificação;
- preservar linha e aba de origem;
- excluir linhas de estrutura, cabeçalhos repetidos e placeholders;
- limitar a escrita ao volume suportado pelo template.

### 3. Escrita no template
- abrir o workbook oficial preservando sua estrutura;
- limpar a faixa de dados aprovada na aba `BD_FLUXO`;
- escrever somente `A:G` a partir da linha 2;
- preservar fórmulas, estilos, filtros, tabela e colunas derivadas;
- salvar uma cópia nova no diretório `output`.

### 4. Orquestração
- gerar identificador de processamento;
- persistir log com estado e contagens;
- expor resultado por API;
- permitir download direto pela interface web.

## Arquitetura de interface

### Frontend
- manter a seleção de fluxo;
- manter a validação atual;
- adicionar ação de geração do DRE final;
- exibir competência, status, contagem de registros, warnings e erros;
- oferecer download do arquivo final quando houver sucesso.

### Backend esperado
- `POST /api/processar/dre`
- `GET /api/processamentos/{id}`
- `GET /api/processamentos/{id}/download`

## Plano de implementação

### Bloco 1 - Contrato de entrada e saída
- congelar campos esperados do processamento;
- validar como a UI envia `arquivo` e `competencia`;
- alinhar nomenclatura de retorno para download e status.

### Bloco 2 - Processamento DRE
- processar o arquivo de referência `RELATORIO DRE MES 05.xls`;
- gerar saída em `output`;
- garantir preservação do template.

### Bloco 3 - UI operacional
- permitir validar antes de gerar;
- permitir gerar sem abandonar a tela;
- mostrar mensagem clara de sucesso ou falha;
- liberar download imediato do arquivo processado.

### Bloco 4 - Documentação e empacotamento
- manter a fonte em Markdown;
- gerar PDF executivo;
- validar página, título, seções e caminhos completos.

## Critérios de aceite

- o arquivo DRE bruto gera workbook final no template oficial;
- o template não perde estrutura;
- o botão de geração funciona pela interface;
- o download final fica disponível após processamento;
- o PDF da Fase 2 é gerado com fonte Inter, cabeçalho, rodapé e paginação.

## Política oficial de aceite de diff (BD_FLUXO)

- Overlap de linhas entre `obra` e arquivo gerado pode ser zero; o dataset de origem do processamento é diferente do template-base.
- A célula `BD_FLUXO!F1644` pode ficar vazia no gerado; isso é esperado após limpeza da faixa `A2:G4964`.
- As colunas derivadas `H:R` permanecem com fórmulas do template; valores cacheados podem vir vazios até recálculo no Excel Desktop.
- Diferenças em `Painel`, `DRE`, `PLANO_CONTAS` e `APOIO` só são aceitas quando restritas à serialização não semântica; alteração estrutural nesses XMLs é regressão.
- Exemplo de leitura correta para maio/2025:
  - range físico da sheet `BD_FLUXO`: `A1:R4964`;
  - linhas efetivamente preenchidas com lançamentos: `N` (volume do lote cumulativo recebido);
  - cabeçalho: linha `1`;
  - última linha com dados reais: `1 + N`;
  - linhas a partir de `2 + N`: ficam sem lançamento real e mantêm estrutura/fórmulas do template.
- As linhas sem lançamento real podem ser ocultadas por configuração, sem remover fórmulas/estrutura.
- Padrão atual: manter visível (sem ocultação automática) para evitar salto de navegação da linha 861 para 4965.
- Regra operacional obrigatória: nunca tratar contagem física da sheet como contagem de registros processados.
- Modo operacional atual (`limpar_faixa_saida=true`): limpa `A2:G4964` e reescreve o lote cumulativo integral para evitar dependência de dados legados da template.
- Regras de período cumulativo bloqueiam:
  - mês acima da competência;
  - meses faltantes entre janeiro e competência;
  - ano divergente da competência.

## Plano de teste

- teste de validação do DRE de referência;
- teste de geração com arquivo válido;
- teste de download do arquivo final;
- teste de preservação do template com `BD_FLUXO1`;
- teste de PDF gerado e leitura das seções principais;
- teste visual da UI em desktop e mobile.

## Riscos e mitigação

- risco de arquivo de origem com cabeçalho repetido no corpo; mitigação: ignorar linhas estruturais na validação e transformação;
- risco de perder fórmulas ao salvar template; mitigação: escrever apenas a faixa aprovada de dados;
- risco de divergência de nomenclatura do backend; mitigação: frontend tolerante a `download_url`, `arquivo_saida` e `id`;
- risco de retrabalho por contratos instáveis; mitigação: manter a fonte de verdade documentada neste arquivo.

## Próxima fase

Após a homologação desta fase, a próxima entrega é a consolidação do Fluxo de Caixa multi-banco, mantendo a mesma filosofia de preservação de template e execução local por padrão.

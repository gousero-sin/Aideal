# Plano de Etapas do MVP AIDEAL GoFlowOS

## Capa

**Projeto:** MVP AIDEAL GoFlowOS  
**Subtítulo:** Cloudflare (browser-first) + Local/Servidor próprio  
**Data de referência:** 30/03/2026  
**Versão:** v1.0

## Resumo executivo

### Objetivo do MVP
Construir um MVP executivo-operacional para receber planilhas financeiras brutas e gerar workbooks finais no padrão AIDEAL, preservando a estrutura dos templates de saída (sheets, fórmulas, filtros, tabelas, segmentações e layout), com operação simplificada para usuários administrativos.

### Escopo principal
- Conversão automática do fluxo DRE.
- Consolidação e conversão automática do Fluxo de Caixa (múltiplos bancos em estrutura-base compatível).
- Painel operacional baseado no GoFlow Core, com indicadores e acompanhamento de execução.

### Decisões já fechadas
- Preservação máxima de template Excel.
- Layout-base comum para bancos na fase inicial (mesma estrutura-base do arquivo Itaú).
- Erro bloqueante para classificações não mapeadas.
- Processamento local por padrão no modo Cloudflare (browser-first).

## Etapas por partes

## Etapa 1 — Fundação e arquitetura
**Período:** 30/03/2026 a 01/04/2026

### Objetivo
Estabelecer a base técnica única do projeto (web + engine + execução local), definindo contratos de dados, organização de módulos e baseline de validação.

### Entradas
- Requisitos e escopo validados.
- Templates oficiais DRE e Fluxo de Caixa.
- Exemplos reais de entrada (`RELATORIO DRE MES 05.xls`, `RELATORIO DE MOVIMENTO BI ITAU.xlsx`).
- Pacote `goflow-core-1.1.0.tgz`.

### Atividades
- Estruturar diretórios de aplicação, engine de transformação e configurações de mapeamento.
- Definir contratos de dados normalizados para DRE e Fluxo de Caixa.
- Definir padrão de validação de arquivos de entrada e mensagens de erro.
- Implementar baseline técnico de preservação de template (diferença estrutural controlada por artefato).

### Entregáveis
- Estrutura inicial de projeto pronta para desenvolvimento em paralelo.
- Contratos de dados e interfaces internas documentados.
- Especificação inicial de validação de entrada.

### Critérios de aceite
- Estrutura de projeto criada e executável localmente.
- Contratos de dados revisados e versionados.
- Regras básicas de validação definidas para ambos os fluxos.

### Dependências
- Disponibilidade dos templates finais e amostras de entrada.
- Definição de estratégia de escrita não destrutiva em templates Excel.

### Riscos e mitigação
- **Risco:** perda de elementos avançados do template ao salvar arquivo.  
  **Mitigação:** escrever somente áreas de dados previstas e validar estrutura após geração.
- **Risco:** ambiguidade de mapeamento inicial.  
  **Mitigação:** centralizar regras em arquivos de configuração e validar com casos reais.

### Prazo
Início: 30/03/2026  
Fim: 01/04/2026

## Etapa 2 — Motor DRE
**Período:** 02/04/2026 a 08/04/2026

### Objetivo
Implementar o pipeline completo de ingestão, validação, transformação e geração do arquivo final DRE no padrão AIDEAL.

### Entradas
- Arquivo bruto DRE em `.xls`/`.xlsx`.
- Template final DRE oficial.
- Regras de mapeamento de campos, naturezas e centros de custo.

### Atividades
- Implementar parser para entrada DRE (sheet principal e planilhas complementares).
- Normalizar lançamentos em crédito/débito e expansões de tributos/tarifas.
- Aplicar regras de validação estrutural (abas, colunas obrigatórias, tipos de dado).
- Gerar workbook final preenchendo áreas de dados no template oficial.
- Produzir log de execução com status, contagens e pendências.

### Entregáveis
- Motor DRE funcional ponta a ponta.
- Exportação de arquivo `.xlsx` final pronto para uso.
- Relatório de validação com erros e warnings.

### Critérios de aceite
- Geração correta do DRE final para o arquivo de referência.
- Preservação de sheets, fórmulas e estrutura do template.
- Mensagem clara em caso de estrutura inválida.

### Dependências
- Etapa 1 concluída.
- Mapeamento de classificação consolidado para DRE.

### Riscos e mitigação
- **Risco:** variações de planilha de origem fora do padrão esperado.  
  **Mitigação:** validação bloqueante e relatório de inconsistência orientado ao usuário.
- **Risco:** arredondamentos divergentes.  
  **Mitigação:** padronização decimal e testes de reconciliação por subtotal.

### Prazo
Início: 02/04/2026  
Fim: 08/04/2026

## Etapa 3 — Motor Fluxo de Caixa
**Período:** 09/04/2026 a 15/04/2026

### Objetivo
Implementar consolidação multiarquivos por banco e geração do Fluxo de Caixa final em template oficial.

### Entradas
- Múltiplos relatórios bancários com estrutura-base compatível.
- Template final Fluxo de Caixa oficial.
- Dicionário de normalização de classificações (aliases).

### Atividades
- Implementar ingestão em lote e identificação de banco/origem por arquivo.
- Normalizar colunas e tipos de transação (crédito, débito, transferência).
- Consolidar movimentos em base única com rastreabilidade por origem.
- Aplicar classificação financeira e validação de mapeamento.
- Gerar workbook final com filtros superiores e visão consolidada preservados.

### Entregáveis
- Motor de Fluxo de Caixa funcional ponta a ponta.
- Arquivo final `.xlsx` consolidado e organizado no padrão AIDEAL.
- Relatório de execução e reconciliação.

### Critérios de aceite
- Processamento de lote multi-banco com saída única válida.
- Filtros e visões consolidadas alimentados com banco/origem.
- Erro bloqueante ao detectar classificação não mapeada.

### Dependências
- Etapa 1 concluída.
- Regras de normalização de classificação aprovadas.

### Riscos e mitigação
- **Risco:** diferenças de nomenclatura entre bancos para a mesma natureza.  
  **Mitigação:** camada de aliases versionada e validação com histórico.
- **Risco:** divergência de saldo por tratamento de transferências.  
  **Mitigação:** regra explícita por tipo e auditoria de reconciliação.

### Prazo
Início: 09/04/2026  
Fim: 15/04/2026

## Etapa 4 — Painel GoFlow + KPIs
**Período:** 16/04/2026 a 21/04/2026

### Objetivo
Disponibilizar interface operacional executiva para upload, execução, monitoramento, download e leitura de indicadores.

### Entradas
- `goflow-core` como base visual e de componentes.
- Motores DRE e Fluxo concluídos (Etapas 2 e 3).
- Diretrizes visuais AIDEAL (paleta, tipografia e proporções de uso).

### Atividades
- Implementar tela inicial com seleção de fluxo (DRE ou Fluxo de Caixa).
- Implementar upload e validação guiada por fluxo.
- Implementar status de execução (em andamento, concluído, erro).
- Implementar download do arquivo final e histórico de processamentos.
- Implementar KPIs operacionais e financeiros básicos de acompanhamento.
- Adaptar identidade visual para padrão executivo corporativo AIDEAL.

### Entregáveis
- Painel operacional web funcional.
- Jornada completa de processamento via interface.
- KPIs iniciais de execução e resultado.

### Critérios de aceite
- Usuário administrativo executa os dois fluxos sem linha de comando.
- Erros de validação aparecem com clareza e ação sugerida.
- Interface aderente à identidade visual aprovada.

### Dependências
- Etapas 2 e 3 concluídas.
- Definição final de indicadores e visualização.

### Riscos e mitigação
- **Risco:** UI conflitar com padrões visuais originais do GoFlow Core.  
  **Mitigação:** camada de temas/tokens dedicada sem alterar núcleo proprietário.
- **Risco:** regressões na experiência de upload de múltiplos arquivos.  
  **Mitigação:** testes de fluxo com lotes reais e simulação de erro.

### Prazo
Início: 16/04/2026  
Fim: 21/04/2026

## Etapa 5 — Deploy, QA final e handover
**Período:** 22/04/2026 a 24/04/2026

### Objetivo
Finalizar a solução para uso em Cloudflare e ambiente local/servidor próprio, com validação final e documentação de operação.

### Entradas
- Aplicação completa das etapas anteriores.
- Checklist de qualidade técnico-funcional.
- Ambiente alvo Cloudflare + ambiente local.

### Atividades
- Configurar build e deploy em Cloudflare Pages (modo browser-first).
- Validar execução local (CLI/API) para migração futura em servidor próprio.
- Executar testes finais funcionais e de regressão.
- Consolidar manual resumido de operação.
- Realizar handover técnico com checklist de aceite final.

### Entregáveis
- Deploy operacional em Cloudflare.
- Rotina local documentada e funcional.
- Pacote de documentação final (uso, validação, troubleshooting).

### Critérios de aceite
- MVP funcional em ambos os modos (Cloudflare e local).
- Testes finais aprovados sem bloqueadores.
- Documentação suficiente para operação assistida e continuidade.

### Dependências
- Conclusão das etapas 1 a 4.
- Acesso aos ambientes de deploy e validação.

### Riscos e mitigação
- **Risco:** comportamento diferente entre navegadores/ambientes.  
  **Mitigação:** bateria final de testes cruzados e validação de compatibilidade.
- **Risco:** atraso por ajustes de última hora em mapeamentos.  
  **Mitigação:** janela de hardening dedicada e congelamento de escopo no início da etapa.

### Prazo
Início: 22/04/2026  
Fim: 24/04/2026

## Matriz de rastreabilidade (requisito → etapa)

### Requisitos funcionais (RF)
- **RF-01 (seleção de fluxo DRE/FC):** Etapa 4.
- **RF-02 (DRE com geração padrão AIDEAL):** Etapa 2.
- **RF-03 (múltiplos bancos no Fluxo de Caixa):** Etapa 3.
- **RF-04 (registro de banco/origem):** Etapa 3 e Etapa 4.
- **RF-05 (preservação de template):** Etapa 1, Etapa 2 e Etapa 3.
- **RF-06 (mensagens claras de erro):** Etapa 2, Etapa 3 e Etapa 4.
- **RF-07 (exportação .xlsx):** Etapa 2, Etapa 3 e Etapa 4.
- **RF-08 (acompanhamento via painel GoFlow):** Etapa 4.

### Requisitos não funcionais (RNF)
- **RNF-01 (compatibilidade .xls/.xlsx):** Etapa 2 e Etapa 3.
- **RNF-02 (confiabilidade de template):** Etapa 1, Etapa 2 e Etapa 3.
- **RNF-03 (auditabilidade/logs):** Etapa 2, Etapa 3 e Etapa 5.
- **RNF-04 (usabilidade sem CLI):** Etapa 4.
- **RNF-05 (portabilidade local/web interno):** Etapa 5.
- **RNF-06 (segurança e limpeza de temporários):** Etapa 2, Etapa 3 e Etapa 5.

## Cronograma consolidado

### Linha do tempo
- **30/03 a 01/04:** Etapa 1 — Fundação e arquitetura.
- **02/04 a 08/04:** Etapa 2 — Motor DRE.
- **09/04 a 15/04:** Etapa 3 — Motor Fluxo de Caixa.
- **16/04 a 21/04:** Etapa 4 — Painel GoFlow + KPIs.
- **22/04 a 24/04:** Etapa 5 — Deploy, QA final e handover.

### Marcos
- **M1:** arquitetura e contratos fechados (01/04/2026).
- **M2:** motor DRE homologado (08/04/2026).
- **M3:** motor Fluxo de Caixa homologado (15/04/2026).
- **M4:** painel operacional com KPIs pronto (21/04/2026).
- **M5:** entrega final e handover concluídos (24/04/2026).

### Marco final de conclusão
**24/04/2026**

## Apêndices

## Apêndice A — Glossário de campos (DRE/Fluxo)

### Campos essenciais DRE
- **Data:** data do lançamento financeiro.
- **Histórico:** identificação textual do lançamento/documento.
- **Crédito/Débito:** valor de entrada e saída.
- **Natureza:** classificação financeira origem.
- **Centro de Custo - Obra:** dimensão de alocação.
- **Rubrica/Conta Pai:** agrupadores para visão gerencial final.

### Campos essenciais Fluxo de Caixa
- **Data Mov.:** data da movimentação bancária.
- **Tipo:** crédito, débito ou transferência.
- **Descrição:** histórico da transação.
- **Valor:** montante da operação.
- **Saldo:** saldo após lançamento.
- **Conta Gerencial/Classificação:** categoria financeira para consolidação.
- **Banco/Origem:** identificação da instituição fonte.

## Apêndice B — Política de tratamento de erro
- Erro de estrutura de entrada: bloquear processamento e informar coluna/aba ausente.
- Erro de mapeamento de classificação: bloquear processamento e listar pendências.
- Erro de consistência numérica: bloquear geração e apresentar reconciliação mínima.
- Warning de qualidade: permitir geração quando não comprometer cálculo final, registrando no log.

## Apêndice C — Premissas operacionais
- Processamento local por padrão no modo Cloudflare (browser-first).
- Sem dependência obrigatória de armazenamento em nuvem para uso básico.
- Possibilidade de execução local ou em servidor próprio mantida desde a base arquitetural.
- Público alvo operacional: gestão e time técnico-administrativo.

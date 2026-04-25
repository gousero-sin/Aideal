# Relatório de Diff — referência correta = arquivo **obra**

## Arquivos comparados
- **Correto (fonte de verdade):** `DRE AIDEAL - 05 2025  - obra.xlsx`
- **Comparado:** `AIDEAL_DRE_05-2025_20260402_133713.xlsx`

## Metodologia
A comparação foi feita em três níveis:
1. **Estrutura**: abas, dimensões, tabelas, filtros, congelamento de painel, nomes definidos.
2. **Lógica**: fórmulas e referências.
3. **Conteúdo**: valores célula a célula, tomando o arquivo **obra** como baseline.

## Resumo executivo
Conclusão: o arquivo `AIDEAL_DRE_05-2025_20260402_133713.xlsx` **não corresponde** ao conteúdo do arquivo **obra**.

Os desvios reais estão concentrados em:
- **BD_FLUXO**: divergência massiva de conteúdo bruto.
- **APOIO**: divergência relevante em linhas e agregações.
- **DRE**: fórmulas idênticas ao obra, porém com `style_id` interno diferente; visualmente o estilo equivalente é o mesmo.
- **PLANO_CONTAS** e **Painel**: sem divergência funcional.

## Estrutura geral
- Mesmas abas: `Painel`, `DRE`, `BD_FLUXO`, `PLANO_CONTAS`, `APOIO`
- Mesmas dimensões por aba
- Mesmos cabeçalhos
- Mesmas tabelas, filtros, merges, freeze panes e nomes definidos
- Mesma quantidade de fórmulas por aba

Isso indica que o arquivo comparado preservou a **casca estrutural** da planilha, mas alterou o **conteúdo base**.

## Quantitativo por aba
| Aba | Células com diferença real de conteúdo | Observação |
| --- | --- | --- |
| Painel | 0 | Sem diferença |
| DRE | 0 | Sem diferença de valores/fórmulas; apenas style_id interno diferente em 3.184 células |
| BD_FLUXO | 26481 | Diferença massiva de conteúdo em A:G; H:R mantidos por fórmulas/estrutura |
| PLANO_CONTAS | 0 | Sem diferença |
| APOIO | 555 | Diferenças de valores e rótulos, principalmente entre linhas 6 e 108 |

## Achado crítico 1 — `BD_FLUXO` do arquivo comparado não é o mesmo dataset do obra
### Evidências objetivas
- Linhas totais em ambos: **4.964**
- Linhas em comum por conteúdo completo (incluindo cabeçalho): **1**
- Ou seja: na prática, **apenas o cabeçalho coincide**.

### Perfil dos dados
| Métrica | obra | comparado |
| --- | --- | --- |
| Métrica | obra | comparado |
| Período em `A` | 2025-01-01 a 2025-05-31 | 2025-05-01 a 2025-05-31 |
| Linhas com data preenchida (coluna A) | 4962 | 860 |
| Linhas com histórico preenchido (coluna B) | 4963 | 860 |
| Linhas com natureza preenchida (coluna F) | 4963 | 11 |
| Última linha preenchida em A | 4964 | 861 |

### Interpretação
O arquivo comparado parece conter:
- apenas **860 linhas úteis** preenchidas em `A:G`;
- uma tabela ainda estendida até a linha **4964** por herança estrutural;
- dados com natureza simplificada, quase sempre `1 - ENTRADA` nas poucas linhas com `Natureza` preenchida;
- conteúdo incompatível com o fluxo do obra.

### Exemplos de divergência em `BD_FLUXO`
| Linha | Data (obra) | Data (comparado) | Histórico (obra) | Histórico (comparado) | Natureza (obra) | Natureza (comparado) | Centro custo (obra) | Centro custo (comparado) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | 2025-01-02 | 2025-05-09 | 6470 - AIDEAL SOLUÇÕES ANTICORROSIVAS LTDA | NIOBIO | 1.2.3 - Origens Financeiras | 1 - ENTRADA | ADMINISTRATIVO | NIOBIO CMOC CONTRATO |
| 3 | 2025-01-06 | 2025-05-12 | 6572 - CMOC BRASIL MINERAÇAO INDUSTRIAL E PAR | SERVIÇO JATEAMENTO E PINTURA MAQUINA DE RECIC | 1.1.1 - Recebimento de Clientes | 1 - ENTRADA | CMOC CONTRATO VIEGENCIA | CANTEIRO DE OBRA |
| 4 | 2025-01-06 | 2025-05-13 | 6574 - VLI MULTIMODAL S.A | FOSFATO | 1.1.1 - Recebimento de Clientes | 1 - ENTRADA | VLI PINTURA | FOSFATO CMOC CONTRAT |
| 5 | 2025-01-07 | 2025-05-16 | 6645 - AIDEAL SOLUÇÕES ANTICORROSIVAS LTDA | NIOBIO | 1.2.3 - Origens Financeiras | 1 - ENTRADA | ADMINISTRATIVO | NIOBIO CMOC CONTRATO |
| 6 | 2025-01-08 | 2025-05-19 | 6672 - AIDEAL SOLUÇÕES ANTICORROSIVAS LTDA | NIOBIO | 1.2.3 - Origens Financeiras | 1 - ENTRADA | ADMINISTRATIVO | NIOBIO CMOC CONTRATO |
| 7 | 2025-01-08 | 2025-05-19 | 6673 - AIDEAL SOLUÇÕES ANTICORROSIVAS LTDA | FOSFATO | 1.2.3 - Origens Financeiras | 1 - ENTRADA | ADMINISTRATIVO | FOSFATO CMOC CONTRAT |

### Diferenças por coluna em `BD_FLUXO`
| Coluna | Cabeçalho | Qtde de células divergentes |
| --- | --- | --- |
| A | Data | 4962 |
| B | Histórico | 4963 |
| C | Crédito | 1007 |
| D | Débito | 4816 |
| E | Saldo | 860 |
| F | Natureza | 4963 |
| G | Centro de Custo - Obra | 4910 |
| H | Ano Fluxo | 0 |
| I | C. Mês | 0 |
| J | Mês | 0 |
| K | Banco | 0 |
| L | Empresa | 0 |
| M | Valor | 0 |
| N | Rubrica | 0 |
| O | Conta Filho | 0 |
| P | Conta Pai | 0 |
| Q | Cod | 0 |
| R | Ano | 0 |

## Achado crítico 2 — `APOIO` diverge do obra
A aba `APOIO` possui **555 células** com diferença de conteúdo real.

### Padrão observado
- divergências concentradas entre as linhas **6 e 108**;
- mudança de rótulos de linhas;
- deslocamento/redistribuição de valores entre colunas mensais;
- pequenas diferenças de precisão decimal em alguns acumulados.

### Exemplos de divergência em `APOIO`
| Linha | Diferenças resumidas |
| --- | --- |
| 6 | B: (=)Receita Bruta -> (+)Receita Bruta ; C: 173156.44 -> None ; D: 420327.6 -> None ; G: None -> 423451.89 ; H: 593484.04 -> 423451.89 ; AB: 1873832.2599999998 -> 1873832.26 |
| 7 | B: (+)Receita Bruta -> (=)Receita Bruta ; C: 173156.44 -> None ; D: 420327.6 -> None ; G: None -> 423451.89 ; H: 593484.04 -> 423451.89 ; AA: -196307.47999999995 -> -196307.48 |
| 8 | C: 173156.44 -> None ; D: 420327.6 -> None ; G: None -> 423451.89 ; H: 593484.04 -> 423451.89 ; AA: -119531.11999999992 -> -119531.1199999999 ; AC: -54747.829999999994 -> -54747.82999999999 |
| 9 | A: 2 -> 3 ; B: (-)Deduções sobre vendas -> (-)Custos Variavéis ; C: -17981.980000000003 -> None ; D: -55263.83 -> None ; G: None -> 60926.00891800001 ; H: -73245.81 -> 60926.00891800001 |
| 10 | A: 2 -> 3 ; B: Impostos sobre Vendas -> FRETE MATERIAIS E EQUIPAMENTOS ; C: -17981.980000000003 -> None ; D: -55263.83 -> None ; G: None -> 10742.678918 ; H: -73245.81 -> 10742.678918 |
| 11 | A: 2 -> 3 ; B: cofins -> FRETE TINTAS E SOLVENTE ; C: -3952.08 -> None ; D: -12145.89 -> None ; G: None -> 1890 ; H: -16097.97 -> 1890 |

## Achado crítico 3 — `DRE` está estruturalmente igual, mas pode estar com cache estático
### O que foi encontrado
- **0 diferenças** de fórmulas.
- **0 diferenças** de valores armazenados em cache na leitura `data_only=True`.
- **3.184 diferenças** apenas em `style_id` interno, porém com estilo efetivo equivalente.

### Interpretação técnica
A aba `DRE` usa fórmulas como:
- `VLOOKUP(..., APOIO!...)`
- somas e percentuais derivados

Como a aba `APOIO` mudou e a `DRE` permaneceu com resultados idênticos ao obra, há forte indício de que o arquivo comparado foi salvo **sem recálculo efetivo** da DRE, preservando cache anterior.  
Em outras palavras: o arquivo comparado pode estar **internamente inconsistente** — base alterada, mas demonstrativo final não recalculado.

## Conclusão técnica
Tomando o arquivo **obra** como correto:
1. O arquivo `AIDEAL_DRE_05-2025_20260402_133713.xlsx` **não é uma variante fiel** do obra.
2. A maior quebra está na aba **BD_FLUXO**, cujo dataset é essencialmente outro.
3. A aba **APOIO** também foi alterada de forma relevante.
4. A aba **DRE** aparenta manter resultado/cache do obra, apesar da mudança na base, o que é um sinal de **inconsistência funcional**.
5. Para qualquer validação, auditoria ou uso operacional, o arquivo correto a ser considerado é o **obra**.

## Arquivos anexos gerados
- `diff_BD_FLUXO_obra_vs_alternativo.csv` — diff completo célula a célula da aba BD_FLUXO
- `diff_APOIO_obra_vs_alternativo.csv` — diff completo célula a célula da aba APOIO
- `diff_DRE_style_ids_only.csv` — diferenças internas de style_id na DRE

## Recomendação objetiva
Se o objetivo é reconstruir o arquivo alternativo corretamente, o caminho é:
1. restaurar `BD_FLUXO` a partir do **obra**;
2. recalcular `APOIO`;
3. forçar recálculo completo da `DRE` no Excel;
4. só então salvar uma nova versão.

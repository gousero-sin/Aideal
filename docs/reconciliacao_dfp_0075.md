# Conferência da DFP 0075-26 — BUNGE

Referência: `REV.01 - DFP 0075-26 BUNGE - JAT. E PINT. EXTRATOR EXT3T.xlsx`, fornecida pelo usuário. A planilha foi usada como dado comparativo, sem alteração do arquivo e sem executar conteúdo nela contido.

## Resultado da comparação

Os valores armazenados na aba `MODELO DFP` não correspondem aos valores do print enviado.

| Indicador | Planilha | Print |
| --- | ---: | ---: |
| Custos diretos | R$ 568.585,42 (E186) | R$ 341.986,00 |
| Custos indiretos | R$ 39.800,98 — 7% (E194) | R$ 17.099,30 — 5% |
| BDI | R$ 255.863,44 — 45% (E200) | R$ 170.993,00 — 50% |
| Impostos | 16,33% (C218) | 16,33% |
| Faturamento | R$ 1.032.926,79 (E223) | R$ 633.534,48 |
| Preço por m² | R$ 469,51 (E224) | R$ 287,97 |

O faturamento do print é matematicamente compatível com seus próprios componentes: `(341.986 + 17.099,30 + 170.993) / (1 - 0,1633)`. Isso não prova igualdade dos itens ou das entradas com a planilha.

A planilha utiliza 12 pessoas, 45 dias, 330 horas por empregado (220/30 × 45), adicional noturno de 15% incorporado ao salário/hora e cinco sábados de 8,8 horas com multiplicador 1,7. A célula H224, apesar do rótulo por dia/colaborador, divide o faturamento por 12, sem dividir pelos dias.

Na leitura do banco local realizada durante a conferência, o ORC-0007 possuía revisão 1 e snapshot DFP zerado. Não há dados persistidos suficientes nessa revisão para reconstruir os itens que produziram o print. Nenhum valor foi inventado ou gravado para forçar a igualdade.

## Testes e regras

`backend/tests/test_orcamento_bunge.py` transcreve os componentes identificados e confere os subtotais e o total histórico, com tolerância de centavos para diferenças de precisão. A versão histórica de cálculo foi preservada.

Novos orçamentos usam a versão 2: salário/hora = salário real / 220; horas derivadas dos dias e jornadas; dias em branco herdam identificação e escopo, enquanto zero é uma escolha explícita; adicionais associados à função e à quantidade de pessoas; custos administrativos diários; alimentação por pessoa/dia; descontos anteriores ao cálculo do faturamento. Horas extras são informadas por pessoa, separadas das horas regulares, e multiplicadas pelo salário/hora e pelo multiplicador correspondente.

A validação de igualdade com a DFP histórica não deve ser confundida com a aplicação das novas regras: elas podem produzir outro total com os mesmos salários e prazos.

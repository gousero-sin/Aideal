# Regras do Fluxo de Caixa por código de conta

## Princípios

- O código da conta gerencial é a chave canônica para classificação, agregação e
  destaque no painel. O nome da conta é destinado à exibição.
- O relatório procura primeiro a linha visual ligada ao código no template. Se o
  código ainda não existir no template, cria uma linha própria na aba `Apoio`
  usando somente o nome da conta; o código continua preservado em `Consolidado`
  e no banco.
- A base manual anual (`Saldo do Ano Anterior`) continua sendo lançada no XLSX,
  exposta pela API administrativa e somada ao saldo final. Ela não é um cartão
  individual no painel web.
- Para janeiro, a base manual anual também torna a competência gerável mesmo
  antes de haver movimentos importados para o mês. Os demais meses continuam
  exigindo movimentos salvos no banco.
- A base manual anual é aplicada apenas quando janeiro está no recorte gerado.
  De fevereiro em diante, a abertura usa o saldo final da competência anterior
  por banco.

## Fornecedores

| Código | Rubrica visual | Grupo do Fluxo |
| --- | --- | --- |
| `4.1` | `TINTAS E SOLVENTES` | Gastos com Fornecedores |
| `4.2` | `ABRASIVOS` | Gastos com Fornecedores |
| `4.3` | `OUTROS MATERIAIS DE APLICAÇÃO` | Gastos com Fornecedores |

O painel usa os mesmos códigos (`4.1`, `4.2`, `4.3`) para compor o destaque de
Fornecedores. Assim, uma troca no texto descritivo da conta não altera o cálculo.

## Transferências e saldos bancários

- Um movimento cujo tipo é `transferencia`, ou cuja classificação começa por
  `Transferência`, é rastreado como `Transferência Emitida` ou
  `Transferência Recebida`.
- Transferências ficam no `Consolidado` para auditoria e participam dos saldos
  de cada banco, mas valem zero em créditos, débitos, saldo líquido, séries,
  rankings, destaques e Apoio financeiro consolidados.
- Para cada banco e competência, o saldo inicial é o fechamento da competência
  imediatamente anterior. O cálculo não salta meses para buscar saldos antigos.
  Na primeira competência com saldo disponível, a abertura é derivada do
  primeiro saldo do extrato menos o impacto do primeiro movimento.
- O fechamento usa o último saldo informado pelo extrato; na ausência dele,
  usa o saldo calculado pelos movimentos. As linhas existentes `Saldo Inicial
  <Banco>` e `Saldo Final <Banco>` no Fluxo de Caixa são abastecidas por essa
  composição.
- A soma das linhas `Saldo Final <Banco>` concilia com a alocação bancária. Se
  houver `Saldo do Ano Anterior` manual, ele permanece como abertura não
  bancária separada; por isso, o saldo final geral é a alocação dos bancos mais
  essa base manual preservada.

## Origem bancária

O nome de arquivo é a fonte primária de banco para novos uploads no formato:

```text
movimentos_YYYY-MM_<banco>_...
```

Exemplo: `movimentos_2026-01_safra_extrato.xlsx` é classificado como `safra`.
O fallback histórico por nome de arquivo permanece ativo; registros já gravados
não são reclassificados automaticamente.

## Painel

`GET /api/fluxo_caixa/painel` expõe `saldos_por_banco` com `saldo_inicial`,
`saldo_final` e `movimentos`. A composição e o ranking bancários usam o saldo
final dessa coleção. Os cartões `Movimentos` e `Saldo ano ant.` foram removidos;
o cartão `Saldo final` mantém a soma da base manual anual com a posição líquida.

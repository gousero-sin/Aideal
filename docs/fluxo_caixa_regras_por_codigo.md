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
- Quando janeiro usa a base manual anual, o relatório não cria linhas de
  `Saldo Inicial <Banco>` derivadas do primeiro saldo dos extratos de janeiro;
  esses saldos seriam uma segunda abertura e duplicariam o total. As linhas de
  `Saldo Final <Banco>` continuam sendo geradas para rastreabilidade e para
  encadear os meses seguintes.

## Fornecedores

| Código | Rubrica visual | Grupo do Fluxo |
| --- | --- | --- |
| `4.1` | `TINTAS E SOLVENTES` | Gastos com Fornecedores |
| `4.2` | `ABRASIVOS` | Gastos com Fornecedores |
| `4.3` | `OUTROS MATERIAIS DE APLICAÇÃO` | Gastos com Fornecedores |

O painel usa os mesmos códigos (`4.1`, `4.2`, `4.3`) para compor o destaque de
Fornecedores. Assim, uma troca no texto descritivo da conta não altera o cálculo.

## Destinos especiais por código e natureza

Algumas contas precisam de um destino visual diferente do nome recebido na
origem. O mapa `saida.rotulos_template_por_codigo` aceita:

- uma string, quando créditos e débitos pertencem à mesma rubrica;
- um objeto com `credito` e `debito`, quando a natureza define a rubrica.

Regras homologadas:

| Código | Crédito | Débito |
| --- | --- | --- |
| `1.1.3` | Recebimento de Clientes | Recebimento de Clientes |
| `2.2` | Entrada por Empréstimos Bancários | Entrada por Empréstimos Bancários |
| `1.2.9` | Resgate de Aplicações | Aplicações |
| `3.12` | SERVIÇO LAUDO TECNICO | SERVIÇO LAUDO TECNICO |
| `12.3` | 13° SALARIO | 13° SALARIO |
| `12.20` | VALE TRANSPORTE | VALE TRANSPORTE |
| `14.4` | ASSISTENCIA MEDICA ADM | ASSISTENCIA MEDICA ADM |
| `18.4` | Aplicações | Aplicações |

Rubricas de entrada são calculadas como `créditos - débitos`; rubricas de saída,
como `débitos - créditos`. Dessa forma, estornos reduzem a rubrica original sem
serem omitidos do saldo final.

Antes de salvar o XLSX, a geração confere se cada movimento com código gerencial
participa exatamente uma vez do Fluxo. Código sem destino, ou com destino
duplicado para a mesma natureza, bloqueia a geração com os dados necessários
para corrigir o mapa.

## Transferências e saldos bancários

- O código canônico `2.1` identifica transferências mesmo se o nome da conta
  mudar. Tipos e rótulos legados continuam aceitos e são materializados como
  `Transferência Emitida` ou `Transferência Recebida`.
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

Arquivos que aparentam seguir o padrão de exportação, mas contêm competência
malformada ou divergente da competência selecionada, bloqueiam a ingestão. Cada
binário recebido é preservado por SHA256 antes do processamento.

O reenvio padrão substitui somente os bancos presentes no novo lote. Bancos já
salvos e não reenviados permanecem na competência. A substituição integral do
mês exige o escopo explícito `competencia`.

Após a ingestão e antes da geração, transferências são conciliadas por valor,
bancos distintos e proximidade de data. Contrapartidas ausentes geram aviso,
mas nunca alteram o saldo financeiro consolidado.

No modo `Ano todo`, Fluxo e DRE exigem sequência completa de janeiro até a
competência ativa. Lacunas bloqueiam a geração para evitar relatório parcial
com aparência de acumulado completo.

Rateios fracionários vindos do sistema de origem são preservados. Somente os
totais publicados pela API são arredondados para centavos; os movimentos não
são arredondados individualmente, pois isso poderia alterar o total do rateio.

## Painel

`GET /api/fluxo_caixa/painel` expõe `saldos_por_banco` com `saldo_inicial`,
`saldo_final` e `movimentos`. A composição e o ranking bancários usam o saldo
final dessa coleção. Os cartões `Movimentos` e `Saldo ano ant.` foram removidos;
o cartão `Saldo final` mantém a soma da base manual anual com a posição líquida.

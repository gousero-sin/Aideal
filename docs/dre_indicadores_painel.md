# Indicadores do Painel DRE

Fontes de regra:

- `Cálculo Objetivos Estratégicos - Painel (1).pdf`
- `Indicadores Viabilidade Projetos DRE (1).pdf`

## Regra central

Os indicadores do painel devem seguir a mesma forma de geração do DRE. A implementação não deve depender da leitura do arquivo `.xlsx` gerado; ela deve reutilizar a lógica e o mapeamento usados para gerar o DRE:

- resolver contas pelo número/código da conta com o mesmo `PLANO_CONTAS` do template;
- usar a mesma resolução de conta pai/conta filho da geração (`DREGeracaoCompletaService._resolver_conta_pai`);
- calcular sobre as linhas e grupos equivalentes aos exibidos no DRE gerado.

Nomes de negócio e rótulos do DRE são apenas descrição/exibição. Para DRE e Fluxo de Caixa, o cálculo deve usar o número/código da conta como chave canônica. Se o PDF citar um nome de negócio, primeiro mapear esse nome para os códigos de conta correspondentes e só então somar os valores.

## Campos manuais da ADM

A aba ADM deve permitir consultar e editar, por mês selecionado, os quatro campos abaixo:

- Contas a Pagar
- Contas a Receber
- Total de Impostos Retidos Acima da Meta
- Total de Impostos Retidos

Esses campos continuam armazenados por competência mensal. O consumo no painel segue regras diferentes por indicador:

- Impostos: usar a competência do próprio DRE analisado.
- NCG: usar a competência subsequente ao mês do DRE analisado.

Exemplo: para um DRE de `05/2026`, o IIRRL/ITMIR consome os impostos salvos em `05/2026`, enquanto o NCG consome Contas a Receber e Contas a Pagar salvos em `06/2026`.

Para períodos com mais de um mês, somar as competências correspondentes. Para NCG, somar sempre as competências subsequentes de cada mês do DRE. Dezembro avança para janeiro do ano seguinte.

## Objetivos estratégicos

### IFSRL

Fórmula:

```text
IFSRL = (Custo Total da Folha Pagamento / Receita Líquida) * 100
Meta: <= 30%
```

`Custo Total da Folha Pagamento` é composto por:

- SALÁRIO
- 13º SALÁRIO
- FÉRIAS
- MULTA RESCISÓRIAS FGTS
- ACERTO RESCISÓRIOS
- FGTS FUNCIONÁRIOS

No DRE gerado, 13º e férias entram sempre como previsão:

- `13º SALÁRIO` deve buscar o código `12.101` (`PREVISÃO 13°`)
- `FÉRIAS` deve buscar o código `12.100` (`PREVISÃO FÉRIAS`)

### IEFP

Fórmula:

```text
IEFP = Receita Líquida / Custo Total da Folha Pagamento
Meta: > 2,5
```

Usa a mesma composição de folha do IFSRL.

### IIRRL

Fórmula:

```text
IIRRL = (Total de Imposto Retido Acima da Meta / Receita Líquida) * 100
Meta: <= 10%
```

`Total de Imposto Retido Acima da Meta` vem do campo mensal editável na ADM, consumido na mesma competência do DRE analisado.

### ITMIR

Fórmula:

```text
ITMIR = Total de Imposto Retido
Meta: < 7 MM
```

`Total de Imposto Retido` vem do campo mensal editável na ADM, consumido na mesma competência do DRE analisado.

## Indicadores de viabilidade

### MCL

Fonte no DRE:

- Valor: `(=)MARGEM DE CONTRIBUIÇÃO`
- Percentual: equivalente à margem sobre Receita Líquida, conforme DRE gerado.

```text
MCL % = Margem de Contribuição / Receita Líquida * 100
```

### PEL

Fórmula:

```text
PEL = Custos Fixos / Margem de Contribuição Líquida (%)
```

Custos fixos são a soma dos grupos do DRE gerado:

- Despesa com Pessoal
- Serviço de Terceiros
- Despesas Administrativas
- Despesas com Veículos e Equipamentos
- Despesas com Locações
- Despesas com Máquinas e Equipamentos
- Despesas com Viagem e Hospedagem
- Despesas Financeiras
- Despesas com Infraestrutura

### EBITDA

Fonte no DRE:

- Valor: `(=)RESULTADO OPERACIONAL`
- Percentual: equivalente ao Resultado Operacional sobre Receita Líquida.

```text
Margem EBITDA % = Resultado Operacional / Receita Líquida * 100
```

### FCL

Fonte no DRE:

- Valor: `(=)RESULTADO GERENCIAL`
- Percentual: equivalente ao Resultado Gerencial sobre Receita Líquida.

```text
FCL % = Resultado Gerencial / Receita Líquida * 100
```

FCL deve usar a linha de Resultado Gerencial do DRE, não Resultado Líquido isolado. Quando a linha `(=)RESULTADO GERENCIAL` não estiver materializada no banco, o painel deve reproduzir a fórmula do DRE gerado:

```text
Resultado Gerencial = Resultado Líquido + (-)Investimentos
```

Essa linha `(-)Investimentos` é a linha gerencial do DRE, não o `Investimento Total` usado no ROI.

### ROI

Fórmula:

```text
ROI = Resultado Líquido / Investimento Total * 100
```

`Resultado Líquido` deve ser o mesmo valor da linha `(=)RESULTADO LÍQUIDO` do DRE gerado. Como essa linha é materializada pela geração a partir do valor líquido/saldo do período, quando ela não estiver persistida como lançamento explícito o painel deve usar o valor líquido calculado pela mesma regra da geração.

`Investimento Total` deve ser a somatória das contas equivalentes no DRE gerado. A lista abaixo descreve os grupos de negócio, mas a implementação deve buscar pelos números/códigos das contas resolvidos no `PLANO_CONTAS`, não pelo texto do nome:

- Aquisição de Máquinas e Equipamentos
- Equipamentos de Aferição
- Materiais de Consumo e Obra
- Material Elétrico
- Mangueiras e Conexões
- Ferramentas Manuais
- Despesas Administrativas
- Programas de Segurança do Trabalho
- Curso e Treinamento
- Exames Médicos
- Uniformes
- EPI´s
- Fornecedores (Total)
- Empréstimos de Terceiros
- Empréstimos Bancários

### NCG

Fórmula:

```text
NCG = Contas a Receber - Contas a Pagar
NCG % = NCG / Receita Líquida * 100
```

`Contas a Receber` e `Contas a Pagar` vêm dos campos mensais editáveis na ADM, mas devem ser consumidos da competência subsequente ao mês do DRE analisado.

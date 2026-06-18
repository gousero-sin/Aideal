# Instruções de Desenvolvimento AIDEAL

## Mapeamento financeiro por código de conta

Para DRE e Fluxo de Caixa, cálculos, indicadores, agrupamentos e regras de geração devem usar o número/código da conta como chave canônica.

- Não usar nome, descrição, rubrica textual ou rótulo visual como chave principal de cálculo.
- Nomes de contas podem ser usados apenas para exibição, logs, mensagens ao usuário ou fallback temporário explicitamente testado.
- Quando houver template/PLANO_CONTAS, resolver primeiro pelo código da conta e só então associar o rótulo exibido.
- Se uma conta necessária não tiver código confiável, corrigir o mapeamento ou a tabela de contas antes de adicionar alias por nome.
- Toda nova regra de indicador deve documentar os códigos de conta usados, além dos nomes de negócio.
- Testes de DRE e Fluxo de Caixa devem cobrir o mapeamento por código para evitar regressão por mudança de nome.

Exemplo: em vez de calcular um grupo procurando apenas por `Aquisição de Máquinas e Equipamentos`, a regra deve identificar os códigos de conta correspondentes a esse grupo e usá-los como base do cálculo.

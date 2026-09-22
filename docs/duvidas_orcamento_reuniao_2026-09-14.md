# Dúvidas em aberto do Orçamento — decisões pendentes

Origem: `Orc_Atualizacao_Reuniao_2026-09-14.md`, seção 12 (DUV-001 a DUV-023).

Este documento não repete as perguntas da reunião: para cada uma, registra **o que o código
faz hoje**, apurado na auditoria de 2026-09-16 do módulo `backend/app/orcamento/` e
`frontend/src/components/orcamento*`. A maior parte das dúvidas já tem uma resposta
implementada — o que falta é confirmá-la ou corrigi-la.

**Atualizado em 2026-09-16** com as decisões tomadas pelo Eduardo e já implementadas — ver a
seção 0. As que seguem abertas estão nas seções 2 e 3.

Cada item indica o impacto de mudar a decisão:

- **Cálculo** — alterar muda valores de orçamentos já salvos ou futuros.
- **Interface** — alteração de rótulo ou campo, sem efeito sobre números.
- **Dado** — afeta o que fica gravado no banco.

## 0. Decidido e implementado em 2026-09-16

Diretriz dada: **onde o comportamento era contraintuitivo, adotar o padrão mais intuitivo.**

| Dúvida | Decisão | O que mudou |
| --- | --- | --- |
| DUV-003 | Mobilização **somada** aos dias de execução | Confirmado; cálculo já era assim |
| DUV-005 | `Horas trabalhadas` é o **total da equipe** | Encerrada; a coluna permanece, agora rotulada "Horas trabalhadas (equipe)" |
| DUV-006 | Horas extras usam salário/hora **e** quantidade de pessoas | Confirmado; cálculo já era assim |
| DUV-007 | `Qtd. média` → **`Quantidade de pessoas`** | Rótulo trocado no perfil novo |
| DUV-001 | Em branco herda, zero é zero | Mantido, mas o campo agora **mostra o valor herdado** como sugestão |
| DUV-004 | Jornada de dia de semana passa a nascer em **8 h** | Novos orçamentos; sábado e domingo seguem em branco |
| DUV-018 | Multiplicador é o **pagamento integral** da hora | Rótulos explícitos: "1,5 = hora e meia", "2 = hora dobrada" |

Além dos rótulos, o resumo passou a **avisar** — sem bloquear o salvamento — nos três casos em
que o orçamento saía errado em silêncio:

1. dias lançados com a **jornada correspondente zerada** (a mão de obra sairia R$ 0,00);
2. horas extras lançadas com **multiplicador zerado** (as horas não eram pagas);
3. bloco **Custos Administrativos** e percentual **ADM CENTRAL** preenchidos ao mesmo tempo
   (risco de contar a estrutura administrativa duas vezes — DUV-009 / DUV-021).

O que **não** foi assumido: os valores dos multiplicadores de hora extra e as jornadas de sábado
e domingo seguem em branco. São política comercial da AIDEAL — a planilha de referência usa 1,7
no sábado, então qualquer chute aqui produziria orçamento errado sem ninguém perceber. O aviso
cobre o risco do silêncio; o valor continua sendo uma escolha de quem orça.

## 1. Decisões que já estão valendo no sistema

Estas foram implementadas. Se alguma estiver errada, os números mudam.

### DUV-001 · Quantidade de dias — automática com ajuste manual `Cálculo`

Cada função herda `Qtd. dias semana` da aba Identificação e Escopo quando o campo fica **em
branco**. Preencher a linha sobrepõe o valor só naquela função. Zero é uma escolha explícita e
não herda nada.

**Resolvido em 2026-09-16:** o campo em branco agora exibe o valor herdado como sugestão, e o
texto de ajuda explica que zero significa "não considerar". A regra continua a mesma; o que
mudou é que ela deixou de ser invisível.

### DUV-003 · Mobilização somada aos dias de execução `Cálculo`

`Dias mob.` é somado aos dias de execução e remunerado com a **jornada de dia de semana**.
Entra também no cálculo de alimentação e no denominador de `Valor dia / colaborador`.

> Se a mobilização for período separado, ou tiver jornada própria, mão de obra e alimentação mudam.

### DUV-005 · `Horas trabalhadas` é o total da equipe `Interface` — encerrada

A coluna é somente leitura e mostra `horas por pessoa × quantidade de pessoas`. Confirmada em
2026-09-16 e mantida na tabela, conforme o ORC-ATU-015; o rótulo passou a dizer
**"Horas trabalhadas (equipe)"** para não deixar dúvida.

### DUV-006 · Horas extras usam salário/hora e quantidade de pessoas `Cálculo`

```text
valor_HE = pessoas × (salário_real ÷ 220) × Σ (horas_da_categoria × multiplicador_da_categoria)
```

As horas extras são informadas **por pessoa** e multiplicadas pela equipe inteira da linha.

### DUV-010 · Ordem de incidência `Cálculo`

Dentro da mão de obra direta, nesta ordem:

1. salário = horas trabalhadas × salário/hora
2. **+** horas extras
3. **+** adicionais (percentual sobre a base escolhida, proporcional às pessoas afetadas)
4. **×** (1 + encargos sociais)
5. **×** (1 − desconto do subtópico)

Depois, sobre o conjunto:

```text
custos_diretos   = soma das seções, cada uma já com seu desconto
custos_indiretos = % sobre custos diretos, e então o desconto próprio
BDI              = % sobre custos diretos, e então o desconto próprio
custos_totais    = diretos + indiretos + BDI
faturamento      = custos_totais ÷ (1 − impostos)
```

O desconto é sempre o **último** passo de cada bloco, e o imposto é calculado por dentro.

### DUV-011 · Participação percentual sobre custos diretos `Interface`

O rodapé de cada tabela mostra `total da seção ÷ custos diretos`.

### DUV-012 e DUV-013 · Código DFP derivado, campo removido `Dado`

O código é gerado pelo sistema como `ORC-XXXX-RX` — idêntico ao identificador do orçamento e da
revisão. O campo editável "Código DFP" **saiu do formulário**, e o backend recusa qualquer
código informado manualmente. O identificador aparece uma única vez, no topo do editor.

### DUV-014 · Banco próprio, já decidido `Dado`

Decidido em 2026-08-27 e implementado: banco separado em `data/`, migrações versionadas
(`V1` a `V6`), revisões imutáveis, histórico de edição por revisão. Supera o trecho de
`Orc_Techs.md` sobre ausência de persistência interna.

### DUV-018 · Multiplicador de hora extra = pagamento total `Cálculo`

**Este é o ponto de maior risco financeiro da lista.**

As horas extras **não** estão incluídas nas horas normais: `Horas trabalhadas` vem de dias ×
jornada, e as horas extras são colunas à parte. Como a parcela de HE é somada ao salário
normal, o multiplicador tem de representar o **pagamento integral da hora** — `1,5`, `2,0`.

**Resolvido em 2026-09-16:** os rótulos passaram a dizer `(1,5 = hora e meia)` e
`(2 = hora dobrada)`, e o resumo avisa quando há horas extras lançadas com multiplicador zerado.
O valor em si continua em branco por ser política comercial.

### DUV-019 · Adicionais incidem sobre salário, e encargos sobre tudo `Cálculo`

Cada adicional escolhe a base: **Salário** ou **Salário e horas extras**. O valor é proporcional
às pessoas afetadas (`pessoas do adicional ÷ pessoas da função`). Os encargos sociais incidem
depois, sobre salário + horas extras + adicionais.

Periculosidade é um adicional configurável como qualquer outro — **não** há 30% fixo no código.

### DUV-020 · Salário por função: padrão cadastrado, cópia congelada na revisão `Dado`

O catálogo (`Cadastros do orçamento`) guarda salário por função com histórico e vigência. Ao
digitar o nome da função na tabela, o salário cadastrado é sugerido; o valor copiado fica
**congelado no snapshot da revisão**, então alterar o catálogo depois não muda orçamentos já
salvos.

### DUV-022 · Área só alimenta o indicador `Cálculo`

`Área total` é usada exclusivamente em `Preço por área = faturamento ÷ área`. Não participa da
formação do preço, e a modalidade (`HH`, `Spot`, `Rotina`, `m²`) **não altera nenhum cálculo**
— hoje ela é apenas um rótulo do cabeçalho.

> Se `m²` deve precificar por área, isso ainda não existe e é desenvolvimento novo.

### DUV-023 · Valor dia / colaborador = faturamento ÷ dias-pessoa `Cálculo`

```text
dias_pessoa = Σ (dias semana + mobilização + sábados + domingos) × pessoas
```

Sobre toda a mão de obra direta. A DFP do print usa denominador **1.620**
(`633.534,48 ÷ 391,07`), que não corresponde às 12 pessoas × 45 dias da planilha de origem —
ver a seção 3.

## 2. Decisões ainda não aplicadas

### DUV-007 · Renomeado para `Quantidade de pessoas` `Interface` — encerrada

Aplicado em 2026-09-16 no perfil de cálculo novo. As revisões históricas mantêm o rótulo antigo,
junto com o resto do seu snapshot.

### DUV-002 · Mobilização ficou como prazo em texto livre `Interface`

Os campos são **"Prazo para Mobilização"** e **"Prazo para Desmobilização"**, ambos texto livre.
Como são texto, não entram em cálculo nenhum — quem alimenta os dias de mobilização é a coluna
`Dias mob.` de cada função, independente desses campos.

> Se a decisão for **Data** de mobilização, o campo muda de tipo e passa a exigir validação.

### DUV-004 · Jornada de semana nasce em 8 h; sábado e domingo em branco `Cálculo`

Aplicado em 2026-09-16. `Horas por dia de semana` passa a nascer em **8 h** nos orçamentos novos
— orçamentos já salvos não mudam. Sábado e domingo continuam em branco porque variam por
contrato.

O risco de a mão de obra sair R$ 0,00 em silêncio foi coberto pelo aviso no resumo, que aparece
sempre que houver dias lançados numa categoria cuja jornada esteja zerada.

> Ainda em aberto, se a AIDEAL quiser: definir as jornadas padrão de sábado e domingo.

### DUV-008 · `Saldo de Mão de Obra` removido da tela, mantido no dado `Dado`

Saiu do formulário e não entra em nenhum cálculo da versão 2, mas a coluna continua no banco e é
herdada entre revisões.

> Decidir: remover de vez (migração) ou manter dormente para não perder o histórico.

### DUV-017 · Alíquotas digitadas por orçamento, sem vínculo com regime `Cálculo` `Dado`

Com a remoção de `Regime Tributário`, as sete alíquotas (IRPJ, ISS, CSLL, PIS, INSS, COFINS,
ICMS) são digitadas manualmente em cada orçamento por quem tem a permissão `orcamento.edit`.
Não existe tabela de alíquotas por regime nem valor padrão. A coluna `regime_tributario`
continua no banco, dormente.

> Pendente: as alíquotas devem vir de um cadastro central com vigência — como já acontece com o
> salário por função — ou seguem manuais por orçamento?

## 3. Dúvidas que ainda não têm resposta

### DUV-009 e DUV-021 · Custos Administrativos e Custos Indiretos coexistem `Cálculo`

Esta é a ambiguidade mais provável de gerar erro de precificação, e vale tratá-la junto.

O que o sistema faz hoje:

| Bloco | Onde entra | Como é calculado |
| --- | --- | --- |
| **Custos Administrativos** | custos **diretos** | `valor diário × dias × % considerado × multiplicador` |
| **Custos Indiretos** | sobre os custos diretos | percentuais de `ADM CENTRAL`, `TAXA COMERCIAL`, `PARTICIPAÇÃO`, `TAXA DE ANTECIPAÇÃO` |

Ou seja: **Custos Administrativos substituiu a Mão de Obra Indireta** (a tabela saiu da tela e o
total ocupa aquele lugar no resumo), mas **não substituiu os Custos Indiretos**, que seguem
existindo como grupo de percentuais. Os 5% do print correspondem a esse segundo grupo.

**Mitigado em 2026-09-16, não resolvido:** o resumo agora avisa quando os dois estão
preenchidos ao mesmo tempo. O aviso não decide nada — apenas impede que a dupla contagem passe
despercebida.

> Continua pendente de decisão: qual dos dois blocos carrega a estrutura administrativa. Enquanto
> não for decidido, cabe a quem orça escolher um e zerar o outro.

### DUV-015 · Anotações `0` e `Alterar` `—`

Sem correspondência possível no código. Só quem estava na reunião pode recuperar o contexto.

### DUV-016 · Métricas do resumo mantidas integralmente `Interface`

A tela mostra as oito métricas do print, nenhuma removida ou renomeada: Custos diretos, Custos
indiretos, Lucro / BDI, Custos totais, Impostos (%), Preço por área, Valor dia / colaborador e
Preço total de faturamento.

> Confirmar se todas permanecem — em especial `Valor dia / colaborador`, cujo critério de cálculo
> ainda não fecha com a DFP de referência.

## 4. Pendência que bloqueia a homologação

**ORC-ATU-051 — a reconciliação do ORC-0007 com a DFP não fechou.** Conforme
`docs/reconciliacao_dfp_0075.md`, há três fontes que não batem entre si:

| Indicador | Planilha `DFP 0075-26` | Print da reunião |
| --- | ---: | ---: |
| Custos diretos | R$ 568.585,42 | R$ 341.986,00 |
| Custos indiretos | R$ 39.800,98 (7%) | R$ 17.099,30 (5%) |
| BDI | R$ 255.863,44 (45%) | R$ 170.993,00 (50%) |
| Faturamento | R$ 1.032.926,79 | R$ 633.534,48 |
| Preço por m² | R$ 469,51 | R$ 287,97 |

Os números do print são internamente consistentes e o sistema os reproduz a partir das próprias
entradas do print. O que não existe é o **conjunto de itens** que gerou aqueles R$ 341.986,00: a
revisão do ORC-0007 no banco estava com snapshot zerado, e a planilha descreve outro cenário
(12 pessoas, 45 dias, 330 horas/empregado, noturno de 15% embutido no salário/hora, cinco
sábados de 8,8 h com multiplicador 1,7).

> Para fechar a homologação é preciso a **memória de cálculo item a item** do orçamento que
> produziu o print — não só os totais. Sem ela, qualquer igualdade seria forçada.

## 5. Ordem sugerida para decidir

1. **ORC-ATU-051** — obter a memória de cálculo do 0007; é o que bloqueia a homologação.
2. **DUV-009 / DUV-021** — decidir qual bloco carrega a estrutura administrativa.
3. **DUV-017** — as alíquotas vêm de cadastro central com vigência ou seguem manuais?
4. **DUV-004** (resto) — jornadas padrão de sábado e domingo, se houver.
5. **DUV-002**, **DUV-008**, **DUV-016** — formato da mobilização e limpeza de dado dormente.
6. **DUV-023** — confirmar o denominador de `Valor dia / colaborador`.
7. **DUV-015** — recuperar o contexto perdido.

As decisões que mudarem regra de cálculo devem virar uma nova `calculation_version`: as revisões
já salvas guardam a versão que as gerou e não podem ser recalculadas retroativamente.

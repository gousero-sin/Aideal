# Auditoria do Fluxo de Caixa e DRE 2026

Data da auditoria: 16/07/2026.

## Conclusão executiva

Os erros de classificação e as fragilidades permanentes do software foram
corrigidos. Os arquivos atuais de janeiro a junho foram reproduzidos em banco
isolado e o sistema passou a calcular cada movimento não-transferência uma única
vez, compensar estornos e manter transferências neutras.

Os saldos atuais ainda não alcançam integralmente os valores homologados porque
existem diferenças reais nos arquivos exportados pelo sistema de origem. Essas
diferenças não devem ser inventadas no banco da AIDEAL. O gestor precisa
corrigi-las ou confirmá-las no sistema de origem e gerar novos arquivos.

Nenhum dos cinco movimentos ausentes foi inserido artificialmente e nenhum dos
dois débitos de R$ 8.700,00 de junho foi apagado. O banco de produção contém
atualmente saldo inicial de R$ 397.877,00, mas o valor homologado informado é
R$ 396.934,78. A diferença de R$ 942,22 deve ser corrigida manualmente pelo
gestor; a auditoria não alterou esse indicador.

## Integridade dos arquivos persistidos

- Foram comparados 21 arquivos em `/Users/gousero/Downloads/FLUXO DE CAIXA/`.
- Os 21 hashes SHA256 coincidem com os hashes registrados em `fluxo_uploads`.
- As contagens também coincidem: 5.397 movimentos, sem linha rejeitada.
- Portanto, o banco atual representa exatamente as exportações atuais.
- A lista completa está em
  `docs/evidencias_fluxo_caixa_2026/hashes_fontes_2026-07-16.csv`.

Essa evidência exclui perda de linhas pelo parser na carga atual. Ela também
mostra que os movimentos financeiros ausentes já não estavam nos arquivos
recebidos.

## Saldos reproduzidos com as exportações atuais

A tabela abaixo usa R$ 396.934,78 apenas como abertura da reprodução isolada.
Esse valor não ficou gravado automaticamente no banco de produção.

| Mês | Variação não-transferência | Saldo acumulado atual | Valor informado | Desvio |
| --- | ---: | ---: | ---: | ---: |
| Janeiro | R$ 24.166,04 | R$ 421.100,82 | R$ 421.100,82 | R$ 0,00 |
| Fevereiro | R$ 204.350,95 | R$ 625.451,77 | R$ 625.451,78 | -R$ 0,01 |
| Março | R$ 1.282.219,47 | R$ 1.907.671,24 | R$ 957.671,28 | R$ 949.999,96 |
| Abril | -R$ 596.615,50 | R$ 1.311.055,74 | R$ 1.061.055,76 | R$ 249.999,98 |
| Maio | -R$ 1.408.064,68 | -R$ 97.008,94 | -R$ 97.009,90 | R$ 0,96 |
| Junho | R$ 466.604,96 | R$ 369.596,03 | R$ 378.296,08 | -R$ 8.700,05 |

Os valores informados originalmente foram marcados como aproximados. Por isso,
diferenças residuais de centavos não foram tratadas como lançamentos ausentes.

## Curva de março a maio: causa no sistema de origem

Um workbook histórico contém cinco movimentos da conta `1.2.9` que não existem
em nenhuma exportação atual nem no banco atual:

| Data | Natureza | Valor | Histórico | Efeito no mês |
| --- | --- | ---: | --- | ---: |
| 30/03/2026 | Débito | R$ 1.000.000,00 | APLICACAO FDO - CLIENTE | -R$ 1.000.000,00 |
| 31/03/2026 | Crédito | R$ 50.000,00 | APLICAÇÃO FINANCEIRA - RESGATE | R$ 50.000,00 |
| 09/04/2026 | Crédito | R$ 200.000,00 | APLICAÇÃO FINANCEIRA - RESGATE | R$ 200.000,00 |
| 16/04/2026 | Crédito | R$ 500.000,00 | ADIAN RESG | R$ 500.000,00 |
| 12/05/2026 | Crédito | R$ 250.000,00 | APLICACAO FINANCEIRA CEF | R$ 250.000,00 |

Efeito líquido:

- março: -R$ 950.000,00;
- abril: +R$ 700.000,00;
- maio: +R$ 250.000,00;
- acumulado até maio: R$ 0,00.

Isso explica por que março e abril ficam muito fora da curva, mas maio volta a
ficar próximo do saldo homologado. A causa imediata é humana/processual ou do
sistema exportador: os lançamentos históricos deixaram de constar na fonte
atual. O parser não pode recriá-los.

Há transferências de R$ 1.000.000,00 em 30/03 e R$ 500.000,00 em 16/04, mas
elas formam pares entre bancos e são movimentos distintos das aplicações e
resgates históricos. Não houve substituição lógica desses movimentos por
transferências.

## Transferências entre bancos

Foram encontrados 76 registros de transferência:

| Mês | Registros | Pares conciliados | Sem contrapartida | Diferença recebidas - emitidas |
| --- | ---: | ---: | ---: | ---: |
| Janeiro | 16 | 8 | 0 | R$ 0,00 |
| Fevereiro | 10 | 5 | 0 | R$ 0,00 |
| Março | 16 | 8 | 0 | R$ 0,00 |
| Abril | 8 | 4 | 0 | R$ 0,00 |
| Maio | 14 | 7 | 0 | R$ 0,00 |
| Junho | 12 | 6 | 0 | R$ 0,00 |

As oito pontas anteriormente sinalizadas em janeiro eram quatro pares reais.
Nos XLSX de origem, o banco emissor usa `Tipo = Transferência` e o receptor usa
`Tipo = Crédito`, com mesmo dia e valor. Quando a descrição estava vazia, a
versão anterior do parser interpretava incorretamente `Transferência` como
entrada e persistia ambos os lados como recebidos.

A correção usa três evidências, nesta ordem:

1. descrição `BANCO ORIGEM X BANCO DESTINO`, quando disponível;
2. variação do saldo da conta no arquivo;
3. contrapartida única de mesmo dia e valor em outro banco.

Depois da correção, os 76 registros formam 38 pares, as emitidas e recebidas
somam igualmente R$ 7.011.331,81 e a diferença é zero. Transferências continuam
neutras no saldo consolidado.

## Junho: lançamento que exige decisão humana

As exportações atuais contêm dois débitos Itaú de R$ 8.700,00 na conta `7.2`:

- 03/06/2026: `LOCAÇÃO COMPRESSOR REF. 05/05 A 03/06/26`;
- 11/06/2026: `LOCAÇÃO COMPRESSOR REF. 04/06 A 03/07/26`.

Os períodos são consecutivos e as linhas não são duplicatas literais. A
diferença do saldo homologado de junho é compatível, aproximadamente, com um
desses pagamentos. O software não possui evidência para excluir nenhum deles.
O gestor deve conferir contrato, nota e pagamento no sistema de origem.

## DRE de junho

O banco possui uploads DRE completos de janeiro a maio. Não existe upload DRE
de junho nem arquivo-fonte `DRE MES 06 - 2026` na pasta analisada. Arquivos
gerados com nome de junho não substituem o arquivo bruto de origem.

A geração `Ano todo` agora bloqueia a DRE de junho e informa a lacuna, evitando
um acumulado janeiro-maio apresentado como se fosse janeiro-junho.

## Causas de software corrigidas

1. **Mapeamento incorreto por código**
   - `1.1.3` agora vai para `Recebimento de Clientes`;
   - `2.2` agora vai para `Entrada por Empréstimos Bancários`;
   - `1.2.9` usa crédito em `Resgate de Aplicações` e débito em `Aplicações`;
   - `3.12`, `14.4` e `18.4` receberam destinos canônicos;
   - nomes alterados não mudam o resultado quando o código permanece igual.

2. **Estornos desapareciam da rubrica**
   - entradas usam créditos menos débitos;
   - saídas usam débitos menos créditos;
   - créditos em contas normalmente de saída reduzem a despesa.

3. **Reenvio parcial apagava bancos não reenviados**
   - a interface sempre enviava `replace=true`;
   - o repositório apagava toda a competência antes de inserir apenas o lote;
   - agora o escopo padrão substitui somente os bancos reenviados;
   - a substituição integral exige `replace_scope=competencia`.

4. **Caixa era gravada como banco desconhecido**
   - `caixa` e variações agora são normalizadas para `cef`;
   - a direção da transferência usa também código e natureza do movimento.
   - uploads já persistidos como `desconhecido` são normalizados em memória pelo
     nome do arquivo durante a geração, sem reescrever valores ou saldos;
   - `Tipo = Transferência` sem descrição agora é tratado como saída, conforme o
     padrão observado nas 21 exportações de origem;
   - registros legados recuperam a direção pela variação do saldo e pela
     contrapartida única de mesmo dia e valor;
   - o reenvio reconhece o alias no nome antigo, remove a versão legada e evita
     duplicar movimentos ao migrar para `cef`.

5. **Arquivos de competência errada eram aceitos**
   - nomes divergentes agora bloqueiam a carga;
   - nomes aparentemente padronizados, mas malformados, também bloqueiam;
   - cada arquivo é arquivado por SHA256 antes do processamento.

6. **Relatório parcial podia parecer acumulado completo**
   - Fluxo e DRE em `Ano todo` exigem todos os meses de janeiro até o mês ativo.

7. **Conta nova podia desaparecer silenciosamente**
   - movimento com código sem destino financeiro único bloqueia o XLSX;
   - a mensagem lista código, nome, natureza, valor, destino e participações.

8. **Totais públicos podiam exibir resíduos além de centavos**
   - rateios internos permanecem intactos;
   - somente totais publicados são arredondados para duas casas.

## Problemas de processo/origem que permanecem para o gestor

1. Corrigir ou confirmar no sistema de origem os cinco movimentos de aplicação
   e resgate listados acima.
2. Conferir os dois pagamentos de R$ 8.700,00 de junho.
3. Corrigir manualmente o saldo inicial de 2026 de R$ 397.877,00 para o valor
   homologado de R$ 396.934,78.
4. Reexportar/renomear corretamente:
   - março Caixa: `movimentos_2026-03_caixa_.xlsx`;
   - junho Caixa: `movimentos_2026-06_caixa_.xlsx`;
   - junho Mercantil: `movimentos_2026-06_mercantil_.xlsx`.
5. Exportar e carregar o DRE bruto de junho.
6. Reingerir somente os bancos e meses corrigidos e regenerar `Ano todo`.

## Verificação técnica

- Reprodução isolada dos 21 arquivos: 5.397 movimentos inseridos.
- Saldo final com a fonte atual e abertura simulada: R$ 369.596,03.
- Transferências na geração pelo banco atual: 38 pares e nenhuma não pareada.
- Testes específicos de Fluxo e auditoria: 57 aprovados.
- Frontend: 8 testes aprovados e build de produção concluído.
- Lint e verificação de whitespace: aprovados.
- Suíte backend completa: 320 testes aprovados, 1 teste esperado como `xfail`
  e 2 falhas antigas fora do escopo desta correção:
  - preservação byte a byte de `sheet5.xml` no processamento DRE;
  - composição do investimento no indicador ROI do painel DRE.
- O ambiente não possui `coverage`/`pytest-cov`; não foi possível medir o
  percentual de cobertura sem alterar dependências.

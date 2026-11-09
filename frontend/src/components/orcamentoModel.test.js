import test from 'node:test';
import assert from 'node:assert/strict';

import {
  CAMPOS_CABECALHO,
  CAMPOS_REVISAO,
  MODALIDADES,
  SITUACOES,
  applyHeaderChange,
  applyDfpChange,
  nextDfpItemLabel,
  buildOrcamentoPayload,
  buildRevisaoPatchPayload,
  computeDfpSummary,
  computeLaborRow,
  collectOrcamentoWarnings,
  computeSectionTotal,
  computeTableRowSubtotal,
  createDfpItemId,
  inheritedLaborDays,
  removeDfpCollectionItem,
  stripDerivedIdentity,
  createEmptyOrcamentoForm,
  createRevisaoForm,
  getDfpSectionStatePath,
  getNestedValue,
  herdarCabecalho,
  normalizeOrcamentos,
  resolveOrcamentoCapabilities,
  resumoCarteira,
  transicoesDisponiveis,
  updateDfpCollectionItemAtPath,
  updateDfpField,
  validateCatalogoDraft,
  validateDfpV2,
  validateOrcamentoForm,
  validateRevisaoForm,
} from './orcamentoModel.js';

test('deriva capacidades de orçamento sem confundir leitura com escrita', () => {
  assert.deepEqual(resolveOrcamentoCapabilities(['orcamento.view']), {
    canEdit: false,
    canTransition: false,
  });
  assert.deepEqual(resolveOrcamentoCapabilities([
    'orcamento.view', 'orcamento.edit', 'orcamento.transition',
  ]), {
    canEdit: true,
    canTransition: true,
  });
});

const formValido = () => ({ ...createEmptyOrcamentoForm(), contratante: 'AMBEV' });

test('novos itens recebem nomes distintos para não impedir salvamento ao adicionar várias linhas', () => {
  assert.equal(nextDfpItemLabel([]), 'Novo item');
  assert.equal(nextDfpItemLabel([{ label: ' novo ITEM ' }, { label: 'Novo item 2' }]), 'Novo item 3');
});

test('seleção geográfica mantém a região do cabeçalho sincronizada com cidade e estado', () => {
  const dfp = { metadata: { municipio: 'Campinas', uf: 'SP' } };
  const empty = { regiao: '', dfp: { metadata: {} } };
  const selected = applyDfpChange(empty, dfp);
  assert.equal(selected.regiao, 'Campinas / SP');
  assert.equal(applyDfpChange(selected, { metadata: { municipio: '', uf: 'RJ' } }).regiao, '');
  assert.equal(applyDfpChange({ ...selected, regiao: 'CANTEIRO — CAMPINAS/SP' }, { metadata: { municipio: 'Niterói', uf: 'RJ' } }).regiao, 'Niterói / RJ');
  assert.equal(empty.regiao, '');
});

test('remoção de função limpa somente seus adicionais sem mutar o orçamento', () => {
  const dfp = { mao_de_obra_direta: { items: [{ id: 'a' }, { id: 'b' }],
    adjustments: [{ id: 'x', labor_item_id: 'a' }, { id: 'y', labor_item_id: 'b' }] } };
  const next = removeDfpCollectionItem(dfp, 'mao_de_obra_direta.items', 'a');
  assert.deepEqual(next.mao_de_obra_direta.items, [{ id: 'b' }]);
  assert.deepEqual(next.mao_de_obra_direta.adjustments, [{ id: 'y', labor_item_id: 'b' }]);
  assert.equal(dfp.mao_de_obra_direta.adjustments.length, 2);
});

test('subtotais legados mostram mão de obra e móveis sem aplicar descontos v2', () => {
  const item = { quantity: 2, hours_per_employee: 10, salary_real: 2200, salary_base_hours: 220, manual_total: 50 };
  const dfp = { calculation_version: 1, mao_de_obra_direta: { items: [item], discount_percent: 50 },
    veiculos_hospedagem: { lodging_assets: [{ quantity: 3, unit_cost: 25 }] } };
  assert.equal(computeTableRowSubtotal(dfp, 'mao_de_obra_direta.items', item), 250);
  assert.equal(computeSectionTotal(dfp, 'mao_de_obra_direta'), 250);
  assert.equal(computeSectionTotal(dfp, 'veiculos_hospedagem.lodging_assets'), 75);
});

test('cálculo v2 mantém paridade com cenário de encargos e adicionais do backend', () => {
  const dfp = {
    calculation_version: 2,
    metadata: { quantidade_dias_semana: 10, quantidade_sabado: 2, quantidade_domingo: 1,
      horas_semana: 8, horas_sabado: 4, horas_domingo: 4, semana_fator: 1.5 },
    mao_de_obra_direta: { items: [{ id: 'pintor', quantity: 2, salary_real: 2200,
      worked_days: 10, saturday_days: 0, sunday_days: 0, mobilization_days: 1,
      overtime_week_hours: 2 }], adjustments: [{ labor_item_id: 'pintor', quantity: 1,
      percent: 30, base: 'salary' }], social_charges_percent: 50, discount_percent: 10 },
    custos_administrativos: { daily_cost: 100, days: 10, considered_percent: 50,
      multiplier: 2, discount_percent: 10 },
  };
  // Instruções DFP: (220/30) × (10 dias + 1 mob) × 2 pessoas.
  assert.ok(Math.abs(computeLaborRow(dfp.mao_de_obra_direta.items[0], dfp).worked_hours - 484 / 3) < 1e-9);
  assert.equal(computeSectionTotal(dfp, 'mao_de_obra_direta'), 2585.7);
  assert.equal(computeSectionTotal(dfp, 'custos_administrativos'), 900);
  assert.equal(computeDfpSummary(dfp).precoTotalFaturamento, 3485.7);
});

test('só a contratante bloqueia a criação; o cabeçalho é completado depois', () => {
  assert.deepEqual(validateOrcamentoForm(createEmptyOrcamentoForm()), {
    contratante: 'Informe a contratante.',
  });
  assert.deepEqual(validateOrcamentoForm(formValido()), {});
});

test('recusa modalidade fora da lista e prazo inválido sem reintroduzir saldo legado', () => {
  assert.deepEqual(validateOrcamentoForm({
    ...formValido(),
    modalidade: 'Empreitada',
    prazoExecucaoDias: '0',
    saldoMaoDeObra: '-5',
  }), {
    modalidade: `A modalidade deve ser ${MODALIDADES.join(' ou ')}.`,
    prazoExecucaoDias: 'O prazo deve ser um número inteiro de dias maior que zero.',
  });
});

test('data de início exige uma data real ou N/A', () => {
  assert.equal(validateOrcamentoForm({ ...formValido(), dataInicio: '2026-02-31' }).dataInicio,
    'Informe uma data válida ou N/A.');
  assert.deepEqual(validateOrcamentoForm({ ...formValido(), dataInicio: '2026-02-28' }), {});
  assert.deepEqual(validateOrcamentoForm({ ...formValido(), dataInicio: 'N/A' }), {});
});

test('prazo do cabeçalho não decide automaticamente a quantidade de dias do DFP', () => {
  const original = { prazoExecucaoDias: '5', dfp: { metadata: { quantidade_dias_semana: 7, prazo_execucao_text: '5' } } };
  const changed = applyHeaderChange(original, 'prazoExecucaoDias', '10');
  assert.equal(changed.dfp.metadata.quantidade_dias_semana, 7);
  assert.equal(changed.dfp.metadata.prazo_execucao_text, '10');
});

test('o código nunca é enviado: quem gera a sequência é o backend', () => {
  const payload = buildOrcamentoPayload({ ...formValido(), codigo: 'TENTATIVA' });
  assert.ok(!('codigo' in payload));
});

test('payload cobre o cabeçalho canônico e descarta textos em branco', () => {
  const payload = buildOrcamentoPayload({
    ...formValido(),
    contratante: ' AMBEV ',
    dadosContratante: 'AMBEV S.A.',
    escopo: '   ',
    modalidade: 'Spot',
    regiao: 'Anapolis/GO',
    prazoExecucaoDias: '10',
    saldoMaoDeObra: '4',
    regimeTributario: 'Presumido',
  });

  assert.equal(payload.contratante, 'AMBEV');
  assert.equal(payload.escopo, null);
  assert.equal(payload.prazo_execucao_dias, 10);
  assert.ok(!('saldo_mao_de_obra' in payload));
  assert.ok(!('regime_tributario' in payload));
});

test('payload não é criado enquanto o formulário for inválido', () => {
  assert.equal(buildOrcamentoPayload({ contratante: '  ' }), null);
});

test('o cabeçalho canônico cobre todos os campos exigidos pelo documento', () => {
  const campos = CAMPOS_CABECALHO.map(({ field }) => field);
  for (const obrigatorio of [
    'contratante', 'dadosContratante', 'escopo', 'modalidade',
    'prazoExecucaoDias', 'dataInicio', 'regiao',
  ]) {
    assert.ok(campos.includes(obrigatorio), `falta ${obrigatorio}`);
  }
});

test('atualização oferece modalidades e remove campos do cabeçalho', () => {
  assert.deepEqual(MODALIDADES, ['HH', 'Spot', 'Rotina', 'm²']);
  const fields = CAMPOS_CABECALHO.map(({ field }) => field);
  assert.ok(!fields.includes('saldoMaoDeObra'));
  assert.ok(!fields.includes('regimeTributario'));
});

test('ciclo de vida segue Rascunho -> Em revisão -> Pronto -> Emitido -> Inativo', () => {
  assert.deepEqual(transicoesDisponiveis('rascunho'), ['em_revisao', 'inativo']);
  assert.deepEqual(transicoesDisponiveis('em_revisao'), ['rascunho', 'pronto_para_proposta', 'inativo']);
  assert.deepEqual(transicoesDisponiveis('pronto_para_proposta'), ['em_revisao', 'emitido', 'inativo']);
  assert.deepEqual(transicoesDisponiveis('emitido'), ['inativo']);
});

test('revisão inativa não oferece nenhuma transição de volta', () => {
  assert.deepEqual(transicoesDisponiveis('inativo'), []);
  assert.deepEqual(transicoesDisponiveis('desconhecida'), []);
});

test('rótulos não usam os estados da proposta técnica', () => {
  assert.equal(SITUACOES.rascunho, 'Rascunho');
  assert.equal(SITUACOES.em_revisao, 'Em revisão');
  assert.equal(SITUACOES.emitido, 'Emitido');
  assert.ok(!('em_elaboracao' in SITUACOES));
  assert.ok(!('pronta_para_emissao' in SITUACOES));
});

test('normaliza orçamentos, revisões e pendências do cabeçalho', () => {
  const [orcamento] = normalizeOrcamentos({
    orcamentos: [{
      id: 'o1',
      sequencial: 1,
      codigo: 'ORC-0001',
      contratante: 'AMBEV',
      revisao_atual: {
        id: 'r2', numero: 2, situacao: 'emitido', vencida: false, valido_ate: '2026-09-26',
      },
      revisoes: [
        { id: 'r1', numero: 1, situacao: 'rascunho', escopo: 'Original' },
        { id: 'r2', numero: 2, situacao: 'emitido' },
      ],
      cabecalho_pendente: ['Região da Obra'],
    }],
  });

  assert.equal(orcamento.codigo, 'ORC-0001');
  assert.equal(orcamento.sequencial, 1);
  assert.equal(orcamento.revisaoAtual.situacaoLabel, 'Emitido');
  assert.equal(orcamento.revisaoAtual.validoAte, '2026-09-26');
  assert.equal(orcamento.revisoes.length, 2);
  assert.deepEqual(orcamento.cabecalhoPendente, ['Região da Obra']);
});

test('descarta registros sem id e aceita lista direta', () => {
  assert.deepEqual(normalizeOrcamentos([{ codigo: 'sem id' }]), []);
  assert.equal(normalizeOrcamentos(null).length, 0);
});

test('resumo agrupa a carteira por estágio do ciclo', () => {
  const resumo = resumoCarteira([
    { revisaoAtual: { situacao: 'rascunho' } },
    { revisaoAtual: { situacao: 'em_revisao' } },
    { revisaoAtual: { situacao: 'pronto_para_proposta' } },
    { revisaoAtual: { situacao: 'emitido' } },
    { revisaoAtual: { situacao: 'inativo' } },
  ]);

  assert.deepEqual(resumo, {
    total: 5,
    emAndamento: 2,
    prontos: 1,
    emitidos: 1,
    totalFaturamento: 0,
  });
});

test('nova revisão herda somente o cabeçalho vigente da atualização', () => {
  const herdado = herdarCabecalho({
    escopo: 'Hidrojateamento',
    modalidade: 'Spot',
    regiao: 'Anápolis/GO',
    prazoExecucaoDias: 10,
    dadosContratante: 'AMBEV S.A.',
    mobilizacao: 'Equipe mobilizada',
    desmobilizacao: '2 dias',
    areaUnidadeBase: '858 m²',
    dfp: {},
  });

  // Perder qualquer um destes reabriria uma pendência já resolvida na revisão anterior.
  assert.deepEqual(herdado, {
    escopo: 'Hidrojateamento',
    modalidade: 'Spot',
    regiao: 'Anápolis/GO',
    prazo_execucao_dias: 10,
    dados_contratante: 'AMBEV S.A.',
    mobilizacao: 'Equipe mobilizada',
    desmobilizacao: '2 dias',
    area_unidade_base: '858 m²',
    dfp: {},
  });
});

test('herança de revisão vazia não inventa valores escalares', () => {
  const { dfp, ...cabecalho } = herdarCabecalho(null);
  assert.deepEqual(Object.values(cabecalho).filter(Boolean), []);
  assert.deepEqual(dfp, {});
});

test('campos editáveis da revisão reutilizam o cabeçalho canônico sem a contratante', () => {
  assert.deepEqual(
    CAMPOS_REVISAO.map(({ field }) => field),
    CAMPOS_CABECALHO.map(({ field }) => field).filter((field) => field !== 'contratante'),
  );
});

test('formulário de edição nasce dos valores da revisão sem mutá-la', () => {
  const revisao = Object.freeze({
    escopo: 'Hidrojateamento',
    modalidade: 'Spot',
    regiao: 'Anápolis/GO',
    prazoExecucaoDias: 10,
    saldoMaoDeObra: 0,
    dadosContratante: 'AMBEV S.A.',
    mobilizacao: null,
    desmobilizacao: '2 dias',
    areaUnidadeBase: '858 m²',
    regimeTributario: 'Presumido',
    dfp: {},
  });

  const form = createRevisaoForm(revisao);

  assert.deepEqual(form, {
    dadosContratante: 'AMBEV S.A.',
    escopo: 'Hidrojateamento',
    modalidade: 'Spot',
    prazoExecucaoDias: 10,
    regiao: 'Anápolis/GO',
    mobilizacao: '',
    desmobilizacao: '2 dias',
    areaUnidadeBase: '858 m²',
    dataInicio: '',
    dfp: {},
  });
  assert.equal(revisao.mobilizacao, null);
});

test('formulário de edição prioriza cidade e estado persistidos sobre região legada', () => {
  const form = createRevisaoForm({
    regiao: 'CENTRO-OESTE — ANÁPOLIS/GO',
    dfp: { metadata: { municipio: 'Goiânia', uf: 'GO' } },
  });

  assert.equal(form.regiao, 'Goiânia / GO');
});

test('edição permite salvar rascunho com cabeçalho incompleto', () => {
  const errors = validateRevisaoForm(createRevisaoForm(null));

  assert.deepEqual(errors, {});
  assert.notEqual(buildRevisaoPatchPayload(createRevisaoForm(null)), null);
});

test('PATCH usa nomes canônicos do backend, normaliza valores e não envia metadados', () => {
  const form = {
    ...createRevisaoForm(null),
    contratante: 'não pertence à revisão',
    situacao: 'emitido',
    escopo: '  Hidrojateamento  ',
    modalidade: 'HH',
    regiao: '  Anápolis/GO ',
    prazoExecucaoDias: '10',
    saldoMaoDeObra: '0',
    dadosContratante: ' AMBEV S.A. ',
    mobilizacao: ' ',
    desmobilizacao: ' 2 dias ',
    areaUnidadeBase: ' 858 m² ',
    regimeTributario: ' Presumido ',
  };

  assert.deepEqual(buildRevisaoPatchPayload(form), {
    dados_contratante: 'AMBEV S.A.',
    escopo: 'Hidrojateamento',
    modalidade: 'HH',
    prazo_execucao_dias: 10,
    regiao: 'Anápolis/GO',
    mobilizacao: null,
    desmobilizacao: '2 dias',
    area_unidade_base: '858 m²',
    dfp: { metadata: { data_inicio: null, data_inicio_na: false } },
  });
});

test('validação v2 recusa contagens fracionárias e percentuais fora do contrato', () => {
  const dfp = {
    calculation_version: 2,
    metadata: { quantidade_dias_semana: 2.5, quantidade_sabado: 0, quantidade_domingo: 0 },
    mao_de_obra_direta: {
      items: [{ id: 'pintor', label: 'Pintor', quantity: 1.5, worked_days: null,
        saturday_days: null, sunday_days: null, mobilization_days: 0, salary_real: 2200 }],
      adjustments: [{ id: 'periculosidade', label: 'Periculosidade', labor_item_id: 'pintor', quantity: 2, percent: 100 }],
      social_charges_percent: 100,
    },
    custos_administrativos: { days: 1.5, considered_percent: 101, discount_percent: 101 },
    custos_indiretos: { items: [{ label: 'ADM CENTRAL', aliquot_percent: 100 }] },
    impostos: { items: [{ label: 'ISS', aliquot_percent: 60 }, { label: 'PIS', aliquot_percent: 40 }] },
    bdi: { factor_percent: 100, discount_percent: 101 },
  };
  const errors = validateDfpV2(dfp);
  assert.ok(errors.some((message) => message.includes('quantidades de dias')));
  assert.ok(errors.some((message) => message.includes('pessoas e dias')));
  assert.ok(errors.some((message) => message.includes('quantidade de dias dos custos administrativos')));
  assert.ok(errors.some((message) => message.includes('soma das alíquotas de impostos')));
  assert.ok(errors.some((message) => message.includes('Fator BDI')));
  assert.ok(errors.some((message) => message.includes('excede a função selecionada')));
});

test('validação v2 aceita salário/hora derivado de salário real por 220', () => {
  const dfp = {
    calculation_version: 2,
    metadata: { quantidade_dias_semana: 1, quantidade_sabado: 0, quantidade_domingo: 0,
      horas_semana: 8, horas_sabado: 0, horas_domingo: 0, semana_fator: 0, sabado_fator: 0, domingo_fator: 0 },
    mao_de_obra_direta: { items: [{ id: 'p', label: 'Pintor', quantity: 1, salary_real: 2200,
      worked_days: 1, saturday_days: 0, sunday_days: 0, mobilization_days: 0,
      overtime_week_hours: 0, overtime_saturday_hours: 0, overtime_sunday_hours: 0 }], adjustments: [], social_charges_percent: 0 },
    custos_administrativos: { days: 0, considered_percent: 100, discount_percent: 0 },
    custos_indiretos: { items: [] }, impostos: { items: [] }, bdi: { factor_percent: 0 },
  };
  assert.deepEqual(validateDfpV2(dfp), []);
  assert.equal(computeLaborRow(dfp.mao_de_obra_direta.items[0], dfp).hourly_rate, 10);
});

test('catálogo rejeita nomes vazios, duplicados e valores negativos antes da API', () => {
  const errors = validateCatalogoDraft({
    custo_administrativo_diario: 10,
    funcoes: [{ nome: 'Pintor', salario_real: 2200 }, { nome: ' pintor ', salario_real: 2300 }],
    itens: [{ nome: '', valor_unitario: -1 }],
  });
  assert.ok(errors.some((message) => message.includes('Não repita')));
  assert.ok(errors.some((message) => message.includes('Informe o nome do item')));
  assert.ok(errors.some((message) => message.includes('número finito e não negativo')));
});

test('formulários clonam o snapshot DFP para que a edição não altere o histórico', () => {
  const dfp = { metadata: { codigo_dfp: 'DFP 001' } };
  const revisao = { dfp };
  const form = createRevisaoForm(revisao);

  form.dfp.metadata.codigo_dfp = 'DFP 002';

  assert.equal(dfp.metadata.codigo_dfp, 'DFP 001');
  assert.equal(buildRevisaoPatchPayload({
    ...form,
    dadosContratante: 'Cliente',
    escopo: 'Escopo',
    modalidade: 'HH',
    prazoExecucaoDias: 1,
    saldoMaoDeObra: 0,
    regiao: 'GO',
  }).dfp.metadata.codigo_dfp, 'DFP 002');
});

test('resolve o caminho de estado inclusive para subseção de hospedagem', () => {
  assert.equal(getDfpSectionStatePath({ id: 'equipamentos' }), 'equipamentos');
  assert.equal(getDfpSectionStatePath({
    id: 'lodging_assets',
    state_key: 'veiculos_hospedagem.lodging_assets',
  }), 'veiculos_hospedagem.lodging_assets');
});

test('atualiza campos e linhas aninhadas sem mutar o snapshot anterior', () => {
  const original = {
    metadata: { area_total: 10 },
    veiculos_hospedagem: {
      lodging_assets: [{ id: 'cama', quantity: 1, unit_cost: 2 }],
    },
  };

  const withArea = updateDfpField(original, 'metadata', 'area_total', '858');
  const withBed = updateDfpCollectionItemAtPath(
    withArea,
    'veiculos_hospedagem.lodging_assets',
    'cama',
    'quantity',
    '4',
  );

  assert.equal(getNestedValue(original, 'metadata.area_total'), 10);
  assert.equal(getNestedValue(withArea, 'metadata.area_total'), '858');
  assert.equal(getNestedValue(withBed, 'veiculos_hospedagem.lodging_assets.0.quantity'), '4');
  assert.equal(original.veiculos_hospedagem.lodging_assets[0].quantity, 1);
});

test('calcula o resumo DFP ao vivo com mão de obra, BDI, indiretos e impostos', () => {
  const summary = computeDfpSummary({
    metadata: { area_total: 10, quantidade_dias_semana: 5 },
    mao_de_obra_direta: {
      items: [{ quantity: 2, hours_per_employee: 10, salary_real: 2200, salary_base_hours: 220, hourly_rate: 0, manual_total: 0, worked_days: 0 }],
      adjustments: [{ percent: 10 }],
      social_charges_percent: 50,
    },
    mao_de_obra_indireta: { items: [], adjustments: [], social_charges_percent: 0 },
    veiculos_hospedagem: { items: [{ quantity: 1, unit_cost: 100 }], lodging_assets: [] },
    alimentacao: { items: [] },
    equipamentos: { items: [] },
    epis_epcs: { items: [] },
    materiais_consumo: { items: [] },
    ferramental: { items: [] },
    outros_custos_diretos: { items: [] },
    custos_indiretos: { items: [{ aliquot_percent: 5 }] },
    bdi: { factor_percent: 20 },
    impostos: { items: [{ aliquot_percent: 10 }] },
  });

  assert.deepEqual(summary, {
    custosDiretosTotal: 430,
    custosIndiretosTotal: 21.5,
    lucroTotal: 86,
    custosTotais: 537.5,
    aliquotaImpostosTotal: 10,
    precoTotalFaturamento: 597.22,
    precoPorArea: 59.72,
    valorDiaColaborador: 59.72,
  });
});

test('custo administrativo vazio usa os mesmos padrões do backend', () => {
  // O backend trata campo ausente/vazio como multiplicador 1 e 100% considerado.
  // Divergir disso mostrava R$ 0 no preview e gravava outro valor.
  const dfp = {
    calculation_version: 2,
    metadata: {},
    mao_de_obra_direta: { items: [], adjustments: [], social_charges_percent: 0 },
    custos_administrativos: { daily_cost: 200, days: 24, considered_percent: 80, multiplier: 1.1 },
  };
  assert.equal(computeSectionTotal(dfp, 'custos_administrativos'), 4224);

  const semMultiplicador = { ...dfp, custos_administrativos: { ...dfp.custos_administrativos, multiplier: '' } };
  assert.equal(computeSectionTotal(semMultiplicador, 'custos_administrativos'), 3840);

  const semPercentual = { ...dfp, custos_administrativos: { ...dfp.custos_administrativos, considered_percent: '' } };
  assert.equal(computeSectionTotal(semPercentual, 'custos_administrativos'), 5280);

  const semAmbos = {
    ...dfp,
    custos_administrativos: { ...dfp.custos_administrativos, multiplier: '', considered_percent: '' },
  };
  assert.equal(computeSectionTotal(semAmbos, 'custos_administrativos'), 4800);

  const zerado = { ...dfp, custos_administrativos: { ...dfp.custos_administrativos, multiplier: 0 } };
  assert.equal(computeSectionTotal(zerado, 'custos_administrativos'), 0);
});

test('reaproveitar orçamento descarta o código DFP do orçamento de origem', () => {
  const origem = { metadata: { codigo_dfp: 'ORC-0007-R2', cliente_unidade: 'Cliente', area_total: 2200 } };
  const copia = stripDerivedIdentity(origem);

  assert.equal(copia.metadata.codigo_dfp, '');
  assert.equal(copia.metadata.cliente_unidade, 'Cliente');
  assert.equal(copia.metadata.area_total, 2200);
  assert.equal(origem.metadata.codigo_dfp, 'ORC-0007-R2');
});

test('gera id de item mesmo sem randomUUID, como em http na rede local', () => {
  const original = Object.getOwnPropertyDescriptor(globalThis, 'crypto');
  const substituir = (value) => Object.defineProperty(globalThis, 'crypto', {
    configurable: true, writable: true, value,
  });
  try {
    substituir({ getRandomValues: (array) => array.fill(7) });
    assert.equal(createDfpItemId(), '07'.repeat(16));

    substituir(undefined);
    const fallback = createDfpItemId();
    assert.equal(typeof fallback, 'string');
    assert.ok(fallback.length > 0);
    assert.notEqual(fallback, createDfpItemId());
  } finally {
    Object.defineProperty(globalThis, 'crypto', original);
  }
});

const dfpV2 = (patch = {}) => ({
  calculation_version: 2,
  metadata: {
    quantidade_dias_semana: 20, quantidade_sabado: 0, quantidade_domingo: 0,
    horas_semana: 8, horas_sabado: 0, horas_domingo: 0,
    semana_fator: 1.5, sabado_fator: 0, domingo_fator: 0,
    ...(patch.metadata || {}),
  },
  mao_de_obra_direta: {
    items: [{ id: 'pintor', label: 'Pintor', quantity: 5, salary_real: 2200 }],
    adjustments: [], social_charges_percent: 0,
    ...(patch.mao_de_obra_direta || {}),
  },
  custos_administrativos: { daily_cost: 0, days: 0, ...(patch.custos_administrativos || {}) },
  custos_indiretos: { items: [], ...(patch.custos_indiretos || {}) },
});

test('campo de dias em branco informa o valor herdado da identificação', () => {
  const dfp = dfpV2();
  assert.equal(inheritedLaborDays(dfp, 'worked_days'), 20);
  assert.equal(inheritedLaborDays(dfp, 'saturday_days'), 0);
  assert.equal(inheritedLaborDays(dfp, 'quantity'), null);
});

test('horas seguem (220/30) × diárias, sem depender da jornada diária', () => {
  // Exemplo das instruções: 20 dias de execução + 20 de mobilização = 293,33 h.
  const dfp = { calculation_version: 2, metadata: { horas_semana: 0, horas_sabado: 0, horas_domingo: 0 } };
  const item = { quantity: 1, salary_real: 2200, worked_days: 20, saturday_days: 0, sunday_days: 0, mobilization_days: 20 };
  const row = computeLaborRow(item, dfp);
  assert.equal(Math.round(row.worked_hours * 100) / 100, 293.33);
  assert.ok(Math.abs(row.total - 2933.3333333) < 1e-6);
  // Fim de semana vale a mesma diária e jornada zerada não gera aviso.
  const fimDeSemana = computeLaborRow({ ...item, worked_days: 10, saturday_days: 5, sunday_days: 5 }, dfp);
  assert.equal(Math.round(fimDeSemana.worked_hours * 100) / 100, 293.33);
  assert.deepEqual(collectOrcamentoWarnings(dfpV2({ metadata: { horas_semana: 0 } })), []);
});

test('avisa quando horas extras são lançadas com multiplicador zerado', () => {
  const dfp = dfpV2({
    metadata: { sabado_fator: 0 },
    mao_de_obra_direta: {
      items: [{ id: 'pintor', label: 'Pintor', quantity: 5, salary_real: 2200,
        overtime_saturday_hours: 8 }],
      adjustments: [], social_charges_percent: 0,
    },
  });
  const avisos = collectOrcamentoWarnings(dfp);
  assert.equal(avisos.some((aviso) => /não estão sendo pagas/.test(aviso)), true);
});

test('avisa sobre estrutura administrativa contada por dois caminhos', () => {
  const dfp = dfpV2({
    custos_administrativos: { daily_cost: 200, days: 20 },
    custos_indiretos: { items: [{ id: 'adm_central', label: 'ADM CENTRAL', aliquot_percent: 5 }] },
  });
  assert.equal(collectOrcamentoWarnings(dfp).some((a) => /duas vezes/.test(a)), true);

  // Um indireto que não é administrativo não dispara o aviso.
  const comercial = dfpV2({
    custos_administrativos: { daily_cost: 200, days: 20 },
    custos_indiretos: { items: [{ id: 'taxa', label: 'TAXA COMERCIAL', aliquot_percent: 5 }] },
  });
  assert.deepEqual(collectOrcamentoWarnings(comercial), []);
});

test('revisões da versão anterior não recebem avisos das regras novas', () => {
  assert.deepEqual(collectOrcamentoWarnings({ calculation_version: 1, metadata: {} }), []);
});

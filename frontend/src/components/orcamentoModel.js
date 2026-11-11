import { validateHh } from './orcamento/hhModel.js';

const deepClone = (value) => {
  if (value === null || value === undefined) return value;
  return JSON.parse(JSON.stringify(value));
};

// crypto.randomUUID só existe em secure context; o app roda em http://goflowaideal (sem HTTPS) na rede.
export const createDfpItemId = () => {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  if (typeof crypto !== 'undefined' && typeof crypto.getRandomValues === 'function') {
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    return [...bytes].map((byte) => byte.toString(16).padStart(2, '0')).join('');
  }
  return `item_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`;
};

// O código DFP é derivado do orçamento no backend: copiá-lo entre orçamentos é rejeitado.
export const stripDerivedIdentity = (dfp) => {
  const snapshot = deepClone(dfp || {});
  if (snapshot.metadata) snapshot.metadata = { ...snapshot.metadata, codigo_dfp: '' };
  return snapshot;
};

export const SITUACOES = Object.freeze({
  rascunho: 'Rascunho',
  em_revisao: 'Em revisão',
  pronto_para_proposta: 'Pronto para proposta',
  emitido: 'Emitido',
  inativo: 'Inativo',
});

const TRANSICOES = Object.freeze({
  rascunho: Object.freeze(['em_revisao', 'inativo']),
  em_revisao: Object.freeze(['rascunho', 'pronto_para_proposta', 'inativo']),
  pronto_para_proposta: Object.freeze(['em_revisao', 'emitido', 'inativo']),
  emitido: Object.freeze(['inativo']),
  inativo: Object.freeze([]),
});

export const MODALIDADES = Object.freeze(['HH', 'Spot', 'Rotina', 'm²']);
const MAX_DFP_NUMERIC_VALUE = 10_000_000_000_000;

export const CAMPOS_CABECALHO = Object.freeze([
  Object.freeze({ field: 'contratante', label: 'Contratante', required: true }),
  Object.freeze({ field: 'dadosContratante', label: 'Dados da Contratante', required: true, long: true }),
  Object.freeze({ field: 'escopo', label: 'Escopo do Serviço', required: true, long: true }),
  Object.freeze({ field: 'modalidade', label: 'Modalidade do Trabalho', required: true, options: MODALIDADES }),
  Object.freeze({ field: 'prazoExecucaoDias', label: 'Prazo de execução (dias)', required: true, type: 'number' }),
  Object.freeze({ field: 'dataInicio', label: 'Data de início (ou N/A)' }),
  Object.freeze({ field: 'regiao', label: 'Região da Obra', required: true }),
  Object.freeze({ field: 'mobilizacao', label: 'Prazo para Mobilização' }),
  Object.freeze({ field: 'desmobilizacao', label: 'Prazo para Desmobilização' }),
  Object.freeze({ field: 'areaUnidadeBase', label: 'Área / unidade-base' }),
]);

export const CAMPOS_REVISAO = Object.freeze(
  CAMPOS_CABECALHO.filter(({ field }) => field !== 'contratante'),
);

export const transicoesDisponiveis = (situacao) => [...(TRANSICOES[situacao] || [])];

export const resolveOrcamentoCapabilities = (permissions) => {
  const granted = new Set(Array.isArray(permissions) ? permissions : []);
  return {
    canEdit: granted.has('orcamento.view') && granted.has('orcamento.edit'),
    canTransition: granted.has('orcamento.view') && granted.has('orcamento.transition'),
  };
};

export const createEmptyOrcamentoForm = (schema = null) => ({
  ...Object.fromEntries(CAMPOS_CABECALHO.map(({ field }) => [field, ''])),
  dfp: deepClone(schema?.defaults || {}),
});

const locationLabel = (metadata) => metadata?.municipio && metadata?.uf
  ? `${metadata.municipio} / ${metadata.uf}` : '';

export const createRevisaoForm = (revisao, schema = null) => {
  const dfp = deepClone(revisao?.dfp || schema?.defaults || {});
  const regionFromLocation = locationLabel(dfp?.metadata);
  return {
    ...Object.fromEntries(
      CAMPOS_REVISAO.map(({ field }) => [field, revisao?.[field] ?? '']),
    ),
    dfp,
    regiao: regionFromLocation || revisao?.regiao || '',
    dataInicio: revisao?.dfp?.metadata?.data_inicio_na ? 'N/A' : (revisao?.dfp?.metadata?.data_inicio || ''),
  };
};

export const syncHeaderDfp = (form) => ({
  ...deepClone(form.dfp || {}),
  metadata: {
    ...deepClone(form.dfp?.metadata || {}),
    data_inicio: form.dataInicio === 'N/A' ? null : (form.dataInicio || null),
    data_inicio_na: form.dataInicio === 'N/A',
  },
});

export const applyHeaderChange = (form, field, value) => {
  const mapping = { contratante: 'cliente_unidade', escopo: 'descricao_projeto',
    mobilizacao: 'mobilizacao_text', desmobilizacao: 'desmobilizacao_text', prazoExecucaoDias: 'prazo_execucao_text' };
  const metadata = { ...form.dfp?.metadata };
  const key = mapping[field];
  if (key && (!metadata[key] || String(metadata[key]) === String(form[field] || ''))) metadata[key] = value;
  if (field === 'regiao') {
    const match = String(value).match(/^(?:.*?—\s*)?(.+?)\s*\/\s*([A-Za-z]{2})$/);
    if (match) { metadata.municipio = match[1].trim(); metadata.uf = match[2].toUpperCase(); }
  }
  return { ...form, [field]: value, dfp: { ...form.dfp, metadata } };
};

export const applyDfpChange = (form, dfp) => {
  const previous = locationLabel(form.dfp?.metadata);
  const current = locationLabel(dfp?.metadata);
  const previousLocation = form.dfp?.metadata || {};
  const currentLocation = dfp?.metadata || {};
  const locationChanged = previousLocation.municipio !== currentLocation.municipio
    || previousLocation.uf !== currentLocation.uf;
  const region = current || locationChanged || previous ? current : form.regiao;
  return { ...form, dfp, regiao: region };
};

const parsePositiveInt = (value) => {
  if (value === '' || value === null || value === undefined) return null;
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : NaN;
};

const optionalText = (value) => {
  const limpo = typeof value === 'string' ? value.trim() : '';
  return limpo || null;
};

const isValidIsoDate = (value) => {
  const match = String(value || '').match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return false;
  const [, year, month, day] = match.map(Number);
  const parsed = new Date(Date.UTC(year, month - 1, day));
  return parsed.getUTCFullYear() === year
    && parsed.getUTCMonth() === month - 1
    && parsed.getUTCDate() === day;
};

const isBlankNumeric = (value) => value === '' || value === null || value === undefined;
const isStrictNonNegativeNumber = (value) => isBlankNumeric(value) || (
  typeof value === 'number'
  && Number.isFinite(value)
  && value >= 0
  && value <= MAX_DFP_NUMERIC_VALUE
);
const isNaturalCount = (value) => isBlankNumeric(value) || (
  isStrictNonNegativeNumber(value) && Number.isInteger(value)
);

const DFP_NUMERIC_KEYS = new Set([
  'area_total', 'sabado_fator', 'domingo_fator', 'semana_fator',
  'quantidade_sabado', 'quantidade_domingo', 'quantidade_dias_semana',
  'horas_sabado', 'horas_domingo', 'horas_semana', 'quantity', 'unit_cost',
  'worked_hours', 'worked_days', 'saturday_days', 'sunday_days', 'mobilization_days',
  'months', 'salary_real', 'salary_base_hours', 'hourly_rate', 'manual_total',
  'overtime_week_hours', 'overtime_saturday_hours', 'overtime_sunday_hours',
  'percent', 'social_charges_percent', 'aliquot_percent', 'factor_percent',
  'discount_percent', 'daily_cost', 'days', 'considered_percent', 'multiplier',
]);

const walkDfpNumbers = (value, path = '', invalid = []) => {
  if (!value || typeof value !== 'object') return invalid;
  Object.entries(value).forEach(([key, current]) => {
    const currentPath = path ? `${path}.${key}` : key;
    if (DFP_NUMERIC_KEYS.has(key) && !isStrictNonNegativeNumber(current)) invalid.push(currentPath);
    if (current && typeof current === 'object') walkDfpNumbers(current, currentPath, invalid);
  });
  return invalid;
};

export const validateDfpV2 = (dfp) => {
  if (dfp?.calculation_version !== 2) return [];
  const errors = [];
  const invalidNumbers = walkDfpNumbers(dfp);
  if (invalidNumbers.length) {
    errors.push(`Há valor numérico inválido em ${invalidNumbers[0]}. Use somente números finitos e não negativos.`);
  }

  const metadata = dfp.metadata || {};
  for (const key of ['quantidade_dias_semana', 'quantidade_sabado', 'quantidade_domingo']) {
    if (!isNaturalCount(metadata[key])) errors.push('As quantidades de dias da identificação devem ser números inteiros não negativos.');
  }

  const rows = Array.isArray(dfp.mao_de_obra_direta?.items) ? dfp.mao_de_obra_direta.items : [];
  rows.forEach((row) => {
    for (const key of ['quantity', 'worked_days', 'saturday_days', 'sunday_days', 'mobilization_days']) {
      if (!isNaturalCount(row?.[key])) {
        errors.push(`Na função “${row?.label || 'sem nome'}”, pessoas e dias devem ser números inteiros não negativos.`);
        break;
      }
    }
  });

  const adjustments = Array.isArray(dfp.mao_de_obra_direta?.adjustments)
    ? dfp.mao_de_obra_direta.adjustments : [];
  const rowsById = new Map(rows.map((row) => [row.id, row]));
  adjustments.forEach((adjustment) => {
    if (!isNaturalCount(adjustment?.quantity)) {
      errors.push(`No adicional “${adjustment?.label || 'sem nome'}”, a quantidade de pessoas deve ser inteira e não negativa.`);
    }
    if (!isBlankNumeric(adjustment?.percent) && Number(adjustment.percent) >= 100) {
      errors.push(`O percentual do adicional “${adjustment?.label || 'sem nome'}” deve ser menor que 100%.`);
    }
    if (Number(adjustment?.quantity || 0) > 0) {
      const target = rowsById.get(adjustment?.labor_item_id);
      if (!target || Number(adjustment.quantity) > Number(target.quantity || 0)) {
        errors.push(`A quantidade do adicional “${adjustment?.label || 'sem nome'}” excede a função selecionada.`);
      }
    }
  });

  const admin = dfp.custos_administrativos || {};
  if (!isNaturalCount(admin.days)) errors.push('A quantidade de dias dos custos administrativos deve ser inteira e não negativa.');
  if (Number(admin.considered_percent || 0) > 100) errors.push('O percentual considerado dos custos administrativos deve estar entre 0% e 100%.');

  const discounts = [
    ['Mão de Obra Direta', dfp.mao_de_obra_direta?.discount_percent],
    ['Custos Administrativos', admin.discount_percent],
    ['Veículos e Hospedagem', dfp.veiculos_hospedagem?.discount_percent],
    ['Alimentação', dfp.alimentacao?.discount_percent],
    ['Equipamentos', dfp.equipamentos?.discount_percent],
    ['EPI / EPC', dfp.epis_epcs?.discount_percent],
    ['Materiais de Consumo', dfp.materiais_consumo?.discount_percent],
    ['Ferramental', dfp.ferramental?.discount_percent],
    ['Outros Custos Diretos', dfp.outros_custos_diretos?.discount_percent],
    ['Custos indiretos', dfp.custos_indiretos?.discount_percent],
    ['BDI', dfp.bdi?.discount_percent],
  ];
  discounts.forEach(([label, value]) => {
    if (Number(value || 0) > 100) errors.push(`O desconto de ${label} deve estar entre 0% e 100%.`);
  });

  const strictPercentages = [
    ['Encargos sociais', dfp.mao_de_obra_direta?.social_charges_percent],
    ['Fator BDI', dfp.bdi?.factor_percent],
    ...(dfp.custos_indiretos?.items || []).map((item) => [`Custos indiretos · ${item.label}`, item.aliquot_percent]),
    ...(dfp.impostos?.items || []).map((item) => [`Impostos · ${item.label}`, item.aliquot_percent]),
  ];
  strictPercentages.forEach(([label, value]) => {
    if (!isBlankNumeric(value) && Number(value) >= 100) errors.push(`${label} deve ser menor que 100%.`);
  });
  const totalTaxes = (dfp.impostos?.items || []).reduce((sum, item) => sum + Number(item?.aliquot_percent || 0), 0);
  if (totalTaxes >= 100) errors.push('A soma das alíquotas de impostos deve ser menor que 100%.');

  return [...new Set(errors)];
};

export const validateCatalogoDraft = (catalogo) => {
  const errors = [];
  if (!isStrictNonNegativeNumber(catalogo?.custo_administrativo_diario)) {
    errors.push('O custo administrativo padrão deve ser um número finito e não negativo.');
  }
  for (const [group, label, valueKey] of [
    ['funcoes', 'função', 'salario_real'],
    ['itens', 'item', 'valor_unitario'],
  ]) {
    const entries = Array.isArray(catalogo?.[group]) ? catalogo[group] : [];
    const names = new Set();
    entries.forEach((entry, index) => {
      const name = typeof entry?.nome === 'string' ? entry.nome.trim() : '';
      if (!name) errors.push(`Informe o nome do ${label} ${index + 1}.`);
      const normalized = name.toLocaleLowerCase('pt-BR');
      if (normalized && names.has(normalized)) errors.push(`Não repita o nome “${name}” no catálogo de ${group}.`);
      names.add(normalized);
      if (!isStrictNonNegativeNumber(entry?.[valueKey])) {
        errors.push(`O valor de “${name || `${label} ${index + 1}`}” deve ser um número finito e não negativo.`);
      }
    });
  }
  return [...new Set(errors)];
};

export const validateOrcamentoForm = (form) => {
  const errors = {};

  if (!form?.contratante?.trim()) errors.contratante = 'Informe a contratante.';
  if (form?.modalidade && !MODALIDADES.includes(form.modalidade)) {
    errors.modalidade = `A modalidade deve ser ${MODALIDADES.join(' ou ')}.`;
  }
  if (Number.isNaN(parsePositiveInt(form?.prazoExecucaoDias))) {
    errors.prazoExecucaoDias = 'O prazo deve ser um número inteiro de dias maior que zero.';
  }
  if (form?.dataInicio && form.dataInicio !== 'N/A' && !isValidIsoDate(form.dataInicio)) {
    errors.dataInicio = 'Informe uma data válida ou N/A.';
  }

  return errors;
};

export const validateRevisaoForm = (form) => {
  const errors = {};

  if (form?.modalidade && !MODALIDADES.includes(form.modalidade)) {
    errors.modalidade = `A modalidade deve ser ${MODALIDADES.join(' ou ')}.`;
  }
  if (form?.prazoExecucaoDias !== '' && Number.isNaN(parsePositiveInt(form?.prazoExecucaoDias))) {
    errors.prazoExecucaoDias = 'O prazo deve ser um número inteiro de dias maior que zero.';
  }
  if (form?.dataInicio && form.dataInicio !== 'N/A' && !isValidIsoDate(form.dataInicio)) {
    errors.dataInicio = 'Informe uma data válida ou N/A.';
  }
  // O bloco HH segue salvo mesmo fora da modalidade HH e o backend sempre o valida.
  const dfpErrors = [...validateHh(form?.dfp?.hh), ...validateDfpV2(form?.dfp)];
  if (dfpErrors.length) errors.dfp = dfpErrors[0];

  return errors;
};

export const buildOrcamentoPayload = (form, { hhDefaults } = {}) => {
  if (Object.keys(validateOrcamentoForm(form)).length > 0) return null;
  const dfp = syncHeaderDfp(form);
  // Orçamento criado já em HH nasce com o modelo padrão de composição, senão o card mostraria
  // R$ 0,00 até a primeira edição.
  if (form.modalidade === 'HH' && !dfp.hh && hhDefaults) dfp.hh = deepClone(hhDefaults);
  return {
    contratante: form.contratante.trim(),
    dados_contratante: optionalText(form.dadosContratante),
    escopo: optionalText(form.escopo),
    modalidade: optionalText(form.modalidade),
    regiao: optionalText(form.regiao),
    prazo_execucao_dias: parsePositiveInt(form.prazoExecucaoDias),
    mobilizacao: optionalText(form.mobilizacao),
    desmobilizacao: optionalText(form.desmobilizacao),
    area_unidade_base: optionalText(form.areaUnidadeBase),
    dfp,
    motivo: null,
  };
};

export const buildRevisaoPatchPayload = (form) => {
  if (Object.keys(validateRevisaoForm(form)).length > 0) return null;
  return {
    dados_contratante: optionalText(form.dadosContratante),
    escopo: optionalText(form.escopo),
    modalidade: optionalText(form.modalidade),
    prazo_execucao_dias: parsePositiveInt(form.prazoExecucaoDias),
    regiao: optionalText(form.regiao),
    mobilizacao: optionalText(form.mobilizacao),
    desmobilizacao: optionalText(form.desmobilizacao),
    area_unidade_base: optionalText(form.areaUnidadeBase),
    dfp: syncHeaderDfp(form),
  };
};

const normalizeDfpSummary = (summary) => ({
  custosDiretosTotal: Number(summary?.custos_diretos_total) || 0,
  custosIndiretosTotal: Number(summary?.custos_indiretos_total) || 0,
  lucroTotal: Number(summary?.lucro_total) || 0,
  precoTotalFaturamento: Number(summary?.preco_total_faturamento) || 0,
  precoPorArea: Number(summary?.preco_por_area) || 0,
  valorDiaColaborador: Number(summary?.valor_dia_colaborador) || 0,
});

export function normalizeRevisao(revisao) {
  const situacao = String(revisao?.situacao || '');
  return {
    id: String(revisao?.id || ''),
    numero: Number(revisao?.numero) || 0,
    situacao,
    situacaoLabel: SITUACOES[situacao] || situacao,
    escopo: String(revisao?.escopo || ''),
    modalidade: revisao?.modalidade || null,
    regiao: revisao?.regiao || null,
    prazoExecucaoDias: revisao?.prazo_execucao_dias ?? null,
    saldoMaoDeObra: revisao?.saldo_mao_de_obra ?? null,
    dadosContratante: revisao?.dados_contratante || null,
    mobilizacao: revisao?.mobilizacao || null,
    desmobilizacao: revisao?.desmobilizacao || null,
    areaUnidadeBase: revisao?.area_unidade_base || null,
    regimeTributario: revisao?.regime_tributario || null,
    dfp: deepClone(revisao?.dfp || {}),
    emitidoEm: revisao?.emitido_em || null,
    validoAte: revisao?.valido_ate || null,
    vencida: revisao?.vencida === true,
    createdAt: revisao?.created_at || null,
  };
}

export const normalizeOrcamentos = (payload) => {
  const registros = Array.isArray(payload) ? payload : (payload?.orcamentos || []);
  return (Array.isArray(registros) ? registros : [])
    .filter((item) => item?.id)
    .map((item) => ({
      id: String(item.id),
      sequencial: Number(item.sequencial) || 0,
      codigo: String(item.codigo || ''),
      contratante: String(item.contratante || ''),
      revisaoAtual: item.revisao_atual ? normalizeRevisao(item.revisao_atual) : null,
      revisoes: (Array.isArray(item.revisoes) ? item.revisoes : []).map(normalizeRevisao),
      cabecalhoPendente: Array.isArray(item.cabecalho_pendente) ? [...item.cabecalho_pendente] : [],
      dfpSummary: normalizeDfpSummary(item.dfp_summary),
      createdAt: item.created_at || null,
    }));
};

export const herdarCabecalho = (revisao) => ({
  escopo: revisao?.escopo || null,
  modalidade: revisao?.modalidade || null,
  regiao: revisao?.regiao || null,
  prazo_execucao_dias: revisao?.prazoExecucaoDias ?? null,
  dados_contratante: revisao?.dadosContratante || null,
  mobilizacao: revisao?.mobilizacao || null,
  desmobilizacao: revisao?.desmobilizacao || null,
  area_unidade_base: revisao?.areaUnidadeBase || null,
  dfp: deepClone(revisao?.dfp || {}),
});

export const resumoCarteira = (orcamentos) => {
  const lista = Array.isArray(orcamentos) ? orcamentos : [];
  const contar = (situacao) => lista.filter((item) => item.revisaoAtual?.situacao === situacao).length;
  const totalFaturamento = lista.reduce(
    (acc, item) => acc + (Number(item?.dfpSummary?.precoTotalFaturamento) || 0),
    0,
  );
  return {
    total: lista.length,
    emAndamento: contar('rascunho') + contar('em_revisao'),
    prontos: contar('pronto_para_proposta'),
    emitidos: contar('emitido'),
    totalFaturamento,
  };
};

export const getSchemaSections = (schema) => (
  Array.isArray(schema?.sections) ? schema.sections : []
);

export const getDfpSectionStatePath = (section) => (
  String(section?.state_key || section?.id || '')
);

export const getNestedValue = (object, path) => String(path || '')
  .split('.')
  .filter(Boolean)
  .reduce((current, key) => (current && typeof current === 'object' ? current[key] : undefined), object);

export const setNestedValue = (object, path, value) => {
  const segments = String(path || '').split('.').filter(Boolean);
  if (segments.length === 0) return object;
  const root = deepClone(object || {});
  let current = root;
  for (let index = 0; index < segments.length - 1; index += 1) {
    const segment = segments[index];
    const next = current[segment];
    current[segment] = next && typeof next === 'object' ? deepClone(next) : {};
    current = current[segment];
  }
  current[segments.at(-1)] = value;
  return root;
};

export const updateDfpField = (dfp, sectionPath, field, value) => (
  setNestedValue(dfp, `${sectionPath}.${field}`, value)
);

export const updateDfpCollectionItemAtPath = (dfp, collectionPath, itemId, field, value) => {
  const collection = getNestedValue(dfp, collectionPath);
  if (!Array.isArray(collection)) return deepClone(dfp || {});
  return setNestedValue(
    dfp,
    collectionPath,
    collection.map((item) => (item?.id === itemId ? { ...item, [field]: value } : item)),
  );
};

export const updateDfpCollectionItem = (dfp, sectionKey, itemId, field, value, nestedKey = 'items') => {
  const next = deepClone(dfp || {});
  const section = next?.[sectionKey];
  if (!section || !Array.isArray(section[nestedKey])) return next;
  section[nestedKey] = section[nestedKey].map((item) => (
    item.id === itemId ? { ...item, [field]: value } : item
  ));
  return next;
};

export const updateDfpAdjustmentItem = (dfp, sectionKey, itemId, value) => (
  updateDfpCollectionItem(dfp, sectionKey, itemId, 'percent', value, 'adjustments')
);

export const removeDfpCollectionItem = (dfp, collectionPath, itemId) => {
  const items = getNestedValue(dfp, collectionPath);
  if (!Array.isArray(items)) return deepClone(dfp);
  const next = setNestedValue(dfp, collectionPath, items.filter((item) => item.id !== itemId));
  if (collectionPath !== 'mao_de_obra_direta.items') return next;
  return setNestedValue(next, 'mao_de_obra_direta.adjustments',
    (dfp.mao_de_obra_direta?.adjustments || []).filter((item) => item.labor_item_id !== itemId));
};

export const nextDfpItemLabel = (items = []) => {
  const names = new Set(items.map((item) => String(item.label || '').trim().toLocaleLowerCase('pt-BR')));
  let label = 'Novo item';
  for (let suffix = 2; names.has(label.toLocaleLowerCase('pt-BR')); suffix += 1) label = `Novo item ${suffix}`;
  return label;
};

const numberOrZero = (value) => {
  const numeric = Number(value);
  return Number.isFinite(numeric) && numeric >= 0 ? numeric : 0;
};

const numberOrBlankDefault = (value, fallback) => (
  value === '' || value === null || value === undefined ? fallback : numberOrZero(value)
);

const roundCurrency = (value) => Math.round((value + Number.EPSILON) * 100) / 100;

const HORAS_MES = 220;
const DIAS_MES = 30;

export const computeLaborRow = (item, dfp) => {
  const m = dfp?.metadata || {};
  const inherited = (value, fallback) => numberOrZero(value == null || value === '' ? fallback : value);
  const days = inherited(item.worked_days, m.quantidade_dias_semana);
  const saturday = inherited(item.saturday_days, m.quantidade_sabado);
  const sunday = inherited(item.sunday_days, m.quantidade_domingo);
  const allDays = days + saturday + sunday + numberOrZero(item.mobilization_days);
  // Instruções da DFP: horas = (220/30) × (dias de execução + mobilização).
  const hours = allDays * HORAS_MES / DIAS_MES;
  const hourly = numberOrZero(item.salary_real) / HORAS_MES;
  const base = allDays * numberOrZero(item.quantity) * numberOrZero(item.salary_real) / DIAS_MES;
  const extra = numberOrZero(item.quantity) * hourly * (
    numberOrZero(item.overtime_week_hours) * numberOrZero(m.semana_fator)
    + numberOrZero(item.overtime_saturday_hours) * numberOrZero(m.sabado_fator)
    + numberOrZero(item.overtime_sunday_hours) * numberOrZero(m.domingo_fator));
  return { ...item, hourly_rate: hourly, worked_hours: hours * numberOrZero(item.quantity),
    total: base + extra, base, extra, allDays };
};

// Dias em branco herdam a premissa geral; zero é uma escolha explícita. A tela precisa
// mostrar de onde vem o valor, senão o campo vazio não diz nada ao usuário.
export const INHERITED_LABOR_DAYS = Object.freeze({
  worked_days: 'quantidade_dias_semana',
  saturday_days: 'quantidade_sabado',
  sunday_days: 'quantidade_domingo',
});

export const inheritedLaborDays = (dfp, field) => {
  const chave = INHERITED_LABOR_DAYS[field];
  return chave ? numberOrZero(dfp?.metadata?.[chave]) : null;
};

const horasExtrasDaCategoria = (dfp, field) => (dfp?.mao_de_obra_direta?.items || [])
  .reduce((soma, item) => soma + numberOrZero(item?.[field]), 0);

const formatarDias = (dias) => `${dias} dia${dias === 1 ? '' : 's'}`;

// O prazo de execução do cabeçalho não alimenta a mão de obra: os dias vêm de
// Identificação e Escopo e de cada função. Quando divergem, o total muda dezenas ou centenas de
// milhares de reais sem nenhum sinal na tela — por isso o aviso nomeia os dois números.
export const avisosDePrazo = (dfp, prazoCabecalho) => {
  if (dfp?.calculation_version !== 2) return [];
  const linhas = (dfp.mao_de_obra_direta?.items || []).filter((item) => numberOrZero(item?.quantity) > 0);
  if (!linhas.length) return [];
  const avisos = [];
  // Só o campo numérico "Prazo de execução (dias)" do cabeçalho: o texto livre de
  // Identificação ("6 meses") geraria um número de dias errado no aviso.
  const prazo = Number.isInteger(Number(prazoCabecalho)) && Number(prazoCabecalho) > 0 ? Number(prazoCabecalho) : null;
  if (prazo) {
    const diasPorFuncao = linhas.map((item) => ['worked_days', 'saturday_days', 'sunday_days'].reduce(
      (soma, campo) => soma + numberOrZero(item?.[campo] == null || item[campo] === '' ? inheritedLaborDays(dfp, campo) : item[campo]),
      0,
    ));
    const diferentes = [...new Set(diasPorFuncao.filter((dias) => dias !== prazo))];
    if (diferentes.length) {
      avisos.push(`O prazo de execução do cabeçalho é de ${formatarDias(prazo)}, mas a mão de obra está calculada com ${diferentes.map(formatarDias).join(' / ')} de execução (dias de semana + sábados + domingos). Confira as quantidades de dias em Identificação e Escopo ou em cada função.`);
    }
  }
  return avisos;
};

// Avisos não bloqueiam o salvamento: apontam entradas que zeram ou duplicam valor em silêncio.
export const collectOrcamentoWarnings = (dfp, { prazoDias } = {}) => {
  if (dfp?.calculation_version !== 2) return [];
  const avisos = [];
  const metadata = dfp.metadata || {};

  for (const [campoHoras, campoFator, rotulo] of [
    ['overtime_week_hours', 'semana_fator', 'semanais'],
    ['overtime_saturday_hours', 'sabado_fator', 'de sábado'],
    ['overtime_sunday_hours', 'domingo_fator', 'de domingo'],
  ]) {
    if (horasExtrasDaCategoria(dfp, campoHoras) > 0 && numberOrZero(metadata[campoFator]) === 0) {
      avisos.push(`Há horas extras ${rotulo} lançadas com multiplicador zerado: elas não estão sendo pagas no cálculo.`);
    }
  }

  avisos.push(...avisosDePrazo(dfp, prazoDias));

  const administrativo = numberOrZero(dfp.custos_administrativos?.daily_cost) > 0;
  const indiretoAdm = (dfp.custos_indiretos?.items || []).find((item) => (
    /adm/i.test(String(item?.label || '')) && numberOrZero(item?.aliquot_percent) > 0
  ));
  if (administrativo && indiretoAdm) {
    avisos.push(`O bloco Custos Administrativos e o percentual “${indiretoAdm.label}” em Custos indiretos estão preenchidos ao mesmo tempo: confira se a estrutura administrativa não está sendo contada duas vezes.`);
  }

  return [...new Set(avisos)];
};

export const computeSectionTotal = (dfp, path) => {
  const section = getNestedValue(dfp, path) || {};
  if (Array.isArray(section)) return computeItemsTotal(section);
  if (path === 'custos_administrativos') {
    const m = dfp.metadata || {};
    const days = numberOrZero(section.days) || numberOrZero(m.quantidade_dias_semana)
      + numberOrZero(m.quantidade_sabado) + numberOrZero(m.quantidade_domingo);
    // Campo vazio cai no mesmo default que o backend aplica, senão o preview
    // mostra um total que não é o que será gravado.
    return roundCurrency(numberOrZero(section.daily_cost) * days
      * numberOrBlankDefault(section.multiplier, 1)
      * numberOrBlankDefault(section.considered_percent, 100) / 100
      * (1 - numberOrZero(section.discount_percent) / 100));
  }
  let base;
  if (path === 'mao_de_obra_direta' && dfp.calculation_version === 2) {
    const rows = (section.items || []).map((item) => computeLaborRow(item, dfp));
    base = rows.reduce((sum, row) => sum + row.total, 0);
    base += (section.adjustments || []).reduce((sum, adjustment) => {
      const row = rows.find((item) => item.id === adjustment.labor_item_id);
      if (!row || !numberOrZero(row.quantity)) return sum;
      return sum + (row.base + (adjustment.base === 'salary_and_overtime' ? row.extra : 0))
        * Math.min(numberOrZero(adjustment.quantity), numberOrZero(row.quantity)) / row.quantity
        * numberOrZero(adjustment.percent) / 100;
    }, 0);
    base *= 1 + numberOrZero(section.social_charges_percent) / 100;
  } else if (path.startsWith('mao_de_obra')) base = computeLaborTotal(section);
  else {
    const peopleDays = (dfp.mao_de_obra_direta?.items || []).reduce((sum, item) => sum
      + computeLaborRow(item, dfp).allDays * numberOrZero(item.quantity), 0);
    base = roundCurrency((section.items || []).reduce((sum, item) => sum
      + (path === 'alimentacao' && dfp.calculation_version === 2 ? peopleDays : numberOrZero(item.quantity))
      * numberOrZero(item.unit_cost), 0));
  }
  return dfp.calculation_version === 2
    ? roundCurrency(base * (1 - Math.min(numberOrZero(section.discount_percent), 100) / 100))
    : roundCurrency(base);
};

export const computeTableRowSubtotal = (dfp, collectionPath, item) => {
  if (collectionPath.startsWith('mao_de_obra')) {
    if (dfp.calculation_version === 2) return computeLaborRow(item, dfp).total;
    const hourly = numberOrZero(item.hourly_rate)
      || (numberOrZero(item.salary_base_hours) > 0 ? numberOrZero(item.salary_real) / item.salary_base_hours : 0);
    return numberOrZero(item.quantity) * numberOrZero(item.hours_per_employee) * hourly + numberOrZero(item.manual_total);
  }
  const quantity = dfp.calculation_version === 2 && collectionPath === 'alimentacao.items'
    ? (dfp.mao_de_obra_direta?.items || []).reduce((sum, row) => sum + computeLaborRow(row, dfp).allDays * numberOrZero(row.quantity), 0)
    : numberOrZero(item.quantity);
  return quantity * numberOrZero(item.unit_cost);
};

const computeLaborTotal = (section) => {
  const base = (Array.isArray(section?.items) ? section.items : []).reduce((total, item) => {
    const baseHours = numberOrZero(item?.salary_base_hours);
    const hourly = numberOrZero(item?.hourly_rate)
      || (baseHours > 0 ? numberOrZero(item?.salary_real) / baseHours : 0);
    return total
      + numberOrZero(item?.quantity) * numberOrZero(item?.hours_per_employee) * hourly
      + numberOrZero(item?.manual_total);
  }, 0);
  const adjusted = (Array.isArray(section?.adjustments) ? section.adjustments : [])
    .reduce((total, adjustment) => total + base * numberOrZero(adjustment?.percent) / 100, base);
  return roundCurrency(adjusted + adjusted * numberOrZero(section?.social_charges_percent) / 100);
};

const computeItemsTotal = (items) => roundCurrency(
  (Array.isArray(items) ? items : []).reduce(
    (total, item) => total + numberOrZero(item?.quantity) * numberOrZero(item?.unit_cost),
    0,
  ),
);

export const computeDfpSummary = (dfp) => {
  if (dfp?.calculation_version === 2) return computeUpdatedSummary(dfp);
  const directLabor = computeLaborTotal(dfp?.mao_de_obra_direta);
  const indirectLabor = computeLaborTotal(dfp?.mao_de_obra_indireta);
  const transport = computeItemsTotal(dfp?.veiculos_hospedagem?.items)
    + computeItemsTotal(dfp?.veiculos_hospedagem?.lodging_assets);
  const directCosts = roundCurrency([
    directLabor,
    indirectLabor,
    transport,
    computeItemsTotal(dfp?.alimentacao?.items),
    computeItemsTotal(dfp?.equipamentos?.items),
    computeItemsTotal(dfp?.epis_epcs?.items),
    computeItemsTotal(dfp?.materiais_consumo?.items),
    computeItemsTotal(dfp?.ferramental?.items),
    computeItemsTotal(dfp?.outros_custos_diretos?.items),
  ].reduce((total, value) => total + value, 0));
  const indirectCosts = roundCurrency(
    (Array.isArray(dfp?.custos_indiretos?.items) ? dfp.custos_indiretos.items : [])
      .reduce((total, item) => total + directCosts * numberOrZero(item?.aliquot_percent) / 100, 0),
  );
  const profit = roundCurrency(directCosts * numberOrZero(dfp?.bdi?.factor_percent) / 100);
  const totalCosts = roundCurrency(directCosts + indirectCosts + profit);
  const totalTaxes = roundCurrency(
    (Array.isArray(dfp?.impostos?.items) ? dfp.impostos.items : [])
      .reduce((total, item) => total + numberOrZero(item?.aliquot_percent), 0),
  );
  const invoicePrice = totalTaxes < 100
    ? roundCurrency(totalCosts / ((100 - totalTaxes) / 100))
    : 0;
  const area = numberOrZero(dfp?.metadata?.area_total);
  const collaborators = (Array.isArray(dfp?.mao_de_obra_direta?.items)
    ? dfp.mao_de_obra_direta.items
    : []).reduce((total, item) => total + numberOrZero(item?.quantity), 0);
  const workedDays = (Array.isArray(dfp?.mao_de_obra_direta?.items)
    ? dfp.mao_de_obra_direta.items
    : []).reduce((total, item) => total + numberOrZero(item?.worked_days), 0);
  const term = Math.max(numberOrZero(dfp?.metadata?.quantidade_dias_semana), workedDays);

  return {
    custosDiretosTotal: directCosts,
    custosIndiretosTotal: indirectCosts,
    lucroTotal: profit,
    custosTotais: totalCosts,
    aliquotaImpostosTotal: totalTaxes,
    precoTotalFaturamento: invoicePrice,
    precoPorArea: area > 0 ? roundCurrency(invoicePrice / area) : 0,
    valorDiaColaborador: term > 0 && collaborators > 0
      ? roundCurrency(invoicePrice / term / collaborators)
      : 0,
  };
};

function computeUpdatedSummary(dfp) {
  const paths = ['mao_de_obra_direta', 'custos_administrativos', 'veiculos_hospedagem', 'alimentacao',
    'equipamentos', 'epis_epcs', 'materiais_consumo', 'ferramental', 'outros_custos_diretos'];
  const direct = roundCurrency(paths.reduce((sum, path) => sum + computeSectionTotal(dfp, path), 0));
  const indirect = roundCurrency(roundCurrency((dfp.custos_indiretos?.items || []).reduce((sum, item) => sum + direct * numberOrZero(item.aliquot_percent) / 100, 0)) * (1 - numberOrZero(dfp.custos_indiretos?.discount_percent) / 100));
  const profit = roundCurrency(roundCurrency(direct * numberOrZero(dfp.bdi?.factor_percent) / 100) * (1 - numberOrZero(dfp.bdi?.discount_percent) / 100));
  const taxes = (dfp.impostos?.items || []).reduce((sum, item) => sum + numberOrZero(item.aliquot_percent), 0);
  const total = roundCurrency(direct + indirect + profit);
  const invoice = taxes < 100 ? roundCurrency(total / (1 - taxes / 100)) : 0;
  const peopleDays = (dfp.mao_de_obra_direta?.items || []).reduce((sum, item) => sum + computeLaborRow(item, dfp).allDays * numberOrZero(item.quantity), 0);
  return { custosDiretosTotal: direct, custosIndiretosTotal: indirect, lucroTotal: profit, custosTotais: total,
    aliquotaImpostosTotal: taxes, precoTotalFaturamento: invoice,
    precoPorArea: numberOrZero(dfp.metadata?.area_total) ? roundCurrency(invoice / dfp.metadata.area_total) : 0,
    valorDiaColaborador: peopleDays ? roundCurrency(invoice / peopleDays) : 0 };
}

// --- Carteira: busca, filtros e ordenação (funções puras, nunca alteram a entrada) ---------

const normalizarBusca = (value) => String(value ?? '')
  .normalize('NFD')
  .replace(/[\u0300-\u036f]/g, '')
  .toLocaleLowerCase('pt-BR')
  .trim();

const SITUACOES_EM_CURSO = Object.freeze(['rascunho', 'em_revisao']);

export const FILTROS_CARTEIRA = Object.freeze([
  Object.freeze({ value: 'todos', label: 'Todos' }),
  Object.freeze({ value: 'em_curso', label: 'Em curso' }),
  Object.freeze({ value: 'pronto_para_proposta', label: 'Prontos' }),
  Object.freeze({ value: 'emitido', label: 'Emitidos' }),
  Object.freeze({ value: 'inativo', label: 'Inativos' }),
]);

export const ORDENACOES_CARTEIRA = Object.freeze([
  Object.freeze({ value: 'recentes', label: 'Mais recentes' }),
  Object.freeze({ value: 'codigo', label: 'Código' }),
  Object.freeze({ value: 'contratante', label: 'Contratante (A–Z)' }),
  Object.freeze({ value: 'valor', label: 'Maior faturamento' }),
]);

const correspondeSituacao = (orcamento, situacao) => {
  const atual = orcamento?.revisaoAtual?.situacao;
  if (!situacao || situacao === 'todos') return true;
  if (situacao === 'em_curso') return SITUACOES_EM_CURSO.includes(atual);
  if (!(situacao in SITUACOES)) return true;
  return atual === situacao;
};

const instante = (orcamento) => {
  const time = Date.parse(orcamento?.createdAt || '');
  return Number.isFinite(time) ? time : 0;
};

const COMPARADORES = Object.freeze({
  recentes: (a, b) => (instante(b) - instante(a)) || ((b.sequencial || 0) - (a.sequencial || 0)),
  codigo: (a, b) => ((a.sequencial || 0) - (b.sequencial || 0)) || String(a.codigo).localeCompare(String(b.codigo), 'pt-BR'),
  contratante: (a, b) => String(a.contratante).localeCompare(String(b.contratante), 'pt-BR', { sensitivity: 'base' })
    || ((a.sequencial || 0) - (b.sequencial || 0)),
  valor: (a, b) => ((Number(b?.dfpSummary?.precoTotalFaturamento) || 0) - (Number(a?.dfpSummary?.precoTotalFaturamento) || 0))
    || ((b.sequencial || 0) - (a.sequencial || 0)),
});

export const filtrarCarteira = (orcamentos, { busca = '', situacao = 'todos', ordem = 'recentes' } = {}) => {
  const lista = Array.isArray(orcamentos) ? orcamentos : [];
  const termo = normalizarBusca(busca);
  const comparar = COMPARADORES[ordem] || COMPARADORES.recentes;
  return lista
    .filter((item) => correspondeSituacao(item, situacao))
    .filter((item) => !termo
      || normalizarBusca(item?.codigo).includes(termo)
      || normalizarBusca(item?.contratante).includes(termo))
    .slice()
    .sort(comparar);
};

export const contarFiltrosCarteira = (orcamentos) => {
  const lista = Array.isArray(orcamentos) ? orcamentos : [];
  return Object.fromEntries(FILTROS_CARTEIRA.map(({ value }) => [
    value, lista.filter((item) => correspondeSituacao(item, value)).length,
  ]));
};

// Mostra as revisões mais recentes e garante que a atual apareça mesmo se for antiga.
export const limitarRevisoesVisiveis = (revisoes, atualId, maximo = 4) => {
  const lista = Array.isArray(revisoes) ? revisoes : [];
  if (lista.length <= maximo) return { visiveis: lista, ocultas: 0 };
  const recentes = lista.slice(-maximo);
  const atual = lista.find((item) => item.id === atualId);
  const visiveis = atual && !recentes.includes(atual)
    ? [atual, ...recentes.slice(1)]
    : recentes;
  return { visiveis, ocultas: lista.length - visiveis.length };
};

// --- Histórico de edição: rótulos de negócio no lugar de chaves técnicas ------------------

const camelParaSnake = (field) => field.replace(/[A-Z]/g, (letra) => `_${letra.toLowerCase()}`);

const ROTULOS_HISTORICO = Object.freeze({
  ...Object.fromEntries(CAMPOS_CABECALHO.map(({ field, label }) => [camelParaSnake(field), label])),
  prazo_execucao_dias: 'Prazo de execução (dias)',
  data_inicio: 'Data de início',
  saldo_mao_de_obra: 'Saldo de Mão de Obra',
  regime_tributario: 'Forma de tributação',
  dfp: 'Composição de preços (DFP)',
  situacao: 'Situação',
  motivo: 'Motivo da mudança',
});

export const rotuloCampoHistorico = (chave) => ROTULOS_HISTORICO[String(chave || '')] || null;

const TITULOS_EVENTO = Object.freeze({
  criacao: 'Criação', edicao: 'Edição', situacao: 'Mudança de situação',
});

export const resumirEventoHistorico = (entry) => {
  const antes = entry?.antes || {};
  const depois = entry?.depois || {};
  const tipo = String(entry?.tipo || '');
  const base = { tipo, titulo: TITULOS_EVENTO[tipo] || 'Alteração', campos: [], de: null, para: null, motivo: null };
  if (tipo === 'criacao') return base;
  if (tipo === 'situacao') {
    return {
      ...base,
      de: SITUACOES[antes.situacao] || antes.situacao || null,
      para: SITUACOES[depois.situacao] || depois.situacao || null,
      motivo: depois.motivo ? String(depois.motivo) : null,
    };
  }
  const campos = Object.keys(depois)
    .filter((key) => JSON.stringify(antes[key]) !== JSON.stringify(depois[key]))
    .map(rotuloCampoHistorico)
    .filter(Boolean);
  return { ...base, campos: [...new Set(campos)] };
};

// O backend grava só o id do usuário; mostramos algo legível sem expor o identificador inteiro.
export const rotuloResponsavel = (userId, currentUserId) => {
  const id = String(userId ?? '').trim();
  if (!id) return 'Responsável não registrado';
  if (currentUserId && id === String(currentUserId)) return 'Você';
  if (id.toLowerCase() === 'sistema') return 'Sistema';
  return `Usuário ${id.length > 8 ? `${id.slice(0, 8)}…` : id}`;
};

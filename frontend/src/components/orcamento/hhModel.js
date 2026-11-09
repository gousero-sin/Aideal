// Composição HH (Homem-Hora): espelha backend/app/orcamento/hh.py, que reproduz a planilha
// "MODELO COMPOSIÇÃO DE CUSTO". O backend é a fonte da verdade ao salvar; aqui o cálculo serve
// para a prévia em tempo real e precisa bater centavo a centavo.

/** Custos mensais por pessoa (subtotal B). `baseHoraExtra=false` sai da base da hora extra. */
export const HH_CUSTO_COLUNAS = Object.freeze([
  ['mobilizacao', 'Mobilização', true],
  ['exames_medicos', 'Exames Médicos', false],
  ['treinamentos', 'Treinamentos', false],
  ['transporte', 'Transporte', false],
  ['cesta_basica', 'Cesta Básica', false],
  ['assistencia_medica', 'Assistência Médica', false],
  ['seguro_vida', 'Seguro de Vida', false],
  ['plr', 'PLR', false],
  ['uniforme', 'Uniforme', true],
  ['epi', 'EPI', true],
  ['treinamento_racs', 'Treinamento de RACs', false],
  ['materiais', 'Materiais', true],
  ['ferramentas', 'Ferramentas', true],
  ['equipamentos', 'Equipamentos', false],
  ['veiculos', 'Veículos', false],
  ['combustivel', 'Combustível / Lubrificantes / Manutenção', true],
  ['comunicacao', 'Comunicação (Telefone / Internet / Rádio)', false],
  ['investimentos', 'Investimentos', false],
  ['desmobilizacao', 'Desmobilização', true],
  ['outros', 'Outros', false],
].map(([id, label, baseHoraExtra]) => Object.freeze({ id, label, baseHoraExtra })));

export const HH_GRUPOS_ENCARGOS = Object.freeze([
  ['A', 'Grupo A — contribuições'],
  ['B', 'Grupo B — tempo não trabalhado'],
  ['C', 'Grupo C — rescisões'],
  ['D', 'Grupo D — incidências cumulativas'],
]);

const num = (value) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : 0;
};

const cents = (value) => Math.round((value + Number.EPSILON) * 100) / 100;

const clone = (value) => JSON.parse(JSON.stringify(value ?? null));

/** Percentuais por grupo e o grupo D derivado (A×B e FGTS×aviso prévio), em pontos %. */
export const computeHhEncargos = (hh) => {
  const itens = Array.isArray(hh?.encargos) ? hh.encargos : [];
  const grupos = { A: 0, B: 0, C: 0, D: 0 };
  const porId = Object.fromEntries(itens.map((item) => [item.id, num(item.percent)]));
  itens.forEach((item) => { if (item.grupo in grupos) grupos[item.grupo] += num(item.percent); });
  const d1 = (grupos.A * grupos.B) / 100;
  const d3 = ((porId.a2 || 0) * (porId.c3 || 0)) / 100;
  grupos.D += d1 + d3;
  return { grupos, derivados: { d1, d3 }, totalPercent: grupos.A + grupos.B + grupos.C + grupos.D };
};

/** Uma função da planilha: A (salário + encargos), B (custos), C (BDI), D (tributos) e HH. */
export const computeHhFuncao = (funcao, hh, encargosPercent = computeHhEncargos(hh).totalPercent) => {
  const quantidade = num(funcao?.quantidade);
  const horas = num(funcao?.horas_mes);
  const salario = num(funcao?.salario_base);
  const meses = num(hh?.meses);
  const noturnoGeral = num(hh?.percentual_noturno) / 100;
  const periculosidade = funcao?.periculosidade ? salario * num(hh?.periculosidade_percent) / 100 : 0;
  const adicionalNoturno = salario * num(funcao?.adicional_noturno_percent) / 100;
  const subtotalA1 = salario + periculosidade + adicionalNoturno;
  const encargosValor = subtotalA1 * encargosPercent / 100;
  const subtotalA2 = subtotalA1 + encargosValor;
  const custos = funcao?.custos || {};
  const subtotalB = HH_CUSTO_COLUNAS.reduce((soma, coluna) => soma + num(custos[coluna.id]), 0);
  const baseC = subtotalA2 + subtotalB;
  const despesas = baseC * num(hh?.bdi?.despesas_indiretas_percent) / 100;
  const lucro = baseC * num(hh?.bdi?.lucro_percent) / 100;
  const subtotalC = despesas + lucro;
  const baseD = baseC + subtotalC;
  const tributos = Object.fromEntries((hh?.tributos || []).map((item) => [item.id, baseD * num(item.percent) / 100]));
  const subtotalD = Object.values(tributos).reduce((soma, valor) => soma + valor, 0);
  const unitario = subtotalA2 + subtotalB + subtotalC + subtotalD;
  const foraDaHoraExtra = HH_CUSTO_COLUNAS
    .filter((coluna) => !coluna.baseHoraExtra)
    .reduce((soma, coluna) => soma + num(custos[coluna.id]), 0);
  const horaNormal = horas ? unitario / horas : 0;
  const baseHoraExtra = horas ? (unitario - foraDaHoraExtra) / horas : 0;
  const fatores = (hh?.horas_extras_percentuais || [60, 80, 100]).map((valor) => num(valor) / 100);
  return {
    salarioHora: horas ? salario / horas : 0,
    periculosidade,
    adicionalNoturno,
    subtotalA1,
    encargosValor,
    subtotalA2,
    totalA: subtotalA2 * quantidade,
    subtotalB,
    totalB: subtotalB * quantidade,
    despesas,
    lucro,
    subtotalC,
    totalC: subtotalC * quantidade,
    tributos,
    subtotalD,
    totalD: subtotalD * quantidade,
    unitario,
    totalMensal: unitario * quantidade,
    totalEstimado: unitario * quantidade * meses,
    horaNormal,
    horasExtras: fatores.map((fator) => baseHoraExtra * (1 + fator)),
    adicionalNoturnoHora: horaNormal * noturnoGeral,
    horaNoturna: horaNormal * (1 + noturnoGeral),
    horasExtrasNoturnas: fatores.map((fator) => baseHoraExtra * (1 + noturnoGeral) * (1 + fator)),
  };
};

/** Totais do contrato; os somatórios usam valores sem arredondar, como o Excel. */
export const computeHhSummary = (hh) => {
  const encargos = computeHhEncargos(hh);
  const totais = { totalA: 0, totalB: 0, totalC: 0, totalD: 0, totalMensal: 0, totalEstimado: 0, despesas: 0, lucro: 0, colaboradores: 0 };
  const grupos = (hh?.grupos || []).map((grupo) => {
    const funcoes = (grupo.funcoes || []).map((funcao) => {
      const calculo = computeHhFuncao(funcao, hh, encargos.totalPercent);
      const quantidade = num(funcao.quantidade);
      ['totalA', 'totalB', 'totalC', 'totalD', 'totalMensal', 'totalEstimado'].forEach((chave) => { totais[chave] += calculo[chave]; });
      totais.despesas += calculo.despesas * quantidade;
      totais.lucro += calculo.lucro * quantidade;
      totais.colaboradores += quantidade;
      return { id: funcao.id, ...calculo };
    });
    return {
      id: grupo.id,
      quantidade: (grupo.funcoes || []).reduce((soma, funcao) => soma + num(funcao.quantidade), 0),
      totalMensal: cents(funcoes.reduce((soma, linha) => soma + linha.totalMensal, 0)),
      totalEstimado: cents(funcoes.reduce((soma, linha) => soma + linha.totalEstimado, 0)),
      funcoes,
    };
  });
  const meses = num(hh?.meses);
  const aliquota = (hh?.tributos || []).reduce((soma, item) => soma + num(item.percent), 0);
  const diretos = (totais.totalA + totais.totalB) * meses;
  return {
    encargos,
    grupos,
    colaboradores: totais.colaboradores,
    meses,
    totalMensal: cents(totais.totalMensal),
    totalEstimado: cents(totais.totalEstimado),
    custosDiretosTotal: cents(diretos),
    custosIndiretosTotal: cents(totais.despesas * meses),
    lucroTotal: cents(totais.lucro * meses),
    custosTotais: cents(diretos + (totais.despesas + totais.lucro) * meses),
    aliquotaImpostosTotal: aliquota,
    precoTotalFaturamento: cents(totais.totalEstimado),
  };
};

export const createHhId = (prefix, existentes = []) => {
  const usados = new Set(existentes.map((id) => String(id).toLocaleLowerCase('pt-BR')));
  let indice = existentes.length + 1;
  while (usados.has(`${prefix}_${indice}`)) indice += 1;
  return `${prefix}_${indice}`;
};

const todasFuncoes = (hh) => (hh?.grupos || []).flatMap((grupo) => grupo.funcoes || []);

export const updateHhField = (hh, field, value) => ({ ...clone(hh), [field]: value });

export const updateHhBdi = (hh, field, value) => ({ ...clone(hh), bdi: { ...(hh?.bdi || {}), [field]: value } });

export const updateHhPercentItem = (hh, collection, id, value) => ({
  ...clone(hh),
  [collection]: (hh?.[collection] || []).map((item) => (item.id === id ? { ...item, percent: value } : item)),
});

export const updateHhHoraExtra = (hh, index, value) => ({
  ...clone(hh),
  horas_extras_percentuais: (hh?.horas_extras_percentuais || [60, 80, 100]).map((item, posicao) => (posicao === index ? value : item)),
});

const mapFuncoes = (hh, grupoId, mapper) => ({
  ...clone(hh),
  grupos: (hh?.grupos || []).map((grupo) => (grupo.id === grupoId ? { ...grupo, funcoes: mapper(grupo.funcoes || []) } : grupo)),
});

export const updateHhFuncao = (hh, grupoId, funcaoId, field, value) => mapFuncoes(hh, grupoId, (funcoes) => funcoes.map((funcao) => (funcao.id === funcaoId ? { ...funcao, [field]: value } : funcao)));

export const updateHhCusto = (hh, grupoId, funcaoId, custoId, value) => mapFuncoes(hh, grupoId, (funcoes) => funcoes.map((funcao) => (funcao.id === funcaoId ? { ...funcao, custos: { ...(funcao.custos || {}), [custoId]: value } } : funcao)));

export const addHhFuncao = (hh, grupoId) => mapFuncoes(hh, grupoId, (funcoes) => [...funcoes, {
  id: createHhId('funcao', todasFuncoes(hh).map((funcao) => funcao.id)),
  label: 'Nova função',
  quantidade: 1,
  horas_mes: 220,
  salario_base: 0,
  periculosidade: false,
  adicional_noturno_percent: 0,
  custos: Object.fromEntries(HH_CUSTO_COLUNAS.map((coluna) => [coluna.id, 0])),
}]);

export const removeHhFuncao = (hh, grupoId, funcaoId) => mapFuncoes(hh, grupoId, (funcoes) => funcoes.filter((funcao) => funcao.id !== funcaoId));

export const addHhGrupo = (hh) => ({
  ...clone(hh),
  grupos: [...(hh?.grupos || []), { id: createHhId('grupo', (hh?.grupos || []).map((grupo) => grupo.id)), label: 'Novo grupo', funcoes: [] }],
});

export const updateHhGrupo = (hh, grupoId, label) => ({
  ...clone(hh),
  grupos: (hh?.grupos || []).map((grupo) => (grupo.id === grupoId ? { ...grupo, label } : grupo)),
});

export const removeHhGrupo = (hh, grupoId) => ({
  ...clone(hh),
  grupos: (hh?.grupos || []).filter((grupo) => grupo.id !== grupoId),
});

// Mesmos limites de backend/app/orcamento/hh.py (normalize_hh).
const HH_LIMITES = Object.freeze({ valor: 1e9, quantidade: 100000, horasMes: 744, meses: 1200, grupos: 50, funcoes: 250, texto: 200, horaExtra: 1000 });

const isBlank = (value) => value === '' || value === null || value === undefined;
const foraDaFaixa = (value, max) => !isBlank(value) && (!Number.isFinite(Number(value)) || Number(value) < 0 || Number(value) > max);

/** Erros que o backend recusaria; bloqueiam o salvamento com mensagem em português. */
export const validateHh = (hh) => {
  if (!hh) return [];
  const erros = [];
  const percentuais = [
    ['Adicional noturno geral', hh.percentual_noturno],
    ['Periculosidade', hh.periculosidade_percent],
    ['Despesas indiretas', hh.bdi?.despesas_indiretas_percent],
    ['Lucro', hh.bdi?.lucro_percent],
    ...(hh.encargos || []).map((item) => [`Encargo ${item.label}`, item.percent]),
    ...(hh.tributos || []).map((item) => [`Tributo ${item.label}`, item.percent]),
  ];
  percentuais.forEach(([rotulo, valor]) => {
    if (foraDaFaixa(valor, 99.999999)) erros.push(`${rotulo} deve estar entre 0% e 100%.`);
  });
  if ((hh.tributos || []).reduce((soma, item) => soma + num(item.percent), 0) >= 100) erros.push('A soma dos tributos HH deve ser menor que 100%.');
  if (foraDaFaixa(hh.meses, HH_LIMITES.meses)) erros.push('Informe o prazo do contrato HH em meses (0 a 1200).');
  if (foraDaFaixa(hh.salario_minimo, HH_LIMITES.valor)) erros.push('O salário mínimo de referência deve ser um número não negativo.');
  (hh.horas_extras_percentuais || []).forEach((valor, indice) => {
    if (foraDaFaixa(valor, HH_LIMITES.horaExtra)) erros.push(`A hora extra ${indice + 1} deve estar entre 0% e 1000%.`);
  });
  const grupos = hh.grupos || [];
  if (grupos.length > HH_LIMITES.grupos) erros.push(`Use no máximo ${HH_LIMITES.grupos} grupos de funções.`);
  if (todasFuncoes(hh).length > HH_LIMITES.funcoes) erros.push(`Use no máximo ${HH_LIMITES.funcoes} funções no HH.`);
  grupos.forEach((grupo) => {
    if (String(grupo.label || '').length > HH_LIMITES.texto) erros.push(`O nome do grupo “${String(grupo.label).slice(0, 40)}…” passa de ${HH_LIMITES.texto} caracteres.`);
  });
  todasFuncoes(hh).forEach((funcao) => {
    const nome = funcao.label || 'sem nome';
    if (!String(funcao.label || '').trim()) erros.push('Toda função HH precisa de um nome.');
    if (String(funcao.label || '').length > HH_LIMITES.texto) erros.push(`O nome da função “${String(nome).slice(0, 40)}…” passa de ${HH_LIMITES.texto} caracteres.`);
    const valores = [funcao.salario_base, ...Object.values(funcao.custos || {})];
    if (valores.some((valor) => foraDaFaixa(valor, HH_LIMITES.valor))) erros.push(`Na função “${nome}”, salário e custos devem ser números entre 0 e 1 bilhão.`);
    if (foraDaFaixa(funcao.quantidade, HH_LIMITES.quantidade)) erros.push(`A quantidade da função “${nome}” deve ficar entre 0 e 100.000.`);
    const horas = Number(funcao.horas_mes);
    if (foraDaFaixa(funcao.horas_mes, HH_LIMITES.horasMes) || (horas > 0 && horas < 1)) erros.push(`As horas por mês de “${nome}” devem ser 0 ou ficar entre 1 e 744.`);
    if (foraDaFaixa(funcao.adicional_noturno_percent, 99.999999)) erros.push(`Adicional noturno de “${nome}” deve estar entre 0% e 100%.`);
  });
  return [...new Set(erros)];
};

/** Avisos não bloqueantes: entradas que zeram o resultado sem chamar atenção. */
export const collectHhWarnings = (hh) => {
  if (!hh) return [];
  const avisos = [];
  const funcoes = todasFuncoes(hh);
  if (!funcoes.some((funcao) => num(funcao.quantidade) > 0)) avisos.push('Nenhuma função HH tem quantidade: o total do contrato fica zerado.');
  if (num(hh.meses) === 0) avisos.push('O prazo do contrato em meses está zerado: o total estimado fica R$ 0,00.');
  funcoes.filter((funcao) => num(funcao.quantidade) > 0 && num(funcao.horas_mes) === 0)
    .forEach((funcao) => avisos.push(`“${funcao.label}” está sem horas no mês: o valor da hora não pode ser calculado.`));
  return avisos;
};

/** Prazo em meses sugerido a partir do prazo de execução do cabeçalho (dias corridos). */
export const mesesDoPrazo = (dias) => {
  const valor = Number(dias);
  return Number.isFinite(valor) && valor > 0 ? Math.max(1, Math.round(valor / 30)) : null;
};

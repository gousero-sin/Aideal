export const MESES_LABEL = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];

export const formatCurrency = (value) =>
  new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    maximumFractionDigits: 0,
  }).format(Number(value || 0));

export const formatNumber = (value) => new Intl.NumberFormat('pt-BR').format(Number(value || 0));

export const formatDecimal = (value, maximumFractionDigits = 1) =>
  new Intl.NumberFormat('pt-BR', {
    maximumFractionDigits,
    minimumFractionDigits: Number(value || 0) % 1 === 0 ? 0 : 1,
  }).format(Number(value || 0));

export const formatMonths = (value) => {
  const numeric = Number(value || 0);
  const unit = Math.abs(numeric) === 1 ? 'mês' : 'meses';
  return `${formatDecimal(numeric)} ${unit}`;
};

export const formatSignedCurrency = (value) => {
  const numeric = Number(value || 0);
  const formatted = formatCurrency(Math.abs(numeric));
  if (numeric === 0) return formatted;
  return numeric > 0 ? `+${formatted}` : `-${formatted}`;
};

export const buildPanelQuery = (filters) => {
  const params = new URLSearchParams();
  if (filters.ano) params.set('ano', String(filters.ano));

  const appendMany = (key, values) => {
    (values || []).forEach((value) => {
      if (value !== null && value !== undefined && String(value).trim() !== '') {
        params.append(key, String(value));
      }
    });
  };

  appendMany('meses', filters.meses);
  appendMany('centro_custo', filters.centro_custo);
  appendMany('natureza', filters.natureza);
  appendMany('banco', filters.banco);
  appendMany('tipo', filters.tipo);
  appendMany('classificacao', filters.classificacao);
  if (filters.escopo_periodo) params.set('escopo_periodo', String(filters.escopo_periodo));
  return params.toString();
};

export const buildDREPanelQuery = (filters) => buildPanelQuery(filters);

export const buildDREExportRequest = (filters = {}, data = {}) => {
  const selectedCenters = Array.isArray(filters.centro_custo) ? filters.centro_custo : [];
  if (selectedCenters.length !== 1) {
    return { valid: false, error: 'Selecione exatamente uma obra para exportar o DRE.' };
  }

  const selectedMonths = Array.isArray(filters.meses) && filters.meses.length > 0
    ? filters.meses : data?.filtros_disponiveis?.meses || [];
  const months = [...new Set(selectedMonths.map(Number).filter((month) => month >= 1 && month <= 12))]
    .sort((left, right) => left - right);
  const year = Number(filters.ano || data?.periodo?.ano);
  if (!Number.isInteger(year) || months.length === 0) {
    return { valid: false, error: 'Não há período disponível para exportar o DRE.' };
  }

  const targetMonth = months[months.length - 1];
  return {
    valid: true,
    centroCusto: selectedCenters[0],
    competencia: `${String(targetMonth).padStart(2, '0')}/${year}`,
    meses: months,
  };
};

export const mergeCurrentYear = (anos, currentYear) => {
  const parsed = Number(currentYear);
  const normalized = [...new Set([...(anos || []), ...(Number.isFinite(parsed) ? [parsed] : [])])];
  return normalized.sort((a, b) => b - a);
};

export const toggleValue = (values, value) => {
  const current = values || [];
  if (current.includes(value)) {
    return current.filter((item) => item !== value);
  }
  return [...current, value];
};

export const topRows = (rows, limit = 10) => (Array.isArray(rows) ? rows.slice(0, limit) : []);

export const getMetric = (row, key) => Number(row?.[key] || 0);

export const pickTopBy = (rows, key, { absolute = false } = {}) => {
  const source = Array.isArray(rows) ? rows : [];
  return source.reduce((winner, row) => {
    if (!winner) return row;
    const currentValue = absolute ? Math.abs(getMetric(row, key)) : getMetric(row, key);
    const winnerValue = absolute ? Math.abs(getMetric(winner, key)) : getMetric(winner, key);
    return currentValue > winnerValue ? row : winner;
  }, null);
};

export const pickLowestBy = (rows, key) => {
  const source = Array.isArray(rows) ? rows : [];
  return source.reduce((winner, row) => {
    if (!winner) return row;
    return getMetric(row, key) < getMetric(winner, key) ? row : winner;
  }, null);
};

export const formatPercent = (value) =>
  `${new Intl.NumberFormat('pt-BR', {
    maximumFractionDigits: 1,
    minimumFractionDigits: Number(value || 0) % 1 === 0 ? 0 : 1,
  }).format(Number(value || 0))}%`;

export const absoluteShare = (row, rows, key = 'saldo') => {
  const total = (Array.isArray(rows) ? rows : []).reduce(
    (sum, item) => sum + Math.abs(getMetric(item, key)),
    0,
  );
  if (!row || total <= 0) return 0;
  return (Math.abs(getMetric(row, key)) / total) * 100;
};

export const countSelectedFilters = (filters, keys) =>
  keys.reduce((total, key) => total + ((filters?.[key] || []).length || 0), 0);

export const buildFilterSummary = (filters, descriptors) =>
  descriptors.flatMap(({ key, label }) =>
    (filters?.[key] || []).map((value) => ({
      key,
      label,
      value,
      text: `${label}: ${value}`,
    })),
  );

// Card de resultado do Painel DRE: o valor é o Resultado Líquido da DRE
// (linha 181); o saldo de caixa só entra quando a API não o envia.
export const buildResultadoLiquidoKpi = (kpis = {}) => {
  const value = kpis.resultado_liquido ?? kpis.saldo_liquido;
  const temDetalhe = kpis.resultado_antes_ir != null && kpis.resultado_gerencial != null;
  const detail = temDetalhe
    ? `antes do IR ${formatSignedCurrency(kpis.resultado_antes_ir)} · gerencial ${formatSignedCurrency(kpis.resultado_gerencial)}`
    : 'resultado líquido do DRE';
  return { value, detail };
};

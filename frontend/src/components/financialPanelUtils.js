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

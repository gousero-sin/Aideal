import React, { useEffect, useId, useMemo, useState } from 'react';
import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { formatCurrency, formatNumber, formatPercent, topRows } from './financialPanelUtils';

const COLORS = ['#35c7f2', '#2f8bd8', '#ffc629', '#f01821', '#8fd5ff', '#7adf9b'];
const DONUT_COLORS = [
  { start: '#4bd8ff', end: '#168ad1' },
  { start: '#4ea7ff', end: '#2357c8' },
  { start: '#ffd957', end: '#e6a711' },
  { start: '#ff414a', end: '#c90f1b' },
  { start: '#a9dcff', end: '#56a9d9' },
  { start: '#82eba4', end: '#42a96d' },
];

const formatAxisLabel = (value = '') => {
  const label = String(value);
  return label.length > 19 ? `${label.slice(0, 18)}...` : label;
};

const formatTooltipValue = (item) => {
  const dataKey = String(item.dataKey);
  if (dataKey.includes('total') || dataKey.includes('lancamentos') || dataKey.includes('movimentos')) {
    return formatNumber(item.value);
  }
  return formatCurrency(item.value);
};

const formatCompactCurrency = (value) => {
  const numeric = Number(value || 0);
  if (!Number.isFinite(numeric)) return formatCurrency(0);

  const absoluteValue = Math.abs(numeric);
  if (absoluteValue >= 1000000) {
    return `R$ ${new Intl.NumberFormat('pt-BR', {
      maximumFractionDigits: 1,
      minimumFractionDigits: 1,
    }).format(numeric / 1000000)} mi`;
  }

  if (absoluteValue >= 1000) {
    return `R$ ${new Intl.NumberFormat('pt-BR', {
      maximumFractionDigits: 0,
    }).format(numeric / 1000)} mil`;
  }

  return formatCurrency(numeric);
};

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="aideal-chart-tooltip">
      <strong>{label}</strong>
      {payload.map((item) => (
        <span key={`${item.dataKey}-${item.name}`} style={{ color: item.color }}>
          {item.name}: {formatTooltipValue(item)}
        </span>
      ))}
    </div>
  );
}

function DonutTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload;
  if (!row) return null;
  return (
    <div className="aideal-chart-tooltip">
      <strong>{row.name}</strong>
      <span style={{ color: row.color }}>
        Impacto: {formatCurrency(row.value)}
      </span>
      <span>{formatPercent(row.share)} do total</span>
    </div>
  );
}

export function ChartCard({ title, subtitle, children, className = '' }) {
  return (
    <article className={`aideal-chart-card ${className}`}>
      <div className="aideal-chart-heading">
        <h3>{title}</h3>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {children}
    </article>
  );
}

export function MonthlyEvolutionChart({ data, countKey }) {
  if (!data?.length) {
    return <div className="aideal-chart-empty">Sem dados para o período filtrado.</div>;
  }

  // Painel DRE usa a linha de Receita Líquida do DRE gerado. Fluxo de Caixa usa brutos.
  const temImpostos = data.some((item) => item?.impostos != null);
  const entradasKey = temImpostos ? 'receita_liquida' : 'credito';
  const saidasKey = temImpostos ? 'saidas_liquidas' : 'debito';
  const entradasName = temImpostos ? 'Receita líquida' : 'Entradas';
  const saidasName = temImpostos ? 'Saídas operacionais' : 'Saídas';

  return (
    <div className="aideal-chart-frame">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 12, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="rgba(143,213,255,0.12)" vertical={false} />
          <XAxis dataKey="mes_label" tick={{ fill: '#a9b9c8', fontSize: 12 }} axisLine={false} tickLine={false} />
          <YAxis
            yAxisId="money"
            tick={{ fill: '#a9b9c8', fontSize: 12 }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(value) => `${Math.round(Number(value) / 1000)}k`}
          />
          <YAxis yAxisId="count" orientation="right" hide />
          <Tooltip content={<ChartTooltip />} />
          <Legend wrapperStyle={{ color: '#a9b9c8', fontSize: 12 }} />
          <Bar yAxisId="money" dataKey={entradasKey} name={entradasName} fill="#35c7f2" radius={[6, 6, 0, 0]} />
          <Bar yAxisId="money" dataKey={saidasKey} name={saidasName} fill="#f01821" radius={[6, 6, 0, 0]} />
          <Line
            yAxisId="money"
            type="monotone"
            dataKey="saldo"
            name="Saldo"
            stroke="#ffc629"
            strokeWidth={3}
            dot={{ r: 3, strokeWidth: 0, fill: '#ffc629' }}
          />
          <Area
            yAxisId="count"
            type="monotone"
            dataKey={countKey}
            name="Volume"
            fill="rgba(143,213,255,0.08)"
            stroke="rgba(143,213,255,0.22)"
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

export function RankingChart({ data, countKey }) {
  const rows = topRows(data, 8);
  if (!rows.length) {
    return <div className="aideal-chart-empty">Sem ranking para exibir.</div>;
  }

  return (
    <div className="aideal-chart-frame aideal-chart-frame-compact">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} layout="vertical" margin={{ top: 6, right: 12, bottom: 0, left: 8 }}>
          <CartesianGrid stroke="rgba(143,213,255,0.1)" horizontal={false} />
          <XAxis type="number" hide />
          <YAxis
            type="category"
            dataKey="nome"
            width={126}
            tick={{ fill: '#a9b9c8', fontSize: 11 }}
            tickFormatter={formatAxisLabel}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip content={<ChartTooltip />} />
          <Bar dataKey="saldo" name="Saldo" radius={[0, 6, 6, 0]}>
            {rows.map((row, index) => (
              <Cell key={row.nome} fill={row.saldo >= 0 ? COLORS[index % COLORS.length] : '#f01821'} />
            ))}
          </Bar>
          <Bar dataKey={countKey} name="Volume" fill="rgba(143,213,255,0.2)" radius={[0, 6, 6, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function CompositionDonut({ data }) {
  const gradientPrefix = useId().replace(/:/g, '');
  const [hiddenNames, setHiddenNames] = useState(() => new Set());
  const rows = useMemo(
    () => topRows(data, 6)
      .map((item, index) => {
        const color = DONUT_COLORS[index % DONUT_COLORS.length];
        return {
          name: item.nome,
          value: Math.abs(Number(item.saldo || 0)) || Number(item.credito || 0) + Number(item.debito || 0),
          color: color.start,
          colorEnd: color.end,
          gradientId: `aidealDonut${gradientPrefix}${index}`,
        };
      })
      .filter((item) => item.value > 0),
    [data, gradientPrefix],
  );

  useEffect(() => {
    const availableNames = new Set(rows.map((row) => row.name));
    setHiddenNames((current) => {
      const next = new Set([...current].filter((name) => availableNames.has(name)));
      return next.size === current.size ? current : next;
    });
  }, [rows]);

  if (!rows.length) {
    return <div className="aideal-chart-empty">Sem composição para exibir.</div>;
  }

  const total = rows.reduce((sum, item) => sum + item.value, 0);
  const visibleRows = rows
    .filter((row) => !hiddenNames.has(row.name))
    .map((row) => ({
      ...row,
      share: total > 0 ? (row.value / total) * 100 : 0,
    }));
  const visibleTotal = visibleRows.reduce((sum, item) => sum + item.value, 0);
  const hiddenCount = rows.length - visibleRows.length;

  const toggleRow = (name) => {
    setHiddenNames((current) => {
      const next = new Set(current);
      if (next.has(name)) {
        next.delete(name);
      } else {
        next.add(name);
      }
      return next;
    });
  };

  return (
    <div className="aideal-donut-layout">
      <div className="aideal-donut-chart-shell">
        <div className="aideal-donut-chart">
          {visibleRows.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <defs>
                  {visibleRows.map((row) => (
                    <linearGradient key={row.gradientId} id={row.gradientId} x1="0" y1="0" x2="1" y2="1">
                      <stop offset="0%" stopColor={row.color} />
                      <stop offset="100%" stopColor={row.colorEnd} />
                    </linearGradient>
                  ))}
                </defs>
                <Tooltip
                  content={<DonutTooltip />}
                  wrapperStyle={{ zIndex: 12, pointerEvents: 'none' }}
                  allowEscapeViewBox={{ x: true, y: true }}
                />
                <Pie
                  data={visibleRows}
                  dataKey="value"
                  nameKey="name"
                  innerRadius="70%"
                  outerRadius="94%"
                  paddingAngle={3}
                  cornerRadius={8}
                  stroke="rgba(7,9,13,0.84)"
                  strokeWidth={4}
                  isAnimationActive
                  animationDuration={760}
                >
                  {visibleRows.map((row) => (
                    <Cell key={row.name} fill={`url(#${row.gradientId})`} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="aideal-donut-empty-ring" />
          )}
          <div className="aideal-donut-center">
            <strong title={formatCurrency(visibleTotal)}>{formatCompactCurrency(visibleTotal)}</strong>
            <span>{visibleRows.length} visível(eis)</span>
            {hiddenCount > 0 && <em>{hiddenCount} oculto(s)</em>}
          </div>
        </div>
      </div>

      <div className="aideal-donut-legend" role="list" aria-label="Filtros da composição">
        {rows.map((row) => (
          <div
            key={row.name}
            className={`aideal-donut-legend-row ${hiddenNames.has(row.name) ? 'is-hidden' : ''}`}
            role="listitem"
          >
            <button
              type="button"
              className="aideal-donut-dot"
              style={{ '--dot-color': row.color }}
              onClick={() => toggleRow(row.name)}
              aria-pressed={!hiddenNames.has(row.name)}
              aria-label={`${hiddenNames.has(row.name) ? 'Exibir' : 'Ocultar'} ${row.name}`}
              title={`${hiddenNames.has(row.name) ? 'Exibir' : 'Ocultar'} ${row.name}`}
            />
            <div className="aideal-donut-legend-copy">
              <strong title={row.name}>{row.name}</strong>
              <span>{formatPercent(total > 0 ? (row.value / total) * 100 : 0)}</span>
            </div>
            <em>{formatCurrency(row.value)}</em>
          </div>
        ))}
      </div>
    </div>
  );
}

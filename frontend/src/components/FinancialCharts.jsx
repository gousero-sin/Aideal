import React from 'react';
import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { formatCurrency, formatNumber, topRows } from './financialPanelUtils';

const COLORS = ['#35c7f2', '#2f8bd8', '#ffc629', '#f01821', '#8fd5ff', '#7adf9b'];

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
          <Bar yAxisId="money" dataKey="credito" name="Entradas" fill="#35c7f2" radius={[6, 6, 0, 0]} />
          <Bar yAxisId="money" dataKey="debito" name="Saídas" fill="#f01821" radius={[6, 6, 0, 0]} />
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
  const rows = topRows(data, 6)
    .map((item) => ({
      name: item.nome,
      value: Math.abs(Number(item.saldo || 0)) || Number(item.credito || 0) + Number(item.debito || 0),
    }))
    .filter((item) => item.value > 0);

  if (!rows.length) {
    return <div className="aideal-chart-empty">Sem composição para exibir.</div>;
  }

  const total = rows.reduce((sum, item) => sum + item.value, 0);
  let cursor = 0;
  const gradient = rows
    .map((row, index) => {
      const start = cursor;
      const end = cursor + (row.value / total) * 100;
      cursor = end;
      return `${COLORS[index % COLORS.length]} ${start}% ${end}%`;
    })
    .join(', ');

  return (
    <div className="aideal-donut-layout">
      <div className="aideal-css-donut" style={{ background: `conic-gradient(${gradient})` }}>
        <div>
          <strong>{rows.length}</strong>
          <span>grupos</span>
        </div>
      </div>
      <div className="aideal-donut-legend">
        {rows.map((row, index) => (
          <div key={row.name}>
            <span style={{ background: COLORS[index % COLORS.length] }} />
            <strong title={row.name}>{row.name}</strong>
            <em>{formatCurrency(row.value)}</em>
          </div>
        ))}
      </div>
    </div>
  );
}

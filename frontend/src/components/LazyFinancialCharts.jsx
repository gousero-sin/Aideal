import React, { Suspense, lazy } from 'react';

// Os gráficos (recharts, ~400 kB) carregam sob demanda: hero, filtros e KPIs
// aparecem antes e o chunk dos gráficos chega em paralelo.
const loadCharts = () => import('./FinancialCharts');

const LazyMonthlyEvolutionChart = lazy(() => loadCharts().then((module) => ({
  default: module.MonthlyEvolutionChart,
})));
const LazyRankingChart = lazy(() => loadCharts().then((module) => ({
  default: module.RankingChart,
})));
const LazyCompositionDonut = lazy(() => loadCharts().then((module) => ({
  default: module.CompositionDonut,
})));

function ChartFallback({ compact = false }) {
  return (
    <div
      className={`aideal-chart-frame aideal-chart-placeholder ${compact ? 'aideal-chart-frame-compact' : ''}`}
      role="status"
      aria-label="Carregando gráfico"
    />
  );
}

export function MonthlyEvolutionChart(props) {
  return (
    <Suspense fallback={<ChartFallback />}>
      <LazyMonthlyEvolutionChart {...props} />
    </Suspense>
  );
}

export function RankingChart(props) {
  return (
    <Suspense fallback={<ChartFallback compact />}>
      <LazyRankingChart {...props} />
    </Suspense>
  );
}

export function CompositionDonut(props) {
  return (
    <Suspense fallback={<ChartFallback compact />}>
      <LazyCompositionDonut {...props} />
    </Suspense>
  );
}

export const preloadFinancialCharts = () => loadCharts().catch(() => {});

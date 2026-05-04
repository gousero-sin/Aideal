import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  BarChart3,
  Download,
  FileSpreadsheet,
  Gauge,
  RefreshCcw,
  RotateCcw,
  TrendingUp,
  UploadCloud,
} from 'lucide-react';
import {
  ChartCard,
  CompositionDonut,
  MonthlyEvolutionChart,
  RankingChart,
} from './FinancialCharts';
import {
  FinancialHealthCard,
  KpiCard,
  OperationSection,
  PanelHero,
  PanelSkeleton,
  RecentActivityCard,
  SituationGrid,
} from './PanelShared';
import { FilterDock, MonthSlicer, SearchableSlicer, YearSelect } from './PanelSlicers';
import StatusPanel from './StatusPanel';
import UploadPanel from './UploadPanel';
import {
  buildFilterSummary,
  buildPanelQuery,
  countSelectedFilters,
  formatCurrency,
  formatMonths,
  formatNumber,
  formatPercent,
  formatSignedCurrency,
  pickLowestBy,
  pickTopBy,
} from './financialPanelUtils';
import { resolveProcessamentoTotal } from './statusPanelModel';

const emptyFilters = {
  ano: '',
  meses: [],
  centro_custo: [],
  natureza: [],
};

export default function PainelDRE({ apiBase, onNotify, onBusyChange }) {
  const [filters, setFilters] = useState(emptyFilters);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [validacao, setValidacao] = useState(null);
  const [processamento, setProcessamento] = useState(null);
  const [operationBusy, setOperationBusy] = useState(false);
  const [operationOpen, setOperationOpen] = useState(false);

  const query = useMemo(() => buildPanelQuery(filters), [filters]);

  const carregarPainel = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${apiBase}/dre/painel${query ? `?${query}` : ''}`);
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        throw new Error(detail?.detail || 'Erro ao carregar Painel DRE');
      }
      const payload = await response.json();
      setData(payload);
      setFilters((prev) => (prev.ano ? prev : { ...prev, ano: String(payload.periodo?.ano || '') }));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [apiBase, query]);

  useEffect(() => {
    carregarPainel();
  }, [carregarPainel]);

  useEffect(() => {
    onBusyChange?.(loading || operationBusy);
  }, [loading, operationBusy, onBusyChange]);

  useEffect(() => () => onBusyChange?.(false), [onBusyChange]);

  const updateFilter = (key, value) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  const handleYearChange = (ano) => {
    setFilters({ ...emptyFilters, ano });
  };

  const clearFilters = () => {
    setFilters({ ...emptyFilters, ano: filters.ano || String(data?.periodo?.ano || '') });
  };

  const openOperation = () => {
    setOperationOpen(true);
    requestAnimationFrame(() => {
      document.getElementById('operacao-dre')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  };

  const handleValidation = (result) => {
    setValidacao(result);
    if (!result) return;
    onNotify?.(
      result.valido
        ? { type: 'success', message: 'Estrutura DRE validada com sucesso.' }
        : { type: 'error', message: `Validação DRE com ${result.erros?.length || 0} erro(s).` },
    );
  };

  const handleProcess = async (result) => {
    setProcessamento(result);
    if (!result) return;

    const temErro = result?.erros?.length > 0 || result?.status === 'error' || result?.sucesso === false;
    if (temErro) {
      onNotify?.({
        type: 'error',
        message: `DRE com ${result?.erros?.length || 0} erro(s) na etapa ${result?._stage || 'operacional'}.`,
      });
      return;
    }

    await carregarPainel();
    const total = resolveProcessamentoTotal(result);
    if (result?._stage === 'ingestao') {
      onNotify?.({ type: 'success', message: `Mês DRE salvo no banco com ${total} lançamento(s).` });
      return;
    }
    if (result?._stage === 'limpeza') {
      onNotify?.({ type: 'success', message: 'Base DRE limpa e Painel DRE atualizado.' });
      return;
    }
    onNotify?.({ type: 'success', message: `DRE final gerado com ${formatNumber(total)} lançamento(s).` });
  };

  const kpis = data?.kpis || {};
  const filtros = data?.filtros_disponiveis || {};
  const activeFilterCount = countSelectedFilters(filters, ['meses', 'centro_custo', 'natureza']);
  const filterSummary = buildFilterSummary(filters, [
    { key: 'meses', label: 'Mês' },
    { key: 'centro_custo', label: 'Obra' },
    { key: 'natureza', label: 'Natureza' },
  ]);
  const situations = useMemo(() => {
    const mesMaiorSaida = pickTopBy(data?.series_mensais, 'debito');
    const obraImpacto = pickTopBy(data?.ranking_obras, 'saldo', { absolute: true });
    const melhorMes = pickTopBy(data?.series_mensais, 'saldo');
    const piorMes = pickLowestBy(data?.series_mensais, 'saldo');
    const pressaoSaida = Number(kpis.pressao_saida_percentual || 0);

    return [
      {
        label: 'Mês de maior saída',
        value: mesMaiorSaida?.mes_label,
        helper: mesMaiorSaida ? `${formatCurrency(mesMaiorSaida.debito)} em débitos` : 'Sem saídas no filtro',
        tone: 'red',
      },
      {
        label: 'Obra de maior impacto',
        value: obraImpacto?.nome,
        helper: obraImpacto
          ? `${formatSignedCurrency(obraImpacto.saldo)} no saldo`
          : 'Sem obras no período',
      },
      {
        label: 'Melhor mês',
        value: melhorMes?.mes_label,
        helper: melhorMes ? `${formatSignedCurrency(melhorMes.saldo)} de saldo` : 'Sem série mensal',
        tone: 'cyan',
      },
      {
        label: 'Mês sob atenção',
        value: piorMes?.mes_label,
        helper: piorMes ? `${formatSignedCurrency(piorMes.saldo)} de saldo` : 'Sem série mensal',
        tone: 'yellow',
      },
      {
        label: 'Pressão de saídas',
        value: formatPercent(pressaoSaida),
        helper: 'débitos sobre entradas no filtro',
        tone: pressaoSaida > 85 ? 'red' : 'yellow',
      },
    ];
  }, [data, kpis.pressao_saida_percentual]);

  const healthMetrics = useMemo(() => {
    const margem = Number(kpis.margem_resultado_percentual || 0);
    const pressao = Number(kpis.pressao_saida_percentual || 0);
    const saldoMedio = Number(kpis.saldo_medio_mensal || 0);
    const mesesAnalise = Number(kpis.meses_analise || 0);

    return [
      {
        label: 'Margem do resultado',
        value: formatPercent(margem),
        detail: 'saldo líquido / entradas',
        progress: margem,
        tone: margem < 0 ? 'red' : margem < 15 ? 'yellow' : 'cyan',
      },
      {
        label: 'Pressão de saídas',
        value: formatPercent(pressao),
        detail: 'débitos / entradas',
        progress: pressao,
        tone: pressao > 90 ? 'red' : pressao > 65 ? 'yellow' : 'cyan',
      },
      {
        label: 'Saldo médio mensal',
        value: formatSignedCurrency(saldoMedio),
        detail: `${formatMonths(mesesAnalise)} no cálculo`,
        tone: saldoMedio >= 0 ? 'cyan' : 'red',
      },
    ];
  }, [
    kpis.margem_resultado_percentual,
    kpis.meses_analise,
    kpis.pressao_saida_percentual,
    kpis.saldo_medio_mensal,
  ]);

  return (
    <section className="aideal-panel-page">
      <PanelHero
        kicker="Painel DRE"
        title="Resultado por obra e natureza"
        description="Visão executiva do DRE com filtros por período, obra e natureza, evolução mensal e indicadores de saúde financeira."
        meta={[
          { label: 'Período', value: data?.periodo?.label || filters.ano || '-' },
          { label: 'Recortes', value: activeFilterCount > 0 ? formatNumber(activeFilterCount) : 'Todos' },
          { label: 'Status', value: loading ? 'Atualizando' : 'Pronto para análise' },
        ]}
        actions={(
          <>
            <YearSelect anos={filtros.anos} value={filters.ano || data?.periodo?.ano || ''} onChange={handleYearChange} />
            <button className="aideal-action aideal-action-secondary" onClick={openOperation}>
              <UploadCloud size={16} aria-hidden="true" />
              <span>Operação</span>
            </button>
            <button className="aideal-action aideal-action-secondary" onClick={clearFilters} disabled={!activeFilterCount}>
              <RotateCcw size={16} aria-hidden="true" />
              <span>Limpar filtros</span>
            </button>
            <button className="aideal-action aideal-action-primary" onClick={carregarPainel} disabled={loading}>
              <RefreshCcw size={16} aria-hidden="true" />
              <span>{loading ? 'Atualizando' : 'Atualizar'}</span>
            </button>
          </>
        )}
      />

      {error && (
        <article className="aideal-panel aideal-panel-error">
          <strong>Não foi possível carregar o Painel DRE.</strong>
          <div>{error}</div>
        </article>
      )}

      <FilterDock
        title="Filtros do DRE"
        subtitle="Recorte por competência, obra e natureza sem perder o contexto dos gráficos."
        activeCount={activeFilterCount}
        activeItems={filterSummary}
        onClear={clearFilters}
        clearDisabled={!activeFilterCount}
      >
        <MonthSlicer
          available={filtros.meses}
          selected={filters.meses}
          onChange={(value) => updateFilter('meses', value)}
        />
        <SearchableSlicer
          title="Obras"
          options={filtros.centro_custo}
          selected={filters.centro_custo}
          onChange={(value) => updateFilter('centro_custo', value)}
        />
        <SearchableSlicer
          title="Naturezas"
          options={filtros.natureza}
          selected={filters.natureza}
          onChange={(value) => updateFilter('natureza', value)}
        />
      </FilterDock>

      {loading && !data ? (
        <PanelSkeleton />
      ) : (
        <>
          <section className="aideal-insight-grid">
            <KpiCard label="Lançamentos" value={formatNumber(kpis.total_lancamentos)} detail="movimentos no filtro" icon={<FileSpreadsheet size={20} />} />
            <KpiCard label="Entradas" value={formatCurrency(kpis.total_credito)} detail="créditos DRE" tone="cyan" icon={<TrendingUp size={20} />} />
            <KpiCard label="Saídas" value={formatCurrency(kpis.total_debito)} detail="débitos DRE" tone="red" icon={<Download size={20} />} />
            <KpiCard label="Saldo" value={formatCurrency(kpis.saldo_liquido)} detail="resultado líquido" tone="yellow" icon={<BarChart3 size={20} />} />
            <KpiCard label="Fôlego" value={formatMonths(kpis.folego_caixa_meses)} detail="saldo / média de saídas" tone="cyan" icon={<Gauge size={20} />} />
          </section>

          <SituationGrid items={situations} />

          <section className="aideal-analytics-grid">
            <ChartCard title="Evolução mensal" subtitle={data?.periodo?.label} className="is-wide">
              <MonthlyEvolutionChart data={data?.series_mensais} countKey="lancamentos" />
            </ChartCard>
            <ChartCard title="Composição por natureza" subtitle="Peso financeiro por natureza">
              <CompositionDonut data={data?.ranking_naturezas} />
            </ChartCard>
          </section>

          <section className="aideal-analytics-grid aideal-analytics-grid-three">
            <ChartCard title="Ranking por obra" subtitle="Saldo por centro de custo">
              <RankingChart data={data?.ranking_obras} countKey="lancamentos" />
            </ChartCard>
            <FinancialHealthCard
              title="Saúde do resultado"
              subtitle="Indicadores agregados do DRE"
              headline={{
                label: 'Fôlego estimado',
                value: formatMonths(kpis.folego_caixa_meses),
                detail: 'saldo positivo dividido pela média mensal de saídas',
                tone: Number(kpis.folego_caixa_meses || 0) <= 1 ? 'red' : 'cyan',
              }}
              metrics={healthMetrics}
            />
            <RecentActivityCard
              title="Últimos lançamentos"
              subtitle="Movimentos DRE mais recentes dentro do filtro ativo"
              rows={data?.ultimos_lancamentos}
              emptyText="Sem lançamentos no filtro ativo."
              getPrimary={(item) => item.historico || 'Sem histórico'}
              getMeta={(item) => `${item.centro_custo} • ${item.natureza}`}
              getAmount={(item) => formatSignedCurrency(item.saldo)}
              getTone={(item) => (item.saldo >= 0 ? 'is-positive' : 'is-negative')}
            />
          </section>
        </>
      )}

      <div id="operacao-dre">
        <OperationSection
          title="Operação DRE"
          description="Validação, ingestão mensal, geração do arquivo final e download."
          icon={<BarChart3 size={18} aria-hidden="true" />}
          open={operationOpen}
          onOpenChange={setOperationOpen}
          busy={operationBusy}
          hasResults={Boolean(validacao || processamento)}
        >
        <UploadPanel
          fluxo="dre"
          apiBase={apiBase}
          onValidation={handleValidation}
          onProcess={handleProcess}
          processamento={processamento}
          validacao={validacao}
          onBusyChange={setOperationBusy}
        />
        {(validacao || processamento) && (
          <StatusPanel validacao={validacao} processamento={processamento} fluxo="dre" />
        )}
        </OperationSection>
      </div>
    </section>
  );
}

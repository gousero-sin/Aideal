import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Landmark,
  RefreshCcw,
  RotateCcw,
  TrendingDown,
  TrendingUp,
  UploadCloud,
  WalletCards,
} from 'lucide-react';
import {
  ChartCard,
  CompositionDonut,
  MonthlyEvolutionChart,
  RankingChart,
} from './FinancialCharts';
import {
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
  absoluteShare,
  buildFilterSummary,
  buildPanelQuery,
  countSelectedFilters,
  formatCurrency,
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
  banco: [],
  tipo: [],
  classificacao: [],
};

function HighlightBalanceCard({ equilibrio }) {
  const totalDestaques = Number(equilibrio?.total_contas_destaque || 0);
  const outrasSaidas = Number(equilibrio?.outras_saidas || 0);
  const participacao = Number(equilibrio?.participacao_saidas_percentual || 0);
  const cobertura = Number(equilibrio?.cobertura_entradas_percentual || 0);
  const saldo = Number(equilibrio?.saldo_liquido || 0);
  const saldoDestaques = Number(equilibrio?.saldo_apos_contas_destaque || 0);
  const meterWidth = Math.max(0, Math.min(100, participacao));

  return (
    <div className="aideal-balance-panel">
      <div className="aideal-balance-primary">
        <span>Concentração nas 5 contas</span>
        <strong>{formatPercent(participacao)}</strong>
        <p>{formatCurrency(totalDestaques)} das saídas mapeadas</p>
      </div>
      <div className="aideal-balance-meter" aria-label="Participação das contas em destaque nas saídas">
        <i style={{ width: `${meterWidth}%` }} />
      </div>
      <div className="aideal-balance-grid">
        <div>
          <span>Outras saídas</span>
          <strong>{formatCurrency(outrasSaidas)}</strong>
        </div>
        <div>
          <span>Cobertura por entradas</span>
          <strong>{formatPercent(cobertura)}</strong>
        </div>
        <div>
          <span>Saldo total</span>
          <strong className={saldo >= 0 ? 'is-positive' : 'is-negative'}>
            {formatSignedCurrency(saldo)}
          </strong>
        </div>
        <div>
          <span>Saldo vs. 5 contas</span>
          <strong className={saldoDestaques >= 0 ? 'is-positive' : 'is-negative'}>
            {formatSignedCurrency(saldoDestaques)}
          </strong>
        </div>
      </div>
    </div>
  );
}

export default function PainelFluxoCaixa({ apiBase, onNotify, onBusyChange }) {
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
      const response = await fetch(`${apiBase}/fluxo_caixa/painel${query ? `?${query}` : ''}`);
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        throw new Error(detail?.detail || 'Erro ao carregar Painel Fluxo de Caixa');
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
      document.getElementById('operacao-fluxo')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  };

  const handleValidation = (result) => {
    setValidacao(result);
    if (!result) return;
    onNotify?.(
      result.valido
        ? { type: 'success', message: 'Estrutura do Fluxo de Caixa validada com sucesso.' }
        : { type: 'error', message: `Validação Fluxo com ${result.erros?.length || 0} erro(s).` },
    );
  };

  const handleProcess = async (result) => {
    setProcessamento(result);
    if (!result) return;

    const temErro = result?.erros?.length > 0 || result?.status === 'error' || result?.sucesso === false;
    if (temErro) {
      onNotify?.({
        type: 'error',
        message: `Fluxo de Caixa com ${result?.erros?.length || 0} erro(s) na etapa ${result?._stage || 'operacional'}.`,
      });
      return;
    }

    await carregarPainel();
    const total = resolveProcessamentoTotal(result);
    if (result?._stage === 'ingestao') {
      onNotify?.({ type: 'success', message: `Lote Fluxo salvo no banco com ${total} movimento(s).` });
      return;
    }
    if (result?._stage === 'limpeza') {
      onNotify?.({
        type: 'success',
        message: `Mês Fluxo de Caixa ${result?._competenciaLabel || ''} excluído e painel atualizado.`,
      });
      return;
    }
    onNotify?.({ type: 'success', message: `Fluxo de Caixa gerado com ${formatNumber(total)} movimento(s).` });
  };

  const kpis = data?.kpis || {};
  const filtros = data?.filtros_disponiveis || {};
  const contasDestaque = Array.isArray(data?.contas_destaque) ? data.contas_destaque : [];
  const equilibrioDestaques = data?.equilibrio_contas_destaque || {};
  const composicaoDestaques = useMemo(
    () => contasDestaque.map((grupo) => ({
      nome: grupo.nome,
      saldo: grupo.total,
      movimentos: grupo.movimentos,
    })),
    [contasDestaque],
  );
  const activeFilterCount = countSelectedFilters(filters, ['meses', 'banco', 'tipo', 'classificacao']);
  const filterSummary = buildFilterSummary(filters, [
    { key: 'meses', label: 'Mês' },
    { key: 'banco', label: 'Banco' },
    { key: 'tipo', label: 'Tipo' },
    { key: 'classificacao', label: 'Classificação' },
  ]);
  const situations = useMemo(() => {
    const saldoCritico = pickLowestBy(data?.series_mensais, 'saldo');
    const maiorSaida = pickTopBy(data?.ranking_classificacoes, 'debito');
    const bancoMovimentado = pickTopBy(data?.ranking_bancos, 'saldo', { absolute: true });
    const classificacaoDominante = pickTopBy(data?.ranking_classificacoes, 'saldo', { absolute: true });
    const melhorMes = pickTopBy(data?.series_mensais, 'saldo');

    return [
      {
        label: 'Saldo crítico',
        value: saldoCritico?.mes_label,
        helper: saldoCritico ? `${formatSignedCurrency(saldoCritico.saldo)} de saldo` : 'Sem série mensal',
        tone: 'red',
      },
      {
        label: 'Maior saída',
        value: maiorSaida?.nome,
        helper: maiorSaida ? `${formatCurrency(maiorSaida.debito)} em débitos` : 'Sem saídas no filtro',
        tone: 'red',
      },
      {
        label: 'Banco mais relevante',
        value: bancoMovimentado?.nome,
        helper: bancoMovimentado
          ? `${formatSignedCurrency(bancoMovimentado.saldo)} no saldo`
          : 'Sem bancos no período',
      },
      {
        label: 'Classificação dominante',
        value: classificacaoDominante?.nome,
        helper: classificacaoDominante
          ? `${formatPercent(absoluteShare(classificacaoDominante, data?.ranking_classificacoes))} do impacto ranqueado`
          : 'Sem classificação calculada',
        tone: 'yellow',
      },
      {
        label: 'Melhor mês',
        value: melhorMes?.mes_label,
        helper: melhorMes ? `${formatSignedCurrency(melhorMes.saldo)} de saldo` : 'Sem série mensal',
        tone: 'cyan',
      },
    ];
  }, [data]);

  return (
    <section className="aideal-panel-page">
      <PanelHero
        kicker="Painel Fluxo de Caixa"
        title="Entradas, saídas, bancos e classificações"
        description="Controle de liquidez com filtros executivos, situações críticas, rankings e evolução mensal consolidada."
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
          <strong>Não foi possível carregar o Painel Fluxo de Caixa.</strong>
          <div>{error}</div>
        </article>
      )}

      <FilterDock
        title="Filtros do Fluxo de Caixa"
        subtitle="Recorte a liquidez por competência, banco, tipo e classificação gerencial."
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
          title="Bancos"
          options={filtros.banco}
          selected={filters.banco}
          onChange={(value) => updateFilter('banco', value)}
        />
        <SearchableSlicer
          title="Tipo"
          options={filtros.tipo}
          selected={filters.tipo}
          onChange={(value) => updateFilter('tipo', value)}
        />
        <SearchableSlicer
          title="Classificações"
          options={filtros.classificacao}
          selected={filters.classificacao}
          onChange={(value) => updateFilter('classificacao', value)}
        />
      </FilterDock>

      {loading && !data ? (
        <PanelSkeleton />
      ) : (
        <>
          <section className="aideal-insight-grid">
            <KpiCard label="Movimentos" value={formatNumber(kpis.total_movimentos)} detail="registros no filtro" icon={<WalletCards size={20} />} />
            <KpiCard label="Entradas" value={formatCurrency(kpis.total_creditos)} detail="créditos bancários" tone="cyan" icon={<TrendingUp size={20} />} />
            <KpiCard label="Saídas" value={formatCurrency(kpis.total_debitos)} detail="débitos bancários" tone="red" icon={<TrendingDown size={20} />} />
            <KpiCard label="Saldo" value={formatCurrency(kpis.saldo_liquido)} detail="posição líquida" tone="yellow" icon={<WalletCards size={20} />} />
            <KpiCard label="Bancos" value={formatNumber(kpis.total_bancos)} detail="origens bancárias" icon={<Landmark size={20} />} />
          </section>

          <SituationGrid items={situations} />

          <section className="aideal-analytics-grid aideal-flow-focus-grid" aria-label="Contas em destaque do fluxo de caixa">
            <ChartCard title="5 contas em destaque" subtitle={data?.periodo?.label}>
              <CompositionDonut data={composicaoDestaques} />
            </ChartCard>
            <ChartCard title="Equilíbrio das saídas" subtitle="5 contas x fluxo total">
              <HighlightBalanceCard equilibrio={equilibrioDestaques} />
            </ChartCard>
          </section>

          <section className="aideal-analytics-grid">
            <ChartCard title="Evolução mensal" subtitle={data?.periodo?.label} className="is-wide">
              <MonthlyEvolutionChart data={data?.series_mensais} countKey="movimentos" />
            </ChartCard>
            <ChartCard title="Composição por banco" subtitle="Distribuição financeira por banco">
              <CompositionDonut data={data?.ranking_bancos} />
            </ChartCard>
          </section>

          <section className="aideal-analytics-grid aideal-analytics-grid-three">
            <ChartCard title="Ranking por banco" subtitle="Saldo por origem bancária">
              <RankingChart data={data?.ranking_bancos} countKey="movimentos" />
            </ChartCard>
            <ChartCard title="Ranking por classificação" subtitle="Classificações com maior impacto">
              <RankingChart data={data?.ranking_classificacoes} countKey="movimentos" />
            </ChartCard>
            <RecentActivityCard
              title="Movimentos recentes"
              subtitle="Últimas entradas e saídas no filtro ativo"
              rows={data?.movimentos_recentes}
              emptyText="Sem movimentos no filtro ativo."
              getPrimary={(item) => item.descricao || 'Sem descrição'}
              getMeta={(item) => `${item.banco} • ${item.classificacao}`}
              getAmount={(item) => formatSignedCurrency(item.saldo_liquido)}
              getTone={(item) => (item.saldo_liquido >= 0 ? 'is-positive' : 'is-negative')}
            />
          </section>
        </>
      )}

      <div id="operacao-fluxo">
        <OperationSection
          title="Operação Fluxo de Caixa"
          description="Validação em lote, ingestão mensal, geração do consolidado e download."
          icon={<WalletCards size={18} aria-hidden="true" />}
          open={operationOpen}
          onOpenChange={setOperationOpen}
          busy={operationBusy}
          hasResults={Boolean(validacao || processamento)}
        >
        <UploadPanel
          fluxo="fluxo_caixa"
          apiBase={apiBase}
          onValidation={handleValidation}
          onProcess={handleProcess}
          processamento={processamento}
          validacao={validacao}
          onBusyChange={setOperationBusy}
        />
        {(validacao || processamento) && (
          <StatusPanel validacao={validacao} processamento={processamento} fluxo="fluxo_caixa" />
        )}
        </OperationSection>
      </div>
    </section>
  );
}

import React from 'react';
import { Activity, ArrowRight, BarChart3, Database, RefreshCcw, WalletCards } from 'lucide-react';
import { GlacierGlassCard, SkeletonText } from 'goflow-core';

const MESES_LABEL = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];

const formatCurrency = (value) =>
  new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    maximumFractionDigits: 0,
  }).format(Number(value || 0));

const formatNumber = (value) => new Intl.NumberFormat('pt-BR').format(Number(value || 0));

const formatMeses = (meses) => {
  if (!Array.isArray(meses) || meses.length === 0) return 'Sem meses';
  return meses.map((mes) => MESES_LABEL[mes - 1] || String(mes).padStart(2, '0')).join(', ');
};

function MetricTile({ label, value, tone = 'blue' }) {
  return (
    <div className={`aideal-metric-tile aideal-metric-tile-${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function FlowSummaryCard({ kind, title, icon, data, onOpenFlow }) {
  const isDre = kind === 'dre';
  const totalPrimary = isDre ? data?.total_lancamentos : data?.total_movimentos;
  const credito = isDre ? data?.total_credito : data?.total_creditos;
  const debito = isDre ? data?.total_debito : data?.total_debitos;
  const ultimo = data?.ultimo_upload;

  return (
    <GlacierGlassCard className="aideal-dashboard-card">
      <div className="aideal-card-heading">
        <div className="aideal-card-icon">{icon}</div>
        <div>
          <h2>{title}</h2>
          <p>{formatMeses(data?.meses_disponiveis)}</p>
        </div>
      </div>

      <div className="aideal-metric-grid">
        <MetricTile label={isDre ? 'Lançamentos' : 'Movimentos'} value={formatNumber(totalPrimary)} />
        <MetricTile label="Entradas" value={formatCurrency(credito)} tone="cyan" />
        <MetricTile label="Saídas" value={formatCurrency(debito)} tone="red" />
        <MetricTile label="Saldo" value={formatCurrency(data?.saldo_liquido)} tone="yellow" />
      </div>

      <div className="aideal-card-footer">
        <div>
          <span className="aideal-muted-label">Última ingestão</span>
          <strong>{ultimo?.arquivo_nome || 'Nenhum arquivo salvo'}</strong>
        </div>
        <button className="aideal-action aideal-action-secondary" onClick={() => onOpenFlow(kind)}>
          <span>Operar</span>
          <ArrowRight size={16} aria-hidden="true" />
        </button>
      </div>
    </GlacierGlassCard>
  );
}

function RecentEvents({ logs }) {
  const eventos = Array.isArray(logs) ? logs : [];
  return (
    <GlacierGlassCard className="aideal-dashboard-card aideal-dashboard-card-compact">
      <div className="aideal-card-heading">
        <div className="aideal-card-icon">
          <Activity size={20} aria-hidden="true" />
        </div>
        <div>
          <h2>Últimos eventos</h2>
          <p>Logs recentes de geração e processamento</p>
        </div>
      </div>

      <div className="aideal-event-list">
        {eventos.length === 0 ? (
          <div className="aideal-empty-state">Sem eventos recentes.</div>
        ) : (
          eventos.map((evento) => (
            <div key={evento.id} className="aideal-event-row">
              <div>
                <strong>{evento.fluxo === 'fluxo_caixa' ? 'Fluxo de Caixa' : 'DRE'}</strong>
                <span>{evento.arquivo_saida || evento.arquivos_entrada?.[0] || 'Processamento registrado'}</span>
              </div>
              <em>{evento.status || 'registrado'}</em>
            </div>
          ))
        )}
      </div>
    </GlacierGlassCard>
  );
}

export default function DashboardOverview({
  data,
  loading,
  error,
  onRefresh,
  onOpenFlow,
}) {
  if (loading && !data) {
    return (
      <section className="aideal-dashboard-grid">
        <GlacierGlassCard className="aideal-dashboard-card">
          <SkeletonText style={{ width: 220, marginBottom: 14 }} />
          <SkeletonText style={{ width: '90%', marginBottom: 10 }} />
          <SkeletonText style={{ width: '70%' }} />
        </GlacierGlassCard>
        <GlacierGlassCard className="aideal-dashboard-card">
          <SkeletonText style={{ width: 220, marginBottom: 14 }} />
          <SkeletonText style={{ width: '90%', marginBottom: 10 }} />
          <SkeletonText style={{ width: '70%' }} />
        </GlacierGlassCard>
      </section>
    );
  }

  return (
    <section className="aideal-dashboard-stack">
      <div className="aideal-dashboard-toolbar">
        <div>
          <span className="aideal-muted-label">Competência executiva</span>
          <strong>{data?.competencia || '-'}</strong>
        </div>
        <button className="aideal-action aideal-action-secondary" onClick={onRefresh} disabled={loading}>
          <RefreshCcw size={16} aria-hidden="true" />
          <span>{loading ? 'Atualizando' : 'Atualizar'}</span>
        </button>
      </div>

      {error && (
        <article className="aideal-panel aideal-panel-error">
          <strong>Não foi possível carregar o dashboard.</strong>
          <div>{error}</div>
        </article>
      )}

      <section className="aideal-dashboard-grid">
        <FlowSummaryCard
          kind="dre"
          title="DRE"
          icon={<BarChart3 size={22} aria-hidden="true" />}
          data={data?.dre || {}}
          onOpenFlow={onOpenFlow}
        />
        <FlowSummaryCard
          kind="fluxo_caixa"
          title="Fluxo de Caixa"
          icon={<WalletCards size={22} aria-hidden="true" />}
          data={data?.fluxo_caixa || {}}
          onOpenFlow={onOpenFlow}
        />
      </section>

      <section className="aideal-dashboard-grid aideal-dashboard-grid-secondary">
        <RecentEvents logs={data?.logs_recentes} />
        <GlacierGlassCard className="aideal-dashboard-card aideal-dashboard-card-compact">
          <div className="aideal-card-heading">
            <div className="aideal-card-icon">
              <Database size={20} aria-hidden="true" />
            </div>
            <div>
              <h2>Base operacional</h2>
              <p>Status de API e persistência local</p>
            </div>
          </div>
          <div className="aideal-system-list">
            <div>
              <span>API</span>
              <strong>{data?.health?.api || 'operacional'}</strong>
            </div>
            <div>
              <span>Banco</span>
              <strong>{data?.health?.database || 'ok'}</strong>
            </div>
            <div>
              <span>Uploads DRE</span>
              <strong>{formatNumber(data?.dre?.uploads_completed)} concluídos</strong>
            </div>
            <div>
              <span>Uploads Fluxo</span>
              <strong>{formatNumber(data?.fluxo_caixa?.uploads_completed)} concluídos</strong>
            </div>
          </div>
        </GlacierGlassCard>
      </section>
    </section>
  );
}
